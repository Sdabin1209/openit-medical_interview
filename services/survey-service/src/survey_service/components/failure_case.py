"""failure_case: 실패 탐지(규칙), 검토 상태, 비식별 내보내기.

입력은 저장된 턴 기록과 검토 결과, 출력은 실패 사례와 내보내기 값이다. 탐지는 규칙 둘이다.
EXTRACT_FAILED(추출 출력 불가로 턴이 실패), REASK_STREAK(되묻기 한도로 서비스가 문항을 건너뜀).
CONFIRMED 만 내보낸다(N09). 환자 발화 원문은 내보내기에 싣지 않고 검토자가 고쳐 쓴 문장만 나간다(D15, L12).
"""

from collections.abc import Callable, Iterable
from datetime import datetime
from uuid import UUID

from survey_service.contract.models import (
    CaseReview,
    DeidentifiedTrace,
    FailureCase,
    FailureCaseExport,
    FailureKind,
    ReviewStatus,
    TurnFailureReason,
)
from survey_service.types import (
    FailureCaseData,
    ReviewDecision,
    ReviewVerdict,
    TurnOutcome,
    TurnRecordData,
)


def detect(turns: Iterable[TurnRecordData], new_id: Callable[[], UUID], now: datetime) -> list[FailureCaseData]:
    """턴 기록에서 실패 사례를 규칙으로 찾는다. 한 턴은 사례를 둘 이상 만들지 않는다(EXTRACT_FAILED 가 먼저)."""
    found: list[FailureCaseData] = []
    for turn in turns:
        kind: FailureKind | None = None
        if turn.outcome is TurnOutcome.FAILED and turn.failure_signal is TurnFailureReason.EXTRACTION_UNAVAILABLE:
            kind = FailureKind.EXTRACT_FAILED
        elif turn.outcome is TurnOutcome.DONE and turn.reask_limit_hit:
            kind = FailureKind.REASK_STREAK
        if kind is None:
            continue
        found.append(
            FailureCaseData(
                case_id=new_id(),
                case_version=1,
                kind=kind,
                session_id=turn.session_id,
                turn_id=turn.turn_id,
                item_id=turn.item_id,
                questionnaire_id=turn.questionnaire_id,
                model_output=turn.extract_output,
                utterance=turn.utterance,
                review_status=ReviewStatus.UNREVIEWED,
                failure_signal=turn.failure_signal,
                response_text=turn.response_text,
                created_at=now,
                occurred_at=turn.finished_at or turn.started_at,
            )
        )
    return found


def review(current: FailureCaseData, body: CaseReview, reviewer: str, now: datetime) -> ReviewDecision:
    """검토 게시. 기준 버전이 최신이 아니면 거절(동시 수정 방지), 내용이 모두 같으면 변화 없음, 다르면 새 버전."""
    if body.base_case_version.root != current.case_version:
        return ReviewDecision(verdict=ReviewVerdict.VERSION_MISMATCH)
    reviewed_input = body.reviewed_input.root if body.reviewed_input is not None else None
    if (
        current.review_status is body.review_status
        and current.expected == body.expected
        and current.reviewed_input == reviewed_input
    ):
        return ReviewDecision(verdict=ReviewVerdict.UNCHANGED)
    updated = current.model_copy(
        update={
            "case_version": current.case_version + 1,
            "review_status": body.review_status,
            "expected": body.expected,
            "reviewed_input": reviewed_input,
            "reviewed_by": reviewer,
            "reviewed_at": now,
        }
    )
    return ReviewDecision(verdict=ReviewVerdict.NEW_VERSION, next=updated)


def exportable(case: FailureCaseData) -> bool:
    """내보낼 수 있는 사례(검토를 마친 CONFIRMED)."""
    return case.review_status is ReviewStatus.CONFIRMED


def to_case(case: FailureCaseData) -> FailureCase:
    """검토자에게 나가는 사례(환자 발화 원문 포함)."""
    return FailureCase.model_validate(_case_body(case, with_review_fields=True))


def to_export(case: FailureCaseData) -> FailureCaseExport:
    """model-lab 이 당겨 가는 사례. 환자 발화 원문과 모델 출력은 담지 않는다."""
    return FailureCaseExport.model_validate(_case_body(case, with_review_fields=False))


def to_trace(case: FailureCaseData) -> DeidentifiedTrace:
    """검토자가 읽는 비식별 턴 기록. 발화는 검토자가 개인정보를 빼고 고쳐 쓴 것만 나간다(자동 비식별은 하지 않는다)."""
    body: dict[str, object] = {"case_id": str(case.case_id), "occurred_at": case.occurred_at.isoformat()}
    if case.model_output is not None:
        body["extract_output"] = case.model_output.model_dump(mode="json", exclude_none=True)
    if case.failure_signal is not None:
        body["failure_signal"] = case.failure_signal.value
    if case.response_text is not None:
        body["response_text"] = case.response_text
    if case.reviewed_input is not None:
        body["utterance"] = case.reviewed_input
    return DeidentifiedTrace.model_validate(body)


def _case_body(case: FailureCaseData, *, with_review_fields: bool) -> dict[str, object]:
    body: dict[str, object] = {
        "case_id": str(case.case_id),
        "case_version": case.case_version,
        "kind": case.kind.value,
        "item_id": case.item_id,
        "questionnaire_id": case.questionnaire_id,
        "review_status": case.review_status.value,
        "created_at": case.created_at.isoformat(),
    }
    if case.expected is not None:
        body["expected"] = case.expected.model_dump(mode="json", exclude_none=True)
    if case.reviewed_input is not None:
        body["reviewed_input"] = case.reviewed_input
    if with_review_fields:
        if case.model_output is not None:
            body["model_output"] = case.model_output.model_dump(mode="json", exclude_none=True)
        if case.utterance is not None:
            body["utterance"] = case.utterance
        if case.reviewed_by is not None:
            body["reviewed_by"] = case.reviewed_by
        if case.reviewed_at is not None:
            body["reviewed_at"] = case.reviewed_at.isoformat()
    return body
