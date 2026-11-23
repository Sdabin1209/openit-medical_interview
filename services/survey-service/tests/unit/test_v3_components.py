"""모델 입출력 v3(계약 9.4.0) 컴포넌트 시험: 확인의 다음 자리, 직전 화면의 절차, 설명 요청의 이어 받기·연속 수,
되묻기 한도의 세는 범위, 한도 문장 요청. 저장·HTTP 없이 입력과 출력만 본다."""

from typing import Any

from tests.support.harness import extraction, value
from tests.unit.test_components import CONTENT, NOW, apply, make_session

from survey_service.components import session, turn
from survey_service.contract.models import (
    ActionExtraction,
    AskBackSource,
    ModelIoFeature,
    ModelIoVersion,
    ResponseAction,
)
from survey_service.types import AnswerRecord, SessionRecord, StaffHelpText, model_io_features

Q1_TEXT = "뇌졸중으로 진단받으셨거나 약을 드시나요?"
Q2_TEXT = "술을 드시나요?"
REASK = extraction(
    "REASK", "Q1", [value("Q1.diagnosed", None, "MISSING", "unspecified")], reason="MISSING", targets=["Q1.diagnosed"]
)
UNCLEAR = extraction(
    "REASK",
    "Q1",
    [value("Q1.diagnosed", None, "MISSING", "unspecified"), value("Q1.on_medication", None, "MISSING", "unspecified")],
    reason="UNCLEAR_TARGET",
    targets=["Q1.diagnosed", "Q1.on_medication"],
)
ASK_MEANING = extraction("REDIRECT", "Q1", [], reason="ASK_MEANING")
ASK_HOW = extraction("REDIRECT", "Q1", [], reason="ASK_HOW")
OFF_TOPIC = extraction("REDIRECT", "Q1", [], reason="OFF_TOPIC")
ANSWERED_Q1 = {"Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=True, precision="exact", status="ANSWERED")}
# Q2 를 묻는 중에 환자가 Q1 의 값을 뒤집어 A 가 Q1 을 확인한다(next_item 이 앞 문항)
CONFIRM_Q1_FROM_Q2 = extraction(
    "CONFIRM",
    "Q1",
    [value("Q1.diagnosed", False, "CONFLICT")],
    reason="CONFLICT_WITH_PREVIOUS",
    targets=["Q1.diagnosed"],
)


def request_for(current: SessionRecord, body: dict[str, Any], *, utterance: str = "말") -> dict[str, Any]:
    extracted = ActionExtraction.model_validate(body)
    transition = session.apply_extraction(current, extracted, skip_target="Q2", reask_limit=2, now=NOW)
    built = turn.response_request(
        session=current, content=CONTENT, extraction=extracted, transition=transition, utterance=utterance
    )
    return built.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------- 1. 확인의 다음 자리


def test_confirm_of_an_earlier_item_asks_that_item_not_the_current_one() -> None:
    """정본 labels.py b_input 은 SAME 의 question_id·text 를 A 출력의 next_item 에서 만든다(v3 실측 2,754행)."""
    current = make_session(current_item_id="Q2", previous_item_id="Q1", answers=ANSWERED_Q1)
    body = request_for(current, CONFIRM_Q1_FROM_Q2)
    assert body["question_id"] == "Q2"  # 묻던 문항은 그대로
    assert body["next"] == {"type": "SAME", "question_id": "Q1", "text": Q1_TEXT}
    # REASK·REDIRECT 는 next_item 이 지금 문항이라 결과가 같다
    at_q1 = make_session()
    for same in (REASK, ASK_MEANING, OFF_TOPIC):
        assert request_for(at_q1, same)["next"] == {"type": "SAME", "question_id": "Q1", "text": Q1_TEXT}


# ---------------------------------------------------------------- 2. 직전 화면의 절차


def test_previous_screen_action_is_carried_and_follows_the_screen() -> None:
    first = make_session()
    assert first.screen_action is ResponseAction.START
    assert turn.extraction_request(first, CONTENT, "네").previous_screen_action is ResponseAction.START
    assert request_for(first, REASK)["previous_screen_action"] == "START"
    confirmed = apply(make_session(current_item_id="Q2", answers=ANSWERED_Q1), CONFIRM_Q1_FROM_Q2).session
    assert confirmed.screen_action is ResponseAction.CONFIRM and confirmed.current_item_id == "Q1"
    assert turn.extraction_request(confirmed, CONTENT, "네").previous_screen_action is ResponseAction.CONFIRM
    # 되묻기 한도로 서비스가 건너뛴 화면은 SKIP 이다(고정 문장이든 LIMIT_REACHED 문장이든)
    skipped = apply(make_session(reask_count=2), REASK)
    assert skipped.limit_skip and skipped.session.screen_action is ResponseAction.SKIP
    failed = session.skip_for_failure_limit(
        make_session(screen_action=ResponseAction.CONFIRM), skip_target="Q2", now=NOW
    )
    assert failed.session.screen_action is ResponseAction.SKIP
    # 0004 전의 세션(알 수 없음)은 싣지 않는다: model-runtime 이 v2 규칙으로 고른다
    unknown = make_session(screen_action=None)
    assert "previous_screen_action" not in turn.extraction_request(unknown, CONTENT, "네").model_dump(exclude_none=True)


# ---------------------------------------------------------------- 3. 설명 요청의 이어 받기


def test_ask_back_source_is_the_pre_apply_reask_request_and_chains_then_clears() -> None:
    current = make_session(answers=ANSWERED_Q1)
    reask_request = turn.response_request(
        session=current,
        content=CONTENT,
        extraction=ActionExtraction.model_validate(REASK),
        transition=apply(current, REASK),
        utterance="글쎄요",
    )
    source = turn.ask_back_source_after(reask_request)
    assert source is not None
    expected = {
        k: v
        for k, v in reask_request.model_dump(mode="json", exclude_none=True).items()
        if k in AskBackSource.model_fields
    }
    assert source.model_dump(mode="json", exclude_none=True) == expected
    assert expected["slots"] == [{"key": "Q1.diagnosed", "value": True, "status": "ANSWERED"}]  # 반영 전 값
    shown = apply(current, REASK).session.model_copy(update={"ask_back_source": source})
    # 설명 요청은 처음 원본을 그대로 싣고, 다음 화면에도 같은 원본이 남는다
    meaning = turn.response_request(
        session=shown, content=CONTENT, extraction=ActionExtraction.model_validate(ASK_MEANING),
        transition=apply(shown, ASK_MEANING), utterance="무슨 뜻이에요?",
    )  # fmt: skip
    assert meaning.ask_back_source == source and turn.ask_back_source_after(meaning) == source
    # 다른 절차의 화면으로 넘어가면 지운다(다른 REDIRECT, NEXT, 고정 문장)
    off = turn.response_request(
        session=shown, content=CONTENT, extraction=ActionExtraction.model_validate(OFF_TOPIC),
        transition=apply(shown, OFF_TOPIC), utterance="날씨가 좋네요",
    )  # fmt: skip
    assert off.ask_back_source is None and turn.ask_back_source_after(off) is None
    assert turn.ask_back_source_after(None) is None
    # 직전 화면이 되묻기·확인이 아니면(원본이 없으면) 싣지 않는다
    assert "ask_back_source" not in request_for(make_session(), ASK_MEANING)


def test_confirm_request_becomes_a_source_with_its_next() -> None:
    current = make_session(current_item_id="Q2", previous_item_id="Q1", answers=ANSWERED_Q1)
    extracted = ActionExtraction.model_validate(CONFIRM_Q1_FROM_Q2)
    built = turn.response_request(
        session=current, content=CONTENT, extraction=extracted, transition=apply(current, CONFIRM_Q1_FROM_Q2), utterance="아니요"
    )  # fmt: skip
    source = turn.ask_back_source_after(built)
    assert source is not None and source.action is not None and source.action.value == "CONFIRM"
    assert source.next.question_id is not None and source.next.question_id.root == "Q1"


# ---------------------------------------------------------------- 4. 설명 요청 연속 수와 되묻기 한도


def explain(current: SessionRecord, body: dict[str, Any], limit: int | None = 3):  # noqa: ANN201
    return session.apply_extraction(
        current,
        ActionExtraction.model_validate(body),
        skip_target="Q2",
        reask_limit=2,
        now=NOW,
        explain_streak_limit=limit,
    )


def test_explain_streak_counts_meaning_and_how_together_and_notices_on_the_third() -> None:
    current = make_session()
    one = explain(current, ASK_MEANING)
    two = explain(one.session, ASK_HOW)
    three = explain(two.session, ASK_MEANING)
    assert [t.session.explain_streak for t in (one, two, three)] == [1, 2, 3]
    assert [t.staff_help_notice for t in (one, two, three)] == [False, False, True]
    assert three.session.current_item_id == "Q1" and three.session.reask_count == 0
    # 기능이 꺼져 있으면(v2) 안내하지 않는다
    assert not explain(two.session, ASK_MEANING, limit=None).staff_help_notice


def test_explain_streak_breaks_on_other_action_or_item_change() -> None:
    two = explain(explain(make_session(), ASK_MEANING).session, ASK_HOW).session
    for other in (OFF_TOPIC, REASK, extraction("HOLD", "Q1", [], reason="UNCERTAIN", targets=["Q1.on_medication"])):
        broken = explain(two, other)
        assert broken.session.explain_streak == 0 and not broken.staff_help_notice
        assert explain(broken.session, ASK_MEANING).session.explain_streak == 1
    moved = explain(two, extraction("NEXT", "Q2", [value("Q1.diagnosed", True), value("Q1.on_medication", False)]))
    assert moved.session.explain_streak == 0 and moved.session.current_item_id == "Q2"


def test_explain_requests_are_not_counted_toward_reask_limit_but_unclear_target_is() -> None:
    current = apply(make_session(), REASK).session
    assert current.reask_count == 1
    for body in (ASK_MEANING, ASK_HOW, ASK_MEANING, ASK_HOW):
        current = apply(current, body).session
    assert current.reask_count == 1 and current.current_item_id == "Q1"
    current = apply(current, UNCLEAR).session
    assert current.reask_count == 2
    final = apply(current, UNCLEAR)
    assert final.limit_skip and final.session.current_item_id == "Q2"


# ---------------------------------------------------------------- 5. 되묻기 한도의 문장


def test_limit_reached_request_shape() -> None:
    current = make_session(answers=ANSWERED_Q1, reask_count=2, screen_action=ResponseAction.REASK)
    built = turn.limit_reached_request(session=current, content=CONTENT, utterance="모르겠어요", next_item_id="Q2")
    assert built.model_dump(mode="json", exclude_none=True) == {
        "runtime_contract_version": 1,
        "action": "SKIP",
        "reason": "LIMIT_REACHED",
        "question_id": "Q1",
        "previous_screen_action": "REASK",
        "user_utterance": "모르겠어요",
        "slots": [{"key": "Q1.diagnosed", "value": True, "status": "ANSWERED"}],
        "values": [],
        "next": {"type": "NEXT", "question_id": "Q2", "text": Q2_TEXT},
    }


def test_model_io_features_turn_on_only_from_v3() -> None:
    assert model_io_features(None) == frozenset() and model_io_features(ModelIoVersion.model_io_v2) == frozenset()
    assert model_io_features(ModelIoVersion.model_io_v3) == frozenset(ModelIoFeature)


def test_staff_help_text_is_appended_and_stays_within_the_sentence_limit() -> None:
    assert (
        turn.with_staff_help("어떤 약이든 괜찮아요.", CONTENT, "Q1")
        == f"어떤 약이든 괜찮아요. {StaffHelpText.EXPLAIN_STAFF_HELP}"
    )
    long = "가" * 344
    fallback = turn.with_staff_help(long, CONTENT, "Q1")
    assert fallback == f"{StaffHelpText.EXPLAIN_STAFF_HELP} {Q1_TEXT}" and len(fallback) <= turn.SENTENCE_MAX
