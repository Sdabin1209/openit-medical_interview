"""inference: 엔진 호출 결과와 시간 상한·실패를 계약의 503 으로 바꾼다."""

import pytest

from model_runtime.components.inference import call_engine
from model_runtime.contract.models import ProblemReason
from model_runtime.types import ChatRequest, EngineError, ServiceFault

pytestmark = pytest.mark.anyio
REQUEST = ChatRequest("a", "s", "u", 10, 0.0)


class Engine:
    def __init__(self, result: str | BaseException) -> None:
        self.result = result

    async def complete(self, request: ChatRequest) -> str:
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


async def test_returns_text_and_elapsed_seconds() -> None:
    text, seconds = await call_engine(Engine("답"), REQUEST, 20)
    assert text == "답" and seconds >= 0


async def test_timeout_is_503_deadline_exceeded_with_retry_after() -> None:
    with pytest.raises(ServiceFault) as info:
        await call_engine(Engine(TimeoutError()), REQUEST, 20)
    assert (info.value.status, info.value.reason) == (503, ProblemReason.DEADLINE_EXCEEDED) and info.value.retry_after


async def test_engine_failure_is_503_without_leaking_the_cause() -> None:
    with pytest.raises(ServiceFault) as info:
        await call_engine(Engine(EngineError("http://inference-engine:8000 secret")), REQUEST, 20)
    assert info.value.status == 503 and "secret" not in info.value.detail and info.value.reason is None
