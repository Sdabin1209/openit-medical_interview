"""prompt: 추출·응답 요청에서 모델 입력 글자를 만든다. 학습 데이터의 user 메시지와 글자(바이트)까지 같다(D77).

입력은 요청 값과 적재한 어댑터(시스템 프롬프트, 서빙 설정), 출력은 추론 엔진에 보낼 채팅 요청이다.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

from model_io import serialize_extraction_input, serialize_response_input

from model_runtime.contract.models import ActionExtraction
from model_runtime.types import ChatRequest, ExtractionTurn, LoadedAdapter


@cache
def _extraction_output_schema() -> Mapping[str, object]:
    """제약 디코딩이 따를 출력 JSON Schema. 계약 ActionExtraction 에서 생성한 모델이 만든다(복사본을 두지 않는다)."""
    return ActionExtraction.model_json_schema()


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
