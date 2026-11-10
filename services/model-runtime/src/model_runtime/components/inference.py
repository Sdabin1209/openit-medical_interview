"""inference: 추론 엔진(vLLM 의 OpenAI 호환 서버)을 부르고 시간 상한을 지킨다.

입력은 모델 입력(채팅 요청), 출력은 모델이 낸 글자와 걸린 시간이다. 엔진과의 통신은 포트(ChatEngine)가 맡는다.
"""

from __future__ import annotations

import asyncio
import time

from model_runtime.contract.models import ProblemReason
from model_runtime.types import ChatEngine, ChatRequest, EngineError, ServiceFault

# 왜 5: 계약 RetryAfterSeconds 의 예시 값이다. 측정으로 정한 값이 아니다(ADR 0003)
RETRY_AFTER_SECONDS = 5


async def call_engine(engine: ChatEngine, request: ChatRequest, limit_seconds: int) -> tuple[str, float]:
    """엔진을 한 번 부른다. 상한(계약 D125: 추출 20초, 응답 25초)을 넘기거나 엔진이 실패하면 503 이다."""
    started = time.monotonic()
    try:
        async with asyncio.timeout(limit_seconds):
            text = await engine.complete(request)
    except TimeoutError as error:
        raise ServiceFault(
            503,
            "모델 호출이 시간 상한을 넘었다",
            f"추론 엔진이 {limit_seconds}초 안에 답하지 못했다",
            reason=_deadline(),
            retry_after=RETRY_AFTER_SECONDS,
        ) from error
    except EngineError as error:
        raise ServiceFault(
            503, "추론 엔진이 요청을 처리하지 못했다", "추론 엔진 호출이 실패했다", retry_after=RETRY_AFTER_SECONDS
        ) from error
    return text, time.monotonic() - started


def _deadline() -> ProblemReason:
    return ProblemReason.DEADLINE_EXCEEDED
