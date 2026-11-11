"""Server-Sent Events 읽기(WHATWG HTML 9.2 'Parsing an event stream')와 응답 문장 스트림의 규칙 점검(계약 README '응답 문장 스트림').

왜 직접 쓰나: 필요한 것은 필드 네 개(event, data, id, retry)와 줄 끝 세 가지(CRLF, LF, CR)의 해석뿐이고 규격이 짧다. 청크 경계가 줄 한가운데나 CRLF 사이를 가르는 경우를
시험으로 고정해 두려면 바이트를 받는 파서가 필요한데, 라이브러리는 줄을 이미 나눈 입력을 받는 쪽이 많다. 외부 의존을 늘리지 않는다.
"""

from __future__ import annotations

import codecs
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import httpx

from .contract import Contract, StepFailure

EVENT_STREAM = "text/event-stream"
STREAM_CACHE_CONTROL = "no-store, no-transform"


@dataclass(frozen=True)
class SseEvent:
    event: str  # 규격의 기본값은 message
    data: str
    last_event_id: str = ""


class SseParser:
    """바이트 조각을 먹여 이벤트를 꺼낸다. 조각 경계는 어디여도 된다(줄 한가운데, CR 과 LF 사이, UTF-8 문자 한가운데)."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._buffer = ""
        self._pending_cr = False  # 직전 조각이 CR 로 끝났다: 다음 글자가 LF 면 같은 줄 끝이다
        self._first = True  # 맨 앞의 BOM 은 버린다(규격)
        self._event = ""
        self._data: list[str] = []
        self._last_id = ""

    def feed(self, chunk: bytes) -> list[SseEvent]:
        return self._consume(self._decoder.decode(chunk))

    def close(self) -> list[SseEvent]:
        """스트림 끝. 빈 줄로 끝나지 않은 마지막 이벤트는 버린다(규격: 이벤트는 빈 줄에서 완성된다)."""
        self._decoder.decode(b"", final=True)
        return []

    def _consume(self, text: str) -> list[SseEvent]:
        if self._first and text:
            self._first = False
            text = text.removeprefix("﻿")
        if self._pending_cr and text:
            self._pending_cr = False
            text = text.removeprefix("\n")
        text = self._buffer + text
        events: list[SseEvent] = []
        start = 0
        index = 0
        while index < len(text):
            char = text[index]
            if char not in "\r\n":
                index += 1
                continue
            if char == "\r" and index + 1 == len(text):
                self._pending_cr = True  # LF 가 뒤에 올지 아직 모른다
                events.extend(self._line(text[start:index]))
                start = index + 1
                break
            events.extend(self._line(text[start:index]))
            index += 2 if char == "\r" and text[index + 1] == "\n" else 1
            start = index
        self._buffer = text[start:]
        return events

    def _line(self, line: str) -> list[SseEvent]:
        if line == "":
            if not self._data:
                self._event = ""
                return []
            event = SseEvent(self._event or "message", "\n".join(self._data), self._last_id)
            self._event = ""
            self._data = []
            return [event]
        if line.startswith(":"):
            return []
        name, sep, value = line.partition(":")
        if sep and value.startswith(" "):
            value = value[1:]
        if name == "event":
            self._event = value
        elif name == "data":
            self._data.append(value)
        elif name == "id" and "\0" not in value:
            self._last_id = value
        return []  # retry 는 읽지 않는다: 이 시험은 재연결하지 않는다


def parse_events(chunks: Iterable[bytes]) -> list[SseEvent]:
    parser = SseParser()
    events: list[SseEvent] = []
    for chunk in chunks:
        events.extend(parser.feed(chunk))
    events.extend(parser.close())
    return events


@dataclass
class StreamOutcome:
    """스트림 한 건의 관측. 시간은 단조 시계(time.monotonic)로 잰 보고용 값이고 합격을 가르는 데 쓰지 않는다."""

    deltas: int = 0
    first_delta_seconds: float | None = None
    result_seconds: float | None = None
    result: Any = None  # result 이벤트의 result 칸(짝인 JSON 작업의 성공 본문)
    error: Any = None  # error 이벤트의 data
    text: str = field(default="")  # delta 를 이은 글

    def describe(self) -> str:
        first = "-" if self.first_delta_seconds is None else f"{self.first_delta_seconds:.2f}초"
        end = "-" if self.result_seconds is None else f"{self.result_seconds:.2f}초"
        return f"delta {self.deltas}개, 첫 delta {first}, result {end}"


class StreamChecker:
    """이벤트를 하나씩 받아 계약의 스트림 규칙을 점검한다: data 가 스키마를 지키는지, event 줄과 data.event 가 같은지, delta* 뒤에 result|error 하나로 끝나는지."""

    def __init__(self, contract: Contract, schema_name: str, clock: Any = time.monotonic) -> None:
        self._validator = contract.named(schema_name)
        self._contract = contract
        self._clock = clock
        self._began = clock()
        self.outcome = StreamOutcome()
        self._ended = False

    def accept(self, event: SseEvent) -> None:
        if self._ended:
            raise StepFailure(f"스트림이 result·error 로 끝난 뒤에 이벤트({event.event})가 더 왔다")
        try:
            data = json.loads(event.data)
        except ValueError as error:
            raise StepFailure(f"이벤트 data 가 JSON 이 아니다: {event.data[:120]!r}") from error
        if errors := self._contract.schema_errors(self._validator, data):
            raise StepFailure(f"이벤트({event.event})가 계약을 어겼다: {errors}")
        if event.event != data["event"]:
            raise StepFailure(f"SSE event 줄({event.event})과 data 의 event 칸({data['event']})이 다르다")
        now = self._clock() - self._began
        if data["event"] == "delta":
            if self.outcome.first_delta_seconds is None:
                self.outcome.first_delta_seconds = now
            self.outcome.deltas += 1
            self.outcome.text += data["text"]
            return
        self._ended = True
        self.outcome.result_seconds = now
        if data["event"] == "result":
            self.outcome.result = data["result"]
        else:
            self.outcome.error = data

    def finish(self) -> StreamOutcome:
        if not self._ended:
            raise StepFailure("스트림이 result 나 error 없이 끝났다")
        return self.outcome


def check_stream_headers(response: httpx.Response) -> None:
    media = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if media != EVENT_STREAM:
        raise StepFailure(f"스트림의 Content-Type 이 {EVENT_STREAM} 이 아니다: {response.headers.get('content-type')}")
    if response.headers.get("cache-control") != STREAM_CACHE_CONTROL:
        raise StepFailure(f"스트림의 Cache-Control 이 '{STREAM_CACHE_CONTROL}' 이 아니다: {response.headers.get('cache-control')}")
    if response.headers.get("content-encoding"):
        raise StepFailure(f"스트림을 압축했다(Content-Encoding {response.headers.get('content-encoding')})")


def read_stream(
    client: httpx.Client,
    contract: Contract,
    service: str,
    operation_id: str,
    *,
    path: dict[str, str] | None = None,
    body: Any = None,
) -> StreamOutcome:
    """스트림 작업 하나를 부르고 읽는다. 상태 200 과 머리글, 이벤트 규칙을 점검하고 관측을 돌려준다. 실패한 호출을 다시 보내지 않는다."""
    op = contract.operations[(service, operation_id)]
    schema = op.spec["responses"]["200"]["content"][EVENT_STREAM]["x-event-data-schema"]["$ref"].rsplit("/", 1)[-1]
    request_schema = contract.request_schema(op)
    if body is not None and request_schema is not None and (errors := contract.schema_errors(contract.validator(request_schema), body)):
        raise StepFailure(f"{operation_id}: 보내려던 요청 본문이 계약을 어겼다(시험 코드의 결함): {errors}")
    checker = StreamChecker(contract, schema)
    parser = SseParser()
    with client.stream(op.method, op.path.format(**(path or {})), json=body, headers={"Accept": EVENT_STREAM}) as response:
        if response.status_code != 200:
            response.read()
            raise StepFailure(f"{operation_id}: 상태 {response.status_code}(기대 200) {response.text[:300]}")
        check_stream_headers(response)
        for chunk in response.iter_raw():  # 왜 iter_raw: 압축 해제 없이 중간 장치가 준 바이트를 받는 대로 읽는다
            for event in parser.feed(chunk):
                checker.accept(event)
        for event in parser.close():
            checker.accept(event)
    return checker.finish()
