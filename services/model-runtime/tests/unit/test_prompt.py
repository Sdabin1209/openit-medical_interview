"""prompt: 모델 입력 글자는 학습 데이터와 같은 직렬화이고 시스템 프롬프트와 서빙 설정은 어댑터의 것이다."""

from typing import Any

import pytest
from model_io import serialize_extraction_input, serialize_response_input

from model_runtime.components.prompt import extraction_request, response_request
from model_runtime.contract.models import ServingConfig
from model_runtime.types import ExtractionTurn, LoadedAdapter


def adapter(constrained: bool = False) -> LoadedAdapter:
    serving = ServingConfig.model_validate(
        {"max_new_tokens": 600, "temperature": 0.2, "constrained_decoding": constrained}
    )
    return LoadedAdapter("lora_a-abc", "시스템 프롬프트", serving)


PAYLOAD: dict[str, Any] = {
    "question_id": "Q9_2",
    "current_question": "하루에 몇 분 하세요?",
    "user_utterance": "열여섯 분 해요",
    "state": {
        "Q9_2.duration_minutes": {"value": 15, "status": "ANSWERED"},
        "Q9_1.days": {"value": 3.0, "status": "ANSWERED"},
    },
}


def test_extraction_request_text_is_the_training_serialization() -> None:
    request = extraction_request(ExtractionTurn(PAYLOAD, ["Q9_2.duration_minutes", "Q9_1.days"]), adapter())
    assert request.user == serialize_extraction_input(PAYLOAD, ["Q9_2.duration_minutes", "Q9_1.days"])
    assert '"value": 15, "status"' in request.user and '"value": 3, "status"' in request.user  # 3.0 이 아니라 3
    assert (request.adapter, request.system, request.max_new_tokens, request.temperature) == (
        "lora_a-abc",
        "시스템 프롬프트",
        600,
        0.2,
    )
    assert request.json_schema is None


def test_constrained_decoding_sends_the_contract_output_schema() -> None:
    request = extraction_request(ExtractionTurn(PAYLOAD, []), adapter(constrained=True))
    assert request.json_schema is not None
    assert {"action", "next_item", "values"} <= set(request.json_schema["required"])  # type: ignore[arg-type]


def test_response_request_sorts_every_level() -> None:
    payload = {"topic": "t", "next": {"type": "NEXT", "text": "다음", "question_id": "Q2"}, "action": "NEXT"}
    request = response_request(payload, adapter())
    assert request.user == serialize_response_input(payload) and request.json_schema is None


def test_extraction_input_selects_state_from_stored_slots() -> None:
    from model_runtime.components.prompt import extraction_input
    from model_runtime.types import ExtractionQuestion

    slots: list[dict[str, Any]] = [
        {"key": "Q1.D01.diagnosed", "value": True, "status": "ANSWERED"},
        {"key": "Q9_1.days", "value": 3, "status": "ANSWERED"},
        {"key": "Q8_2.duration_minutes", "value": 30, "status": "ANSWERED"},
        {"key": "Q9_2.duration_minutes", "value": None, "status": "MISSING"},
    ]
    turn = extraction_input(ExtractionQuestion("Q9_2", "Q9_1", "하루에 몇 분이요?", "삼십 분이요", slots))
    assert turn.state_key_order == ["Q9_1.days", "Q8_2.duration_minutes", "Q9_2.duration_minutes"]
    assert set(turn.input) == {"question_id", "current_question", "user_utterance", "state"}


def test_response_input_is_built_from_structured_values_and_bad_items_are_400() -> None:
    from model_runtime.components.prompt import response_input
    from model_runtime.types import ServiceFault

    request: dict[str, Any] = {
        "action": "NEXT",
        "question_id": "Q4",
        "user_utterance": "안 피웠어요",
        "slots": [],
        "values": [{"key": "Q4.answer", "value": False, "precision": "exact", "status": "ANSWERED", "save": True}],
        "next": {"type": "NEXT", "question_id": "Q5", "text": "가열담배를 써 보셨나요?"},
    }
    assert response_input(request)["known"] == "피운 적 없음"
    with pytest.raises(ServiceFault) as info:
        response_input({**request, "question_id": "Q99", "values": [{**request["values"][0], "key": "Q99.x"}]})
    assert info.value.status == 400
