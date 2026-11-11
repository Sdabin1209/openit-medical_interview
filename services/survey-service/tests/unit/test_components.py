"""컴포넌트 단위 시험: 입력과 출력만 본다(저장·HTTP 없음)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from tests.support.harness import extraction, question_set, value

from survey_service.components import failure_case, question_bank, result, session, start_code, trace, turn
from survey_service.contract.models import (
    ActionExtraction,
    BlankReason,
    CaseReview,
    QuestionSetContent,
    ReviewStatus,
    SessionStatus,
)
from survey_service.types import (
    AnswerRecord,
    BlankRecord,
    FailureCaseData,
    ReviewVerdict,
    SessionRecord,
    StartCodeVerdict,
    TurnOutcome,
    TurnRecordData,
)

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
CONTENT = QuestionSetContent.model_validate(question_set()["content"])


def make_session(**update: Any) -> SessionRecord:
    base = session.start(
        session_id=uuid.uuid4(), device_id="kiosk-01", subject_ref="s", questionnaire_id="q", question_set_version_id=uuid.uuid4(),
        runtime_contract_version=1, first_item_id="Q1", greeting="안녕하세요", model_io_version="model-io-v2", now=NOW,
    )  # fmt: skip
    return base.model_copy(update=update)


def apply(current: SessionRecord, body: dict[str, object], *, skip: str = "Q2", limit: int = 2):  # noqa: ANN201
    return session.apply_extraction(
        current, ActionExtraction.model_validate(body), skip_target=skip, reask_limit=limit, now=NOW
    )


# ---------------------------------------------------------------- question_bank


def test_bank_valid_content_has_no_problems_and_hash_ignores_key_order() -> None:
    assert question_bank.validate(CONTENT) == []
    reordered = QuestionSetContent.model_validate(dict(reversed(list(question_set()["content"].items()))))
    assert question_bank.content_hash(CONTENT) == question_bank.content_hash(reordered)
    changed = question_set()
    changed["content"]["title"] = "다른 제목"
    assert question_bank.content_hash(
        QuestionSetContent.model_validate(changed["content"])
    ) != question_bank.content_hash(CONTENT)


def test_bank_field_total_limit_and_lookup() -> None:
    many = question_set()
    for index, count in ((0, 60), (1, 50)):  # 문항마다는 상한 안이지만 합이 상한(104)을 넘는다
        item = many["content"]["bank"]["items"][index]
        item["fields"] = [
            {"item_id": item["item_id"], "field_name": f"f{n}", "data_type": "boolean"} for n in range(count)
        ]
    problems = question_bank.validate(QuestionSetContent.model_validate(many["content"]))
    assert any("상한" in p.detail for p in problems)
    assert (
        question_bank.question_text(CONTENT, "Q2") == "술을 드시나요?"
        and question_bank.question_text(CONTENT, "Q9") is None
    )
    assert len(question_bank.all_field_specs(CONTENT)) == 4


@pytest.mark.parametrize(
    ("operator", "left", "right", "expected"),
    [("EQ", 3, 3, True), ("NE", 3, 4, True), ("LT", 2, 3, True), ("LE", 3, 3, True), ("GT", 4, 3, True), ("GE", 3, 4, False),
     ("EQ", True, 1, False), ("LT", "a", "b", False), ("EQ", None, 1, False), ("GT", True, False, False)],
)  # fmt: skip
def test_bank_comparisons(operator: str, left: object, right: object, expected: bool) -> None:
    body = question_set()["content"]
    body["flow"]["rules"][1]["branches"][0] = {
        "when": {"slot": "Q2.answer", "operator": operator, "value": right},
        "next_item": "END",
    }
    content = QuestionSetContent.model_validate(body)
    answers = {"Q2.answer": left}
    assert (question_bank.next_after(content, "Q2", answers) == "END") is expected  # pyright: ignore[reportArgumentType]


def test_bank_next_after_default_and_unknown() -> None:
    assert question_bank.next_after(CONTENT, "Q1", {}) == "Q2"
    assert question_bank.next_after(CONTENT, "Q2", {"Q2.answer": False}) == "END"
    assert question_bank.next_after(CONTENT, "Q2", {"Q2.answer": True}) == "Q2_1"
    assert question_bank.next_after(CONTENT, "Q2", {}) == "Q2_1"  # 답이 없으면 조건이 맞지 않아 기본 분기
    assert question_bank.next_after(CONTENT, "nope", {}) == "END"


# ---------------------------------------------------------------- start_code


def test_start_code_shape_and_verdicts() -> None:
    codes = {start_code.new_code() for _ in range(50)}
    assert all(len(c) == 6 and c.isdigit() for c in codes) and len(codes) > 40
    record = start_code.issue(
        code="123456", subject_ref="s", questionnaire_id=None, issued_by="u", now=NOW, ttl_seconds=300
    )
    assert record.expires_at - record.issued_at == timedelta(seconds=300)
    ev = start_code.evaluate
    assert ev(None, "d", NOW) is StartCodeVerdict.INVALID
    assert ev(record, "d", NOW) is StartCodeVerdict.OK
    assert ev(record, "d", NOW + timedelta(seconds=300)) is StartCodeVerdict.EXPIRED
    used = start_code.use(record, "d", uuid.uuid4())
    assert (
        ev(used, "d", NOW) is StartCodeVerdict.REPLAY
        and ev(used, "d", NOW + timedelta(days=1)) is StartCodeVerdict.REPLAY
    )
    assert ev(used, "other", NOW) is StartCodeVerdict.USED


# ---------------------------------------------------------------- session


def test_next_moves_item_and_saves_values() -> None:
    t = apply(make_session(), extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
    assert (
        t.session.current_item_id == "Q2"
        and t.session.previous_item_id == "Q1"
        and t.session.asked_items == ("Q1", "Q2")
    )
    assert t.session.answers["Q1.diagnosed"].value is True and not t.limit_skip


def test_correct_overwrites_and_clears_blank() -> None:
    current = make_session(
        answers={"Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=False, precision="exact", status="ANSWERED")},
        blanks=(BlankRecord(item_id="Q1", key="Q1.diagnosed", reason=BlankReason.UNKNOWN),),
    )
    t = apply(current, extraction("CORRECT", "Q2", [value("Q1.diagnosed", True, "CORRECTION")]))
    assert t.session.answers["Q1.diagnosed"].value is True and t.session.blanks == ()


def test_hold_and_skip_record_blanks_with_reasons() -> None:
    held = apply(
        make_session(),
        extraction(
            "HOLD",
            "Q2",
            [value("Q1.diagnosed", None, "UNKNOWN", "unspecified")],
            reason="UNCERTAIN",
            targets=["Q1.diagnosed"],
        ),
    )
    assert held.session.blanks == (BlankRecord(item_id="Q1", key="Q1.diagnosed", reason=BlankReason.UNKNOWN),)
    skipped = apply(
        make_session(),
        extraction(
            "SKIP",
            "Q2",
            [value("Q1.diagnosed", None, "REJECTED", "unspecified")],
            reason="REFUSED",
            targets=["Q1.diagnosed"],
        ),
    )
    assert skipped.session.blanks[0].reason is BlankReason.REJECTED and skipped.session.current_item_id == "Q2"


def test_reask_counts_up_to_limit_then_skips_and_redirect_is_not_counted() -> None:
    reask = extraction(
        "REASK",
        "Q1",
        [value("Q1.diagnosed", None, "UNCLEAR", "unspecified")],
        reason="MISSING",
        targets=["Q1.diagnosed"],
    )
    redirect = extraction("REDIRECT", "Q1", [], reason="OFF_TOPIC")
    current = make_session()
    current = apply(current, reask).session
    current = apply(current, redirect).session
    assert current.reask_count == 1 and current.answers["Q1.diagnosed"].status == "UNCLEAR"
    current = apply(current, reask).session
    assert current.reask_count == 2 and current.current_item_id == "Q1"
    final = apply(current, reask)  # 처음 질문 1회 + 되묻기 2회 뒤의 세 번째
    assert final.limit_skip and final.session.current_item_id == "Q2" and final.session.reask_count == 0
    assert final.session.blanks == (BlankRecord(item_id="Q1", key="Q1.diagnosed", reason=BlankReason.REASK_LIMIT),)


def test_confirm_counts_like_reask_and_whole_item_blank_when_no_placeholder() -> None:
    confirm = extraction(
        "CONFIRM",
        "Q1",
        [value("Q1.diagnosed", True, "CONFLICT")],
        reason="CONFLICT_WITH_PREVIOUS",
        targets=["Q1.diagnosed"],
    )
    current = make_session(reask_count=2)
    final = apply(current, confirm)
    assert final.limit_skip and final.session.blanks == (
        BlankRecord(item_id="Q1", key=None, reason=BlankReason.REASK_LIMIT),
    )


def test_last_item_ends_complete_and_limit_skip_can_end() -> None:
    last = make_session(current_item_id="Q2_1")
    done = apply(last, extraction("NEXT", "END", [value("Q2_1.amount", 3)]))
    assert (
        done.session.status is SessionStatus.ENDED_COMPLETE
        and done.session.current_item_id is None
        and done.session.ended_at == NOW
    )
    reask = extraction("REASK", "Q2_1", [], reason="MISSING", targets=["Q2_1.amount"])
    skipped = apply(last.model_copy(update={"reask_count": 2}), reask, skip="END")
    assert skipped.session.status is SessionStatus.ENDED_COMPLETE


def test_lifecycle_pause_resume_end_expire() -> None:
    active = make_session()
    paused = session.pause(active, session.PauseReason.STAFF_CALL, NOW)
    assert paused.status is SessionStatus.PAUSED
    resumed = session.resume(paused, NOW)
    assert resumed.status is SessionStatus.ACTIVE and resumed.resume_pending and resumed.pause_reason is None
    assert session.expire_if_idle(paused, NOW + timedelta(hours=1), 60) is paused  # 멈춘 세션은 만료하지 않는다
    assert session.expire_if_idle(active, NOW + timedelta(seconds=59), 60) is active
    assert session.expire_if_idle(active, NOW + timedelta(seconds=60), 60).status is SessionStatus.EXPIRED
    ended = session.end(active, NOW)
    assert ended.status is SessionStatus.ENDED_PARTIAL and session.end(ended, NOW + timedelta(hours=1)) is ended


# ---------------------------------------------------------------- turn


def test_requests_carry_structured_values_only() -> None:
    answers = {
        "Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=True, precision="exact", status="ANSWERED"),
        "Q1.on_medication": AnswerRecord(key="Q1.on_medication", value=None, precision="unspecified", status="UNCLEAR"),
    }
    current = make_session(answers=answers, previous_item_id="Q0", current_item_id="Q2")
    request = turn.extraction_request(current, CONTENT, "네")
    body = request.model_dump(mode="json", exclude_none=True)
    assert body["question_id"] == "Q2" and body["previous_question_id"] == "Q0" and body["user_utterance"] == "네"
    assert body["current_question"] == "안녕하세요"
    assert [s["key"] for s in body["slots"]] == ["Q1.diagnosed", "Q1.on_medication"]  # 넣은 순서가 state 순서다
    assert body["slots"][1] == {"key": "Q1.on_medication", "value": None, "status": "UNCLEAR"}
    assert "topic" not in body and "state" not in body and len(body["fields"]) == 4
    first = make_session()
    assert "previous_question_id" not in turn.extraction_request(first, CONTENT, "네").model_dump(exclude_none=True)
    start = turn.start_response_request(CONTENT, "Q1", 1).model_dump(mode="json", exclude_none=True)
    assert start == {
        "runtime_contract_version": 1,
        "action": "START",
        "next": {"type": "NEXT", "question_id": "Q1", "text": "뇌졸중으로 진단받으셨거나 약을 드시나요?"},
    }
    assert turn.limit_skip_text(CONTENT, "END").endswith("감사합니다.") and "한 번에 몇 잔" in turn.limit_skip_text(
        CONTENT, "Q2_1"
    )
    assert (
        turn.resume_text(CONTENT, "Q2").endswith("술을 드시나요?")
        and turn.resume_text(CONTENT, None) == "문진을 이어서 할게요."
    )


def test_response_request_for_each_action_matches_contract_rules() -> None:
    current = make_session()
    answers = {"Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=True, precision="exact", status="ANSWERED")}
    cases = {
        "CORRECT": extraction("CORRECT", "Q2", [value("Q1.diagnosed", False, "CORRECTION")]),
        "REASK": extraction("REASK", "Q1", [], reason="MISSING", targets=["Q1.diagnosed"]),
        "CONFIRM": extraction("CONFIRM", "Q1", [value("Q1.diagnosed", False, "CONFLICT")], reason="CONFLICT_WITH_PREVIOUS", targets=["Q1.diagnosed"]),
        "HOLD": extraction("HOLD", "END", [], reason="UNCERTAIN", targets=["Q1.diagnosed"]),
        "SKIP": extraction("SKIP", "Q2", [], reason="REFUSED", targets=["Q1.on_medication"]),
        "REDIRECT": extraction("REDIRECT", "Q1", [], reason="OUT_OF_SCHEMA", note="손발이 저림"),
    }  # fmt: skip
    for action, body in cases.items():
        extracted = ActionExtraction.model_validate(body)
        transition = session.apply_extraction(
            current.model_copy(update={"answers": answers}), extracted, skip_target="Q2", reask_limit=2, now=NOW
        )
        request = turn.response_request(
            session=current.model_copy(update={"answers": answers}),
            content=CONTENT,
            extraction=extracted,
            transition=transition,
            utterance="말",
        )
        body = request.model_dump(mode="json", exclude_none=True)
        assert body["action"] == action  # 계약의 조건부 규칙은 모델 검증이 이미 통과했다
        assert body["values"] == ExtractedValuesDump.dump(extracted) and body["slots"][0]["key"] == "Q1.diagnosed"
        assert ("note" in body) is (action == "REDIRECT") and ("targets" in body) is (
            action in {"REASK", "CONFIRM", "HOLD", "SKIP"}
        )
    same = turn.response_request(
        session=current, content=CONTENT, extraction=ActionExtraction.model_validate(cases["CONFIRM"]),
        transition=session.apply_extraction(current, ActionExtraction.model_validate(cases["CONFIRM"]), skip_target="Q2", reask_limit=2, now=NOW),
        utterance="말",
    )  # fmt: skip
    assert (
        same.next.type.value == "SAME"
        and same.next.text is not None
        and same.next.text.root == "뇌졸중으로 진단받으셨거나 약을 드시나요?"
    )
    end = turn.response_request(
        session=current, content=CONTENT, extraction=ActionExtraction.model_validate(cases["HOLD"]),
        transition=session.apply_extraction(current, ActionExtraction.model_validate(cases["HOLD"]), skip_target="Q2", reask_limit=2, now=NOW),
        utterance="말",
    )  # fmt: skip
    assert end.next.type.value == "END" and end.next.question_id is None


class ExtractedValuesDump:
    """추출 출력의 values 를 요청에 실리는 모양으로 낸다."""

    @staticmethod
    def dump(extracted: ActionExtraction) -> list[dict[str, object]]:
        return extracted.values.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------- result


def test_blank_assembly_and_fhir_value_types() -> None:
    current = make_session(
        answers={
            "Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=True, precision="exact", status="ANSWERED"),
            "Q2_1.amount": AnswerRecord(key="Q2_1.amount", value=3, precision="approximate", status="ANSWERED"),
            "Q1.on_medication": AnswerRecord(key="Q1.on_medication", value=None, precision="unspecified", status="UNCLEAR"),
        },
        asked_items=("Q1", "Q2_1"),
        status=SessionStatus.EXPIRED, ended_at=NOW,
    )  # fmt: skip
    blanks = {(b.item_id, b.key, b.reason) for b in result.blanks_of(current, CONTENT)}
    assert blanks == {("Q1", "Q1.on_medication", BlankReason.UNCLEAR), ("Q2", None, BlankReason.UNASKED)}
    built = result.assemble(current, CONTENT, ("doctor", NOW))
    assert built.acknowledged_by is not None and [a.key.root for a in built.answers] == ["Q1.diagnosed", "Q2_1.amount"]
    fhir = result.to_fhir(built, CONTENT, "https://example.org/fhir/Questionnaire/")
    assert fhir["status"] == "stopped" and fhir["questionnaire"] == "https://example.org/fhir/Questionnaire/q"
    text = str(fhir)
    assert "valueBoolean" in text and "valueInteger" in text and "asked-unknown" in text and "not-asked" in text


# ---------------------------------------------------------------- trace, failure_case


def _turn(outcome: TurnOutcome, **update: Any) -> TurnRecordData:
    return TurnRecordData(
        session_id=uuid.UUID(int=1), turn_id=uuid.UUID(int=2), questionnaire_id="q", item_id="Q1", outcome=outcome,
        utterance="말", started_at=NOW, **update,
    )  # fmt: skip


def test_trace_merge_prefers_the_more_finished_record() -> None:
    processing, failed, done = _turn(TurnOutcome.PROCESSING), _turn(TurnOutcome.FAILED), _turn(TurnOutcome.DONE)
    assert trace.merge(None, processing) is processing
    assert (
        trace.merge(processing, failed) is failed
        and trace.merge(done, failed) is done
        and trace.merge(failed, failed.model_copy()) is not None
    )
    kind, sid, detail = trace.business_event("turn_done", None, action="NEXT")
    assert (kind, sid, detail) == ("turn_done", None, {"action": "NEXT"})


def test_detection_rules() -> None:
    sig = {"failure_signal": "EXTRACTION_UNAVAILABLE", "finished_at": NOW}
    turns = [
        _turn(TurnOutcome.FAILED, **sig),
        _turn(TurnOutcome.FAILED, failure_signal="RESPONSE_UNAVAILABLE", finished_at=NOW),
        _turn(TurnOutcome.DONE, reask_limit_hit=True, finished_at=NOW),
        _turn(TurnOutcome.DONE, finished_at=NOW),
    ]
    kinds = [c.kind.value for c in failure_case.detect(turns, uuid.uuid4, NOW)]
    assert kinds == ["EXTRACT_FAILED", "REASK_STREAK"]


def test_review_decisions() -> None:
    case = FailureCaseData(
        case_id=uuid.uuid4(), case_version=1, kind=failure_case.FailureKind.EXTRACT_FAILED, session_id=uuid.uuid4(), turn_id=uuid.uuid4(),
        item_id="Q1", questionnaire_id="q", model_output=None, utterance="원문", review_status=ReviewStatus.UNREVIEWED,
        created_at=NOW, occurred_at=NOW,
    )  # fmt: skip
    body = CaseReview.model_validate({"base_case_version": 1, "review_status": "DISMISSED"})
    assert failure_case.review(case, body, "r", NOW).verdict is ReviewVerdict.NEW_VERSION
    stale = CaseReview.model_validate({"base_case_version": 5, "review_status": "DISMISSED"})
    assert failure_case.review(case, stale, "r", NOW).verdict is ReviewVerdict.VERSION_MISMATCH
    same = CaseReview.model_validate({"base_case_version": 1, "review_status": "UNREVIEWED"})
    assert failure_case.review(case, same, "r", NOW).verdict is ReviewVerdict.UNCHANGED
    assert not failure_case.exportable(case)


def test_fhir_absent_map_covers_every_blank_reason_and_failure_limit_is_error() -> None:
    """계약 FhirMapping 의 absent_map: 빈칸 원인 여섯 값이 모두 있고 FAILURE_LIMIT 는 error 다."""
    from survey_service.contract.models import FhirAbsentReason

    assert set(result.FHIR_ABSENT) == set(BlankReason)
    assert result.FHIR_ABSENT[BlankReason.FAILURE_LIMIT] is FhirAbsentReason.error
    assert result.FHIR_ABSENT[BlankReason.REASK_LIMIT] is FhirAbsentReason.asked_unknown


def test_failure_limit_skip_blanks_unsaved_slots_and_moves_on() -> None:
    placeholder = make_session(
        answers={
            "Q1.diagnosed": AnswerRecord(key="Q1.diagnosed", value=None, precision="unspecified", status="UNCLEAR")
        },
        reask_count=1,
        failed_turn_ids=(uuid.uuid4(), uuid.uuid4()),
    )
    moved = session.skip_for_failure_limit(placeholder, skip_target="Q2", now=NOW)
    assert not moved.limit_skip and moved.session.current_item_id == "Q2" and moved.session.reask_count == 0
    assert moved.session.failed_turn_ids == () and moved.session.previous_item_id == "Q1"
    assert moved.session.blanks == (BlankRecord(item_id="Q1", key="Q1.diagnosed", reason=BlankReason.FAILURE_LIMIT),)


def test_failure_limit_turn_is_still_a_detected_extract_failure() -> None:
    """연속 실패 한도로 건너뛴 턴은 DONE 으로 기록되지만 추출 실패 사례를 잃지 않는다."""
    from survey_service.contract.models import FailureKind, TurnFailureReason

    done = TurnRecordData(
        session_id=uuid.uuid4(), turn_id=uuid.uuid4(), questionnaire_id="q", item_id="Q1", outcome=TurnOutcome.DONE,
        utterance="음", failure_signal=TurnFailureReason.EXTRACTION_UNAVAILABLE, started_at=NOW,
    )  # fmt: skip
    found = failure_case.detect([done], uuid.uuid4, NOW)
    assert [f.kind for f in found] == [FailureKind.EXTRACT_FAILED]
