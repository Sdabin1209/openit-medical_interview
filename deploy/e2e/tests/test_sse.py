"""SSE 읽기와 응답 문장 스트림 점검: 정해 둔 바이트열로 시험한다(네트워크 없음). 조각 경계가 줄·CRLF·UTF-8 문자를 가르는 경우를 포함한다."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from openit_e2e.contract import Contract, StepFailure
from openit_e2e.sse import SseParser, StreamChecker, parse_events, read_stream

REPO = Path(__file__).resolve().parents[3]
CONTRACT = Contract(REPO / "contracts")
SESSION = "11111111-2222-4333-8444-555555555555"
TURN = "66666666-7777-4888-8999-000000000000"
HEADERS = {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store, no-transform"}


def sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


DELTA_1 = sse("delta", {"event": "delta", "text": "안녕"})
DELTA_2 = sse("delta", {"event": "delta", "text": "하세요"})
STARTED = {"session_id": SESSION, "status": "ACTIVE", "questionnaire_id": "q-1", "response_text": "안녕하세요"}
RESULT = sse("result", {"event": "result", "result": STARTED})
ERROR = sse("error", {"event": "error", "problem": {"type": "about:blank", "title": "x", "status": 503}})


def one_byte_chunks(raw: bytes) -> list[bytes]:
    return [raw[i : i + 1] for i in range(len(raw))]


# ---------------------------------------------------------------- 파서(WHATWG HTML 9.2)
def test_events_are_the_same_for_any_chunking() -> None:
    raw = DELTA_1 + DELTA_2 + RESULT
    whole = parse_events([raw])
    assert [e.event for e in whole] == ["delta", "delta", "result"]
    assert parse_events(one_byte_chunks(raw)) == whole  # 한 바이트씩: 줄과 UTF-8 문자 한가운데가 모두 갈린다
    for cut in range(len(raw)):
        assert parse_events([raw[:cut], raw[cut:]]) == whole


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_all_three_line_endings_and_split_crlf(newline: bytes) -> None:
    raw = b"event: a" + newline + b"data: 1" + newline + newline + b"data: 2" + newline + newline
    expected = parse_events([raw])
    assert [(e.event, e.data) for e in expected] == [("a", "1"), ("message", "2")]
    assert parse_events(one_byte_chunks(raw)) == expected  # CR 과 LF 사이에서 갈려도 빈 줄이 하나 더 생기지 않는다


def test_comment_bom_multiline_data_and_single_space_strip() -> None:
    raw = "﻿: 주석\ndata:  두 칸\ndata: 둘째\n\n".encode()
    (event,) = parse_events(one_byte_chunks(raw))
    assert event.data == " 두 칸\n둘째"  # 콜론 뒤 공백은 하나만 뗀다


def test_unterminated_last_event_is_dropped_and_field_without_colon() -> None:
    assert parse_events([b"data: 1\n\ndata: 2"]) != []
    assert len(parse_events([b"data: 1\n\ndata: 2"])) == 1
    (event,) = parse_events([b"data\n\n"])
    assert event.data == ""


def test_parser_reuses_across_feeds() -> None:
    parser = SseParser()
    assert parser.feed(b"data: a\n") == []
    assert [e.data for e in parser.feed(b"\n")] == ["a"]


# ---------------------------------------------------------------- 스트림 규칙
def check(raw: bytes, schema: str = "SessionStartStreamEvent") -> Any:
    checker = StreamChecker(CONTRACT, schema, clock=iter([0.0, 0.1, 0.3, 0.6, 1.0]).__next__)
    for event in parse_events(one_byte_chunks(raw)):
        checker.accept(event)
    return checker.finish()


def test_delta_then_result_is_recorded_with_counts_and_times() -> None:
    outcome = check(DELTA_1 + DELTA_2 + RESULT)
    assert outcome.deltas == 2 and outcome.text == "안녕하세요" and outcome.result == STARTED and outcome.error is None
    assert outcome.first_delta_seconds == pytest.approx(0.1) and outcome.result_seconds == pytest.approx(0.6)
    assert "delta 2개" in outcome.describe()


def test_result_alone_and_error_alone_are_valid_endings() -> None:
    assert check(RESULT).deltas == 0
    assert check(DELTA_1 + ERROR).error["problem"]["status"] == 503


def test_stream_without_result_or_error_fails() -> None:
    with pytest.raises(StepFailure, match="result 나 error 없이"):
        check(DELTA_1 + DELTA_2)


def test_event_after_the_end_fails() -> None:
    with pytest.raises(StepFailure, match="더 왔다"):
        check(RESULT + DELTA_1)
    with pytest.raises(StepFailure, match="더 왔다"):
        check(RESULT + ERROR)


def test_event_line_must_match_data_event_field() -> None:
    wrong = sse("result", {"event": "delta", "text": "x"})
    with pytest.raises(StepFailure, match="다르다"):
        check(wrong + RESULT)


def test_data_that_breaks_the_schema_fails() -> None:
    bad = sse("result", {"event": "result", "result": {**STARTED, "status": "NOPE"}})
    with pytest.raises(StepFailure, match="계약을 어겼다"):
        check(bad)
    with pytest.raises(StepFailure, match="JSON 이 아니다"):
        check(b"event: delta\ndata: {not json\n\n")


def test_turn_schema_takes_turn_result_and_rejects_session_result() -> None:
    turn = sse("result", {"event": "result", "result": {"turn_id": TURN, "status": "ACTIVE"}})
    assert check(turn, "TurnStreamEvent").result["turn_id"] == TURN
    with pytest.raises(StepFailure, match="계약을 어겼다"):
        check(RESULT, "TurnStreamEvent")


# ---------------------------------------------------------------- 응답 머리글과 상태 코드(가짜 서버)
def serve(body: bytes, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "text/event-stream"
        return httpx.Response(
            status, headers=HEADERS if headers is None else headers, content=(body[i : i + 7] for i in range(0, len(body), 7))
        )  # 생성기: 실제 연결처럼 조각으로 온다

    return httpx.Client(base_url="https://x.invalid", transport=httpx.MockTransport(handler))


def run(client: httpx.Client) -> Any:
    return read_stream(client, CONTRACT, "survey-service", "startSessionStream", body={"start_code": "123456"})


def test_read_stream_passes_with_valid_headers() -> None:
    outcome = run(serve(DELTA_1 + RESULT))
    assert outcome.deltas == 1 and outcome.result == STARTED


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({"Content-Type": "application/json", "Cache-Control": "no-store, no-transform"}, "Content-Type"),
        ({"Content-Type": "text/event-stream"}, "Cache-Control"),
        ({"Content-Type": "text/event-stream", "Cache-Control": "no-store"}, "Cache-Control"),
        ({**HEADERS, "Content-Encoding": "gzip"}, "압축"),
    ],
)
def test_read_stream_rejects_bad_headers(headers: dict[str, str], message: str) -> None:
    with pytest.raises(StepFailure, match=message):
        run(serve(gzip.compress(DELTA_1 + RESULT) if "Content-Encoding" in headers else DELTA_1 + RESULT, headers=headers))


def test_read_stream_rejects_non_200() -> None:
    with pytest.raises(StepFailure, match="상태 503"):
        run(serve(b'{"title":"x"}', status=503, headers={"Content-Type": "application/problem+json"}))


def test_read_stream_rejects_request_body_that_breaks_the_contract() -> None:
    with pytest.raises(StepFailure, match="보내려던 요청 본문"):
        read_stream(serve(RESULT), CONTRACT, "survey-service", "startSessionStream", body={"start_code": "1"})
