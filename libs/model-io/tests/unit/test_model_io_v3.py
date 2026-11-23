"""모델 입출력 v3(계약 9.4.0): 직렬화, 새 사유의 검증과 LoRA-B 입력, 값 없는 NEXT 의 다음 문항.

기대 값은 학습 서버 dataset1118 의 실제 행(scenario_id 를 주석에 적었다)에서 옮겼다. v2 의 동작이 바뀌지 않는지도 본다.
"""

import json

import pytest

from helpers import context, gap, value
from model_io import (
    check_extraction_output,
    compose_response_from_request,
    compose_response_input,
    select_state,
    serialize_extraction_input,
)

# dataset1118 A, c_Q9_1_P17_confirm_reply_F2_0001_v0 (v2 순서로 들어온 요청 값)
_A_INPUT = {
    "current_question": "아까는 일주일에 6일이라고 하셨는데요, 2일이 맞을까요?",
    "question_id": "Q9_1",
    "state": {"Q9_1.days": {"value": 6, "status": "ANSWERED"}},
    "user_utterance": "일주일에 6일이 맞아요, 요즘은 아침에 30분 정도 천천히 걷는 걸 매일 해요.",
}


def test_v3_serialization_sorts_every_level() -> None:
    text = serialize_extraction_input(_A_INPUT, ["Q9_1.days"], model_io_version="model-io-v3")
    assert text == json.dumps(_A_INPUT, ensure_ascii=False, sort_keys=True)
    assert '"Q9_1.days": {"status": "ANSWERED", "value": 6}' in text


def test_v2_serialization_is_unchanged() -> None:
    text = serialize_extraction_input(_A_INPUT, ["Q9_1.days"])
    assert '"Q9_1.days": {"value": 6, "status": "ANSWERED"}' in text
    assert text == serialize_extraction_input(_A_INPUT, ["Q9_1.days"], model_io_version="model-io-v2")


def test_unknown_model_io_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="모르는 모델 입출력 버전"):
        serialize_extraction_input(_A_INPUT, [], model_io_version="model-io-v9")


def test_valueless_next_skips_by_the_stored_value() -> None:
    """Q4 가 '아니요'로 저장된 상태에서 Q4 확인에 '맞다' -> 값 없는 NEXT.

    다음은 Q4_1 을 건너뛴 Q5 다(dataset1118 P17 41행).
    """
    state: dict[str, object] = {"Q4.answer": {"status": "ANSWERED", "value": False}}
    ok = check_extraction_output(
        json.dumps({"action": "NEXT", "next_item": "Q5", "values": []}), context("Q4", state, "model-io-v3")
    )
    assert ok.valid and not ok.violations
    wrong = check_extraction_output(
        json.dumps({"action": "NEXT", "next_item": "Q4_1", "values": []}), context("Q4", state, "model-io-v3")
    )
    assert "NEXT_ITEM_MISMATCH" in {v.code.value for v in wrong.violations}


def test_new_a_reasons_pass_and_limit_reached_is_rejected() -> None:
    keys = ["Q1.D03.diagnosed", "Q1.D03.on_medication"]
    reask: dict[str, object] = {
        "action": "REASK",
        "next_item": "Q1.D03",
        "reason": "UNCLEAR_TARGET",
        "targets": keys,
        "values": [gap(k) for k in keys],
    }
    assert check_extraction_output(json.dumps(reask), context("Q1.D03", None, "model-io-v3")).violations == ()
    for reason in ("ASK_MEANING", "ASK_HOW"):
        redirect: dict[str, object] = {"action": "REDIRECT", "next_item": "Q1.D03", "reason": reason, "values": []}
        assert check_extraction_output(json.dumps(redirect), context("Q1.D03", None, "model-io-v3")).violations == ()
    limit: dict[str, object] = {
        "action": "SKIP",
        "next_item": "Q1.D04",
        "reason": "LIMIT_REACHED",
        "targets": [],
        "values": [],
    }
    outcome = check_extraction_output(json.dumps(limit), context("Q1.D03", None, "model-io-v3"))
    assert not outcome.valid and "OUTPUT_SCHEMA" in {v.code.value for v in outcome.violations}


def test_unclear_target_asks_with_the_missing_phrase() -> None:
    """dataset1118 c_Q1.D03_P15_ack_short_X_0001_v0 의 A 입력·정답과 B 입력."""
    keys = ["Q1.D03.diagnosed", "Q1.D03.on_medication"]
    a_out: dict[str, object] = {
        "action": "REASK",
        "next_item": "Q1.D03",
        "reason": "UNCLEAR_TARGET",
        "targets": keys,
        "values": [gap(k) for k in keys],
    }
    state: dict[str, object] = {
        "Q1.D02.diagnosed": {"status": "ANSWERED", "value": True},
        "Q1.D02.on_medication": {"status": "ANSWERED", "value": False},
    }
    text = "다음은 고혈압입니다. 진단받은 적이 있으신지, 지금 약을 드시는지 알려 주세요."
    b = compose_response_input(a_out, "Q1.D03", "약 먹고 있어요", state, text)
    assert b == {
        "action": "REASK",
        "ask": "고혈압 진단을 받은 적이 있는지, 지금 고혈압 약을 먹는지",
        "known": "",
        "next": {"question_id": "Q1.D03", "text": text, "type": "SAME"},
        "reason": "UNCLEAR_TARGET",
        "topic": "고혈압 진단을 받았는지와 지금 약을 먹는지",
        "user_utterance": "약 먹고 있어요",
    }


def test_limit_reached_input_has_no_a_output() -> None:
    """dataset1118 c_Q7_1_P22_limit_skip_L_0001_v0_bonly(LoRA-B 전용)."""
    text = "가장 많이 드신 날을 떠올려 보시면, 무슨 술을 얼마나 드셨나요?"
    request: dict[str, object] = {
        "runtime_contract_version": 1,
        "action": "SKIP",
        "reason": "LIMIT_REACHED",
        "question_id": "Q7_1",
        "user_utterance": "있죠",
        "slots": [],
        "values": [],
        "next": {"type": "NEXT", "question_id": "Q7_2", "text": text},
    }
    assert compose_response_from_request(request) == {
        "action": "SKIP",
        "hold": "평소 마시는 양",
        "known": "",
        "next": {"question_id": "Q7_2", "text": text, "type": "NEXT"},
        "reason": "LIMIT_REACHED",
        "topic": "술 마시는 날 평소에 마시는 양",
        "user_utterance": "있죠",
    }


def test_ask_back_redirect_carries_the_confirm_it_interrupts() -> None:
    """설명 요청 REDIRECT 는 직전 확인의 ask·previous·current 를 이어 받는다(fix3.md 1장).

    확인 요청은 dataset1118 c_Q1.D04_P06_conflict_0061_v1 의 A 입력·정답이고, 이어 받은 값은
    c_Q1.D04_P17_confirm_reply_F5_0001_v0 의 B 입력에 있는 값이다.
    """
    text = "당뇨병은 어떠세요? 진단을 받으셨거나 약을 복용 중이신가요?"
    same: dict[str, object] = {"type": "SAME", "question_id": "Q1.D04", "text": text}
    slots: list[dict[str, object]] = [
        {"key": "Q1.D04.diagnosed", "value": False, "status": "ANSWERED"},
        {"key": "Q1.D04.on_medication", "value": False, "status": "ANSWERED"},
    ]
    source: dict[str, object] = {
        "action": "CONFIRM",
        "reason": "CONFLICT_WITH_PREVIOUS",
        "question_id": "Q1.D05",
        "previous_question_id": "Q1.D04",
        "user_utterance": "지금당뇨병약은먹고있어요",
        "slots": slots,
        "values": [value("Q1.D04.on_medication", True, status="CONFLICT", save=False)],
        "targets": ["Q1.D04.on_medication"],
        "next": same,
    }
    request: dict[str, object] = {
        "runtime_contract_version": 1,
        "action": "REDIRECT",
        "reason": "ASK_MEANING",
        "question_id": "Q1.D04",
        "user_utterance": "뭐라고요?",
        "slots": slots,
        "values": [],
        "next": same,
    }
    plain = compose_response_from_request(request)
    assert "ask" not in plain and "previous" not in plain
    carried = compose_response_from_request({**request, "ask_back_source": source})
    assert carried["ask"] == "이번에 말한 값(current)이 맞는지, 아까 말한 값(previous)이 맞는지"
    assert (carried["previous"], carried["current"]) == ("지금 약 안 먹음", "지금 약 먹음")
    assert {k: v for k, v in carried.items() if k not in ("ask", "previous", "current")} == plain


def test_other_redirects_ignore_an_ask_back_source() -> None:
    """OFF_TOPIC·ASK_PURPOSE 는 이어 받지 않는다(계약이 막지만 받아도 쓰지 않는다)."""
    same: dict[str, object] = {"type": "SAME", "question_id": "Q1.D04", "text": "당뇨병은 어떠세요?"}
    keys = ["Q1.D04.diagnosed", "Q1.D04.on_medication"]
    source: dict[str, object] = {
        "action": "REASK",
        "reason": "UNCLEAR_TARGET",
        "question_id": "Q1.D04",
        "user_utterance": "네",
        "slots": [],
        "values": [gap(k) for k in keys],
        "targets": keys,
        "next": same,
    }
    request: dict[str, object] = {
        "runtime_contract_version": 1,
        "action": "REDIRECT",
        "reason": "OFF_TOPIC",
        "question_id": "Q1.D04",
        "user_utterance": "날씨 좋네요",
        "slots": [],
        "values": [],
        "next": same,
        "ask_back_source": source,
    }
    assert "ask" not in compose_response_from_request(request)


def test_v2_package_rejects_v3_reasons() -> None:
    """v2 어댑터는 새 사유를 학습하지 않았다. 내면 출력 불가다(계약 ActionReason 9.4.0)."""
    redirect: dict[str, object] = {"action": "REDIRECT", "next_item": "Q1.D03", "reason": "ASK_HOW", "values": []}
    outcome = check_extraction_output(json.dumps(redirect), context("Q1.D03"))
    assert not outcome.valid


def test_v3_reason_shapes_are_enforced() -> None:
    """독립 검토(2026-11-23) 4번: 설명 요청에 저장, 설명 요청을 REASK 로, 대상 모호인데 한 칸만 다시 묻기.

    셋 다 출력 불가다.
    """
    keys = ["Q1.D01.diagnosed", "Q1.D01.on_medication"]
    cases: list[dict[str, object]] = [
        {"action": "REDIRECT", "next_item": "Q1.D01", "reason": "ASK_HOW", "values": [value(keys[0], True)]},
        {"action": "REASK", "next_item": "Q1.D01", "reason": "ASK_HOW", "targets": keys[:1], "values": [gap(keys[0])]},
        {
            "action": "REASK",
            "next_item": "Q1.D01",
            "reason": "UNCLEAR_TARGET",
            "targets": keys[:1],
            "values": [gap(keys[0])],
        },
    ]
    for case in cases:
        outcome = check_extraction_output(json.dumps(case), context("Q1.D01", None, "model-io-v3"))
        assert not outcome.valid, case


def test_state_after_a_confirm_screen_has_only_the_confirmed_item() -> None:
    """확인 질문 다음 턴의 state 는 확인하는 문항의 값만이다(dataset1118 confirm_state, P17 4,050/4,050행)."""
    slots: list[dict[str, object]] = [
        {"key": "Q1.D03.diagnosed", "value": True, "status": "ANSWERED"},
        {"key": "Q1.D04.diagnosed", "value": False, "status": "ANSWERED"},
        {"key": "Q1.D04.on_medication", "value": False, "status": "ANSWERED"},
        {"key": "Q1.D05.diagnosed", "value": True, "status": "ANSWERED"},
    ]
    assert list(select_state(slots, "Q1.D04", "Q1.D05", previous_screen_action="CONFIRM")) == [
        "Q1.D04.diagnosed",
        "Q1.D04.on_medication",
    ]
    assert "Q1.D05.diagnosed" in select_state(slots, "Q1.D04", "Q1.D05")
