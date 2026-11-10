"""prompt: 모델 입력 글자는 학습 데이터와 같은 직렬화이고 시스템 프롬프트와 서빙 설정은 어댑터의 것이다."""

from typing import Any

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
