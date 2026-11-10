"""모델 입력 직렬화: 학습 데이터 user 메시지와 글자가 같다(D77)."""

import json

from model_io import serialize_extraction_input, serialize_response_input


def test_extraction_input_sorts_top_level_and_keeps_state_order() -> None:
    payload = {
        "user_utterance": "네 오년 전에요",
        "question_id": "Q1.D03",
        "current_question": "고혈압은요?",
        "state": {
            "Q1.D02.diagnosed": {"status": "ANSWERED", "value": False},
            "Q1.D01.diagnosed": {"status": "ANSWERED", "value": True},
        },
    }
    text = serialize_extraction_input(payload, ["Q1.D02.diagnosed", "Q1.D01.diagnosed"])
    assert text == (
        '{"current_question": "고혈압은요?", "question_id": "Q1.D03", "state": {"Q1.D02.diagnosed": {"value": false, '
        '"status": "ANSWERED"}, "Q1.D01.diagnosed": {"value": true, "status": "ANSWERED"}}, '
        '"user_utterance": "네 오년 전에요"}'
    )


def test_state_key_order_changes_the_text() -> None:
    state = {"A.x": {"value": 1, "status": "ANSWERED"}, "B.y": {"value": 2, "status": "ANSWERED"}}
    payload = {"question_id": "Q1", "current_question": "q", "user_utterance": "u", "state": state}
    assert serialize_extraction_input(payload, ["A.x", "B.y"]) != serialize_extraction_input(payload, ["B.y", "A.x"])


def test_integer_valued_float_is_written_as_integer() -> None:
    state = {
        "Q8_1.days": {"value": 3.0, "status": "ANSWERED"},
        "Q4_1.years_since_quit": {"value": 0.5, "status": "ANSWERED"},
    }
    payload = {"question_id": "Q1", "current_question": "q", "user_utterance": "u", "state": state}
    text = serialize_extraction_input(payload, list(state))
    assert '"value": 3,' in text and '"value": 0.5,' in text


def test_non_ascii_is_not_escaped_and_empty_state_is_braces() -> None:
    payload: dict[str, object] = {"question_id": "Q1", "current_question": "안녕", "user_utterance": "네", "state": {}}
    text = serialize_extraction_input(payload, [])
    assert "안녕" in text and '"state": {}' in text and "\\u" not in text


def test_keys_missing_from_the_order_follow_sorted() -> None:
    state = {"B.y": {"value": 1, "status": "ANSWERED"}, "A.x": {"value": 2, "status": "ANSWERED"}}
    payload = {"question_id": "Q1", "current_question": "q", "user_utterance": "u", "state": state}
    assert list(json.loads(serialize_extraction_input(payload, []))["state"]) == ["A.x", "B.y"]


def test_response_input_sorts_every_level() -> None:
    payload = {"topic": "t", "next": {"type": "NEXT", "text": "다음", "question_id": "Q2"}, "action": "NEXT"}
    assert serialize_response_input(payload) == (
        '{"action": "NEXT", "next": {"question_id": "Q2", "text": "다음", "type": "NEXT"}, "topic": "t"}'
    )
