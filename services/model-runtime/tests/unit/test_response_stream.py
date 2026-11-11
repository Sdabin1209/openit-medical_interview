"""generateResponseStream: 조각 순서와 result 일치, 344자 끊기, 빈 출력, 엔진 실패, 시간 상한, 스트림 전 409·503.

추론 엔진은 시험이 정한 조각을 내는 가짜(ScriptedChat)이고, 시간은 시험이 정한 상한(0초)과 영원히 끝나지 않는 조각
기다림으로 넘긴다(실제 대기와 벽시계 없음).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from fastapi import FastAPI

from model_runtime.contract.models import ResponseStreamEvent
from model_runtime.types import ChatRequest, EngineError
from scenario.world import B_REQUEST, World, world
from support import Identity, make_app, settings_for

pytestmark = pytest.mark.anyio
IDENTITY = Identity.new()
BODY: dict[str, Any] = {"runtime_contract_version": 1, **B_REQUEST}
NEVER = object()  # 이 자리에서 영원히 기다린다(시간 상한 시험)


class ScriptedChat:
    """stream 이 script 의 항목을 차례로 낸다. 예외는 던지고 NEVER 는 끝나지 않는 기다림이다."""

    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.requests: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> str:  # pragma: no cover
        raise NotImplementedError

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        self.requests.append(request)
        for item in self.script:
            if item is NEVER:
                await asyncio.Event().wait()
            if isinstance(item, BaseException):
                raise item
            yield item


async def run(tmp: Path, script: list[Any], body: dict[str, Any] = BODY, limit: float | None = None) -> Any:  # noqa: ANN401
    """적재를 마친 앱에 스트림 요청을 보내 응답과 가짜 엔진을 돌려준다."""
    chat = ScriptedChat(script)
    tmp.mkdir(exist_ok=True)
    with world(tmp) as w:
        digest = await anyio.to_thread.run_sync(
            lambda: w.publish("stream")
        )  # 도구가 자기 이벤트 루프를 쓰므로 스레드에서
        app = build(w, tmp, chat, limit)
        async with app.router.lifespan_context(app):
            await app.state.runtime.activate(digest, "시험", "approver")
            await app.state.runtime.wait_idle()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://model-runtime"
            ) as client:
                token = {"Authorization": f"Bearer {IDENTITY.machine_token()}"}
                response = await client.post("/v1/responses/stream", json=body, headers=token)
    return response, chat, digest


def build(w: World, tmp: Path, chat: ScriptedChat, limit: float | None) -> FastAPI:
    settings = settings_for(tmp, w.pki, w.registry_url, model_cache_dir=tmp / "cache-stream")
    return make_app(settings, w.pki, IDENTITY, w.engine, chat=chat, respond_limit_seconds=limit)


def events(text: str) -> list[dict[str, Any]]:
    """SSE 본문을 이벤트로 읽는다. event 줄이 data.event 와 같고 data 가 계약을 지키는지 함께 본다."""
    found: list[dict[str, Any]] = []
    for block in text.split("\n\n")[:-1]:
        name, data = block.split("\n")
        assert name.startswith("event: ") and data.startswith("data: ")
        parsed = json.loads(data.removeprefix("data: "))
        assert name.removeprefix("event: ") == parsed["event"]
        ResponseStreamEvent.model_validate(parsed)
        found.append(parsed)
    assert text.endswith("\n\n")
    return found


async def test_deltas_are_sent_unchanged_in_order_then_result_equals_their_concatenation(tmp_path: Path) -> None:
    pieces = ["진단 ", "받으셨", "군요.\n", " 다음 질문입니다. "]
    response, chat, digest = await run(tmp_path, pieces)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store, no-transform"
    assert "content-encoding" not in response.headers
    got = events(response.text)
    assert [e["text"] for e in got[:-1]] == pieces  # 공백과 줄바꿈도 바꾸지 않는다
    assert got[-1] == {"event": "result", "result": {"package_digest": digest, "text": "".join(pieces)}}
    assert len(chat.requests) == 1


async def test_the_fragment_that_would_pass_344_characters_is_not_sent(tmp_path: Path) -> None:
    response, _, _ = await run(tmp_path, ["가" * 300, "나" * 44, "다"])
    got = events(response.text)
    assert [e["event"] for e in got] == ["delta", "delta", "error"]  # 정확히 344자까지는 보낸다
    assert got[-1]["problem"]["status"] == 503 and got[-1]["problem"]["reason"] == "OUTPUT_INVALID"
    assert got[-1]["retry_after_seconds"] == 5


@pytest.mark.parametrize("script", [[], [""], ["", ""]])
async def test_empty_sentence_is_output_invalid(tmp_path: Path, script: list[str]) -> None:
    response, _, _ = await run(tmp_path, script)
    got = events(response.text)
    assert [e["event"] for e in got] == ["error"] and got[0]["problem"]["reason"] == "OUTPUT_INVALID"


async def test_engine_failure_after_deltas_ends_with_the_503_the_json_path_gives(tmp_path: Path) -> None:
    response, _, _ = await run(tmp_path, ["진단 ", EngineError("http://engine secret")])
    got = events(response.text)
    assert [e["event"] for e in got] == ["delta", "error"]
    assert got[-1]["problem"]["status"] == 503 and "secret" not in response.text
    assert got[-1]["problem"]["title"] == "추론 엔진이 요청을 처리하지 못했다" and got[-1]["retry_after_seconds"] == 5


async def test_time_limit_covers_the_stream_until_the_last_event(tmp_path: Path) -> None:
    response, _, _ = await run(tmp_path, ["진단 ", NEVER], limit=0)
    got = events(response.text)
    assert got[-1]["event"] == "error" and got[-1]["problem"]["reason"] == "DEADLINE_EXCEEDED"
    assert got[-1]["problem"]["status"] == 503 and got[-1]["retry_after_seconds"] == 5


async def test_rejections_before_the_stream_are_json_problems(tmp_path: Path) -> None:
    mismatch, chat, _ = await run(tmp_path, ["x"], body={**BODY, "runtime_contract_version": 2})
    assert mismatch.status_code == 409 and mismatch.headers["content-type"] == "application/problem+json"
    assert mismatch.json()["reason"] == "QUESTION_BANK_VERSION_MISMATCH" and chat.requests == []
    invalid, _, _ = await run(
        tmp_path / "b",
        ["x"],
        body={**BODY, "question_id": "Q99", "values": [{**B_REQUEST["values"][0], "key": "Q99.x"}]},
    )
    assert invalid.status_code == 400


async def test_not_loaded_is_503_json_before_the_stream(tmp_path: Path) -> None:
    with world(tmp_path) as w:
        app = build(w, tmp_path, ScriptedChat(["x"]), None)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://model-runtime") as client,
        ):
            token = {"Authorization": f"Bearer {IDENTITY.machine_token()}"}
            response = await client.post("/v1/responses/stream", json=BODY, headers=token)
            anonymous = await client.post("/v1/responses/stream", json=BODY)
    assert response.status_code == 503 and response.json()["reason"] == "MODEL_NOT_LOADED"
    assert response.headers["retry-after"] == "5" and anonymous.status_code == 401
