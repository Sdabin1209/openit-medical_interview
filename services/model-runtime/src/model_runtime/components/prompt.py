"""prompt: 추출·응답 요청에서 모델 입력 글자를 만든다. 학습 데이터의 user 메시지와 글자(바이트)까지 같다(D77).

입력은 요청 값과 적재한 어댑터(시스템 프롬프트, 서빙 설정), 출력은 추론 엔진에 보낼 채팅 요청이다.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

from model_io import (
    ModelInputError,
    compose_extraction_input,
    compose_response_from_request,
    serialize_extraction_input,
    serialize_response_input,
)

from model_runtime.contract.models import ActionExtraction
from model_runtime.types import ChatRequest, ExtractionQuestion, ExtractionTurn, LoadedAdapter, ServiceFault


@cache
def _extraction_output_schema() -> Mapping[str, object]:
    """제약 디코딩이 따를 출력 JSON Schema. 계약 ActionExtraction 에서 생성한 모델이 만든다(복사본을 두지 않는다)."""
    return ActionExtraction.model_json_schema()


def extraction_input(question: ExtractionQuestion) -> ExtractionTurn:
    """추출 요청의 구조화된 값에서 모델 입력 객체를 만든다(state 에 넣을 문항의 선택과 묶음 순서 포함, 데이터셋
    정본의 규칙)."""
    payload, order = compose_extraction_input(
        question.question_id,
        question.current_question,
        question.user_utterance,
        question.slots,
        question.previous_question_id,
    )
    return ExtractionTurn(payload, order)


def response_input(request: Mapping[str, object]) -> dict[str, object]:
    """응답 생성 요청의 구조화된 값에서 LoRA-B 모델 입력 객체를 만든다(topic, known, ask, previous, current, hold
    포함)."""
    try:
        return compose_response_from_request(request)
    except ModelInputError as error:
        raise ServiceFault(400, "요청이 계약을 어겼다", "문항·칸·값이 모델 입출력 v2 의 표에 없다") from error


def extraction_request(turn: ExtractionTurn, adapter: LoadedAdapter) -> ChatRequest:
    """LoRA-A 요청. 제약 디코딩은 어댑터의 서빙 설정이 켠 경우에만 출력 스키마를 싣는다."""
    return ChatRequest(
        adapter=adapter.name,
        system=adapter.system_prompt,
        user=serialize_extraction_input(turn.input, turn.state_key_order),
        max_new_tokens=adapter.serving.max_new_tokens.root,
        temperature=adapter.serving.temperature.root,
        json_schema=_extraction_output_schema() if adapter.serving.constrained_decoding.root else None,
    )


def response_request(payload: Mapping[str, object], adapter: LoadedAdapter) -> ChatRequest:
    """LoRA-B 요청. 출력은 응답 문장 그대로의 글자라 제약 디코딩이 없다(IO_SPEC.md 4.2)."""
    return ChatRequest(
        adapter=adapter.name,
        system=adapter.system_prompt,
        user=serialize_response_input(payload),
        max_new_tokens=adapter.serving.max_new_tokens.root,
        temperature=adapter.serving.temperature.root,
    )
