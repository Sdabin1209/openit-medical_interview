"""link/engine: OpenAI 호환 API(openai SDK)로 채팅 완성을 부르고 어댑터를 올리고 내린다."""

from pathlib import Path

import httpx2 as httpx
import pytest

from fakes.engine import FakeEngine
from model_runtime.link.engine import VllmEngine
from model_runtime.types import ChatRequest, EngineError
from support import BASE_MODEL, adapter_folder

pytestmark = pytest.mark.anyio


def client(fake: FakeEngine) -> VllmEngine:
    return VllmEngine(
        "http://engine",
        BASE_MODEL,
        httpx.AsyncClient(transport=httpx.ASGITransport(app=fake.app()), base_url="http://engine"),
    )


async def test_load_complete_unload(tmp_path: Path) -> None:
    fake = FakeEngine(answer=lambda adapter, user: f"{adapter}:{user}")
    engine = client(fake)
    folder = adapter_folder(tmp_path, "a")
    await engine.load_adapter("lora_a-1", folder)
    assert fake.loaded == {"lora_a-1": str(folder)}
    text = await engine.complete(ChatRequest("lora_a-1", "시스템", "사용자 글자", 100, 0.3))
    assert text == "lora_a-1:사용자 글자"
    call = fake.calls[0]
    assert (call.system, call.user, call.max_tokens, call.temperature, call.response_format) == (
        "시스템",
        "사용자 글자",
        100,
        0.3,
        None,
    )
    await engine.unload_adapter("lora_a-1")
    assert fake.loaded == {}
    await engine.unload_adapter("lora_a-1")  # 없는 이름은 무시한다


async def test_constrained_decoding_sends_json_schema() -> None:
    fake = FakeEngine(answer=lambda _a, _u: "{}")
    engine = client(fake)
    fake.loaded["m"] = "/x"
    await engine.complete(ChatRequest("m", "s", "u", 10, 0.0, json_schema={"type": "object"}))
    assert fake.calls[0].response_format == {
        "type": "json_schema",
        "json_schema": {"name": "ActionExtraction", "schema": {"type": "object"}},
    }


async def test_unknown_model_and_empty_answers_are_engine_errors() -> None:
    fake = FakeEngine(answer=lambda _a, _u: "")
    engine = client(fake)
    with pytest.raises(EngineError):
        await engine.complete(ChatRequest("nope", "s", "u", 10, 0.0))
    fake.loaded["m"] = "/x"
    with pytest.raises(EngineError):
        await engine.complete(ChatRequest("m", "s", "u", 10, 0.0))  # 빈 답


async def test_refused_adapter_and_health(tmp_path: Path) -> None:
    fake = FakeEngine(refuse_load=True)
    engine = client(fake)
    with pytest.raises(EngineError):
        await engine.load_adapter("x", adapter_folder(tmp_path, "a"))
    assert await engine.healthy()
    fake.healthy = False
    assert not await engine.healthy()


async def test_unreachable_engine_is_engine_error() -> None:
    async def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    engine = VllmEngine("http://engine", BASE_MODEL, httpx.AsyncClient(transport=httpx.MockTransport(down)))
    with pytest.raises(EngineError):
        await engine.complete(ChatRequest("m", "s", "u", 10, 0.0))
    with pytest.raises(EngineError):
        await engine.load_adapter("m", Path("/x"))
    assert not await engine.healthy()
    await engine.unload_adapter("m")  # 정리 단계는 실패해도 멈추지 않는다


async def test_ready_only_when_the_engine_serves_the_profile_base_model() -> None:
    fake = FakeEngine()
    assert await client(fake).healthy()
    fake.base_model = "Qwen/Qwen3-1.7B"  # 엔진이 프로파일과 다른 기반 모델로 떠 있다
    assert not await client(fake).healthy()
