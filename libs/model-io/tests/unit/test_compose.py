"""구조화된 값 → LoRA-B 입력의 글 조각. 기대 글자는 데이터셋 정본(labels.py)의 표와 문장 틀이 만든 학습 파일의
글자다."""

from helpers import gap, value
from model_io import compose_response_input, compose_start_input, serialize_response_input


def test_start_input_is_the_first_item_topic_and_question() -> None:
    assert compose_start_input("뇌졸중 진단을 받으셨나요?") == {
        "action": "START",
        "topic": "뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지",
        "next": {"type": "NEXT", "question_id": "Q1.D01", "text": "뇌졸중 진단을 받으셨나요?"},
    }


def test_reask_names_what_is_known_and_what_to_ask() -> None:
    output = {
        "action": "REASK",
        "next_item": "Q1.D01",
        "reason": "MISSING",
        "targets": ["Q1.D01.on_medication"],
        "values": [value("Q1.D01.diagnosed", True), gap("Q1.D01.on_medication")],
    }
    result = compose_response_input(output, "Q1.D01", "몇 년 전에 진단을 받았어요.", {}, "뇌졸중 약을 드시나요?")
    assert result == {
        "action": "REASK",
        "reason": "MISSING",
        "topic": "뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지",
        "user_utterance": "몇 년 전에 진단을 받았어요.",
        "known": "진단 받음",
        "ask": "지금 뇌졸중(중풍) 약을 먹는지",
        "next": {"type": "SAME", "question_id": "Q1.D01", "text": "뇌졸중 약을 드시나요?"},
    }


def test_confirm_has_previous_and_current_and_empty_known() -> None:
    state = {"Q9_2.duration_minutes": {"value": 15, "status": "ANSWERED"}}
    output = {
        "action": "CONFIRM",
        "next_item": "Q9_2",
        "reason": "CONFLICT_WITH_PREVIOUS",
        "targets": ["Q9_2.duration_minutes"],
        "values": [value("Q9_2.duration_minutes", 16, status="CONFLICT", save=False)],
    }
    result = compose_response_input(output, "Q9_2", "열여섯 분 해요", state, "하루에 몇 분 하세요?")
    assert (result["known"], result["previous"], result["current"]) == ("", "하루 15분", "하루 16분")
    assert result["ask"] == "이번에 말한 값(current)이 맞는지, 아까 말한 값(previous)이 맞는지"


def test_end_has_no_question_and_skip_has_hold() -> None:
    output = {
        "action": "SKIP",
        "next_item": "END",
        "reason": "REFUSED",
        "targets": ["Q10.days"],
        "values": [gap("Q10.days", "REJECTED")],
    }
    result = compose_response_input(output, "Q10", "말하기 싫어요", {}, None)
    assert result["next"] == {"type": "END"} and result["hold"] == "근력 운동 한 날 수" and result["known"] == ""


def test_composed_input_serializes_with_every_level_sorted() -> None:
    output = {"action": "NEXT", "next_item": "Q5", "values": [value("Q4.answer", False)]}
    result = compose_response_input(output, "Q4", "안 피웠어요", {}, "가열담배를 써 보셨나요?")
    text = serialize_response_input(result)
    assert text.startswith('{"action": "NEXT", "known": "피운 적 없음"') and text.index('"question_id"') < text.index(
        '"text"'
    )


def test_items_outside_the_dataset_tables_are_a_compose_error_not_a_crash() -> None:
    import pytest

    from model_io import ModelInputError, compose_response_from_request

    unknown_item = {
        "action": "NEXT",
        "question_id": "Q99",
        "user_utterance": "u",
        "slots": [],
        "values": [value("Q99.x", 1)],
        "next": {"type": "END"},
    }
    with pytest.raises(ModelInputError):
        compose_response_from_request(unknown_item)
    with pytest.raises(ModelInputError):
        compose_response_from_request({"action": "START", "next": {"type": "NEXT", "question_id": "0", "text": "t"}})
