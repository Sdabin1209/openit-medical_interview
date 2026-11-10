"""trace: 턴 기록과 업무 로그 저장 준비(최소 1회 수신, 중복 제거).

입력은 턴 처리의 사건, 출력은 저장할 턴 기록과 중복을 가른 결과다. DB 접근은 모른다(store 가 한다).
같은 (session_id, turn_id) 는 한 건이고, 재전송이나 재시도로 같은 기록이 다시 와도 하나로 합친다.
"""

from datetime import datetime
from uuid import UUID

from survey_service.contract.models import ActionExtraction, TurnFailureReason
from survey_service.types import SessionRecord, TurnOutcome, TurnRecordData

# 왜 이 순서: DONE 이 이미 있으면 뒤늦게 온 FAILED 나 PROCESSING 이 덮지 않는다(최소 1회 수신의 중복·역순 도착)
_RANK = {TurnOutcome.PROCESSING: 0, TurnOutcome.FAILED: 1, TurnOutcome.DONE: 2}


def begin(session: SessionRecord, turn_id: UUID, utterance: str, now: datetime) -> TurnRecordData:
    """처리 시작 기록(PROCESSING). 같은 turn_id 의 동시 요청을 가르는 표시다."""
    if session.current_item_id is None:
        raise ValueError("진행 중인 세션이 아니다")
    return TurnRecordData(
        session_id=session.session_id,
        turn_id=turn_id,
        questionnaire_id=session.questionnaire_id,
        item_id=session.current_item_id,
        outcome=TurnOutcome.PROCESSING,
        utterance=utterance,
        started_at=now,
    )


def done(
    started: TurnRecordData,
    *,
    extraction: ActionExtraction,
    response_text: str,
    response: dict[str, object],
    package_digest: str | None,
    reask_limit_hit: bool,
    now: datetime,
) -> TurnRecordData:
    """값을 만든 턴의 기록."""
    return started.model_copy(
        update={
            "outcome": TurnOutcome.DONE,
            "extract_output": extraction,
            "response_text": response_text,
            "response": response,
            "package_digest": package_digest,
            "reask_limit_hit": reask_limit_hit,
            "finished_at": now,
        }
    )


def failed(
    started: TurnRecordData,
    *,
    signal: TurnFailureReason,
    response: dict[str, object],
    extraction: ActionExtraction | None,
    package_digest: str | None,
    now: datetime,
) -> TurnRecordData:
    """값을 만들지 못한 턴의 기록. 세션 상태는 바뀌지 않으므로 같은 turn_id 로 다시 처리할 수 있다(D75)."""
    return started.model_copy(
        update={
            "outcome": TurnOutcome.FAILED,
            "failure_signal": signal,
            "response": response,
            "extract_output": extraction,
            "package_digest": package_digest,
            "finished_at": now,
        }
    )


def merge(existing: TurnRecordData | None, incoming: TurnRecordData) -> TurnRecordData:
    """같은 턴의 기록이 둘 이상 오면 하나로 합친다. 더 끝난 쪽을 남기고 같으면 먼저 온 것을 남긴다."""
    if existing is None or _RANK[incoming.outcome] > _RANK[existing.outcome]:
        return incoming
    return existing


def business_event(
    kind: str, session_id: UUID | None, **detail: str | int | bool
) -> tuple[str, UUID | None, dict[str, object]]:
    """업무 로그 한 건(종류, 세션, 세부). 환자 발화와 비밀은 넣지 않는다."""
    return kind, session_id, dict(detail)
