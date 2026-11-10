"""LoRA-A 입력 만들기: state 에 넣을 문항(지금, 직전, 참조 원천)과 묶음 순서, 다시 묻는 칸."""

from model_io import compose_extraction_input, reference_item, serialize_extraction_input


def slot(key: str, value: object, status: str = "ANSWERED") -> dict[str, object]:
    return {"key": key, "value": value, "status": status}


SLOTS = [
    slot("Q1.D01.diagnosed", True),  # 지금·직전·참조 원천 어디도 아니다
    slot("Q8_1.days", 3),
    slot("Q8_2.duration_minutes", 30),
    slot("Q9_1.days", 2),
    slot("Q9_2.duration_minutes", None, "MISSING"),
]


def test_reference_source_comes_from_the_canonical_table() -> None:
    assert reference_item("Q10") == "Q9_1" and reference_item("Q9_2") == "Q8_2" and reference_item("Q1.D01") is None


def test_state_has_only_current_previous_and_reference_items() -> None:
    payload, order = compose_extraction_input("Q9_2", "하루에 몇 분이요?", "삼십 분이요", SLOTS, "Q9_1")
    assert order == ["Q9_1.days", "Q8_2.duration_minutes", "Q9_2.duration_minutes"]
    assert payload["state"]["Q9_2.duration_minutes"] == {"value": None, "status": "MISSING"}
    assert "Q1.D01.diagnosed" not in payload["state"] and "Q8_1.days" not in payload["state"]


def test_answered_values_of_current_previous_reference_then_pending() -> None:
    slots = [
        slot("Q9_2.duration_minutes", None, "UNCLEAR"),
        slot("Q8_2.duration_minutes", 30),
        slot("Q9_1.days", 2),
        slot("Q9_2.x", 1),
    ]
    _, order = compose_extraction_input("Q9_2", "q", "u", slots, "Q9_1")
    assert order == ["Q9_2.x", "Q9_1.days", "Q8_2.duration_minutes", "Q9_2.duration_minutes"]


def test_first_item_has_empty_state_and_serializes_like_training_text() -> None:
    payload, order = compose_extraction_input("Q1.D01", "뇌졸중 진단을 받으셨나요?", "네", [], None)
    assert serialize_extraction_input(payload, order) == (
        '{"current_question": "뇌졸중 진단을 받으셨나요?", "question_id": "Q1.D01", '
        '"state": {}, "user_utterance": "네"}'
    )


def test_a_slot_that_appears_again_keeps_its_first_place_and_last_value() -> None:
    slots = [slot("Q9_1.days", 2), slot("Q9_2.a", 1), slot("Q9_1.days", 5)]
    payload, order = compose_extraction_input("Q9_2", "q", "u", slots, "Q9_1")
    assert order == ["Q9_2.a", "Q9_1.days"] and payload["state"]["Q9_1.days"]["value"] == 5
