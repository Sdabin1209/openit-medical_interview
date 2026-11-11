"""ASGI 를 직접 부르는 시험 도구: 응답 본문을 조각마다 받고, 키오스크가 끊는 것을 흉내 낸다.

왜 httpx.ASGITransport 로 안 되나: 그것은 본문을 끝까지 모은 뒤에 돌려줘서 '받는 대로 흘린다'와 '끊겨도 끝까지
처리한다'를 볼 수 없다.
"""

import asyncio
import json
from typing import Any

from fastapi import FastAPI
from starlette.types import Message


def parse_events(raw: bytes) -> list[tuple[str, dict[str, Any]]]:
    """SSE 본문을 (event 줄, data 의 JSON) 목록으로 읽는다(WHATWG HTML 9.2.6). data 의 event 칸이 event 줄과 같은지도 본다."""
    events: list[tuple[str, dict[str, Any]]] = []
    for block in raw.decode().split("\n\n"):
        if not block:
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        data = json.loads(fields["data"])
        assert data["event"] == fields["event"]
        events.append((fields["event"], data))
    return events


class Call:
    """진행 중인 HTTP 호출 하나. 본문 조각을 하나씩 받고 끊을 수 있다."""

    def __init__(self, app: FastAPI, path: str, body: dict[str, Any], headers: dict[str, str]) -> None:
        raw = json.dumps(body).encode()
        self._scope: dict[str, Any] = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1", "method": "POST",
            "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "", "scheme": "https",
            "server": ("survey-service", 443), "client": ("gateway", 1),
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]
            + [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }  # fmt: skip
        self._body, self._sent_body = raw, False
        self._disconnected = asyncio.Event()
        self.messages: asyncio.Queue[Message] = asyncio.Queue()
        self._app = app
        self._task: asyncio.Task[None] | None = None

    async def _receive(self) -> Message:
        if not self._sent_body:
            self._sent_body = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        await self._disconnected.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: Message) -> None:
        self.messages.put_nowait(message)

    async def open(self) -> dict[str, str]:
        """호출을 시작해 응답 머리를 받고 머리글을 돌려준다(상태 코드는 self.status)."""
        self._task = asyncio.get_running_loop().create_task(self._app(self._scope, self._receive, self._send))
        start = await self.messages.get()
        assert start["type"] == "http.response.start"
        self.status: int = start["status"]
        return {k.decode(): v.decode() for k, v in start["headers"]}

    async def chunk(self) -> bytes | None:
        """본문 조각 하나. 본문이 끝났으면 None."""
        message = await self.messages.get()
        if not message.get("more_body", False) and not message.get("body"):
            return None
        return bytes(message["body"])

    def disconnect(self) -> None:
        self._disconnected.set()

    async def finish(self) -> None:
        assert self._task is not None
        await self._task
