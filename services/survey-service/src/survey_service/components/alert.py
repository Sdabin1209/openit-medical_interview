"""alert: 직원 알림 만들기(위험, 직원 호출, 결과 도착)와 보이는 대상·푸시 내용.

입력은 세션 사건, 출력은 알림이다. 되묻기 한도에 닿아 건너뛰는 것은 알림을 내지 않는다(v7-flow-resolutions).
"""

from datetime import datetime
from uuid import UUID

from survey_service.contract.models import (
    AlertEventName,
    AlertKind,
    RiskCategory,
    StaffAlert,
    StaffAlertEvent,
    UserRole,
    WebPushPayload,
)
from survey_service.types import AlertEventRecord, AlertRecord, SessionRecord

# 왜 이 대응: 직원은 위험과 직원 호출을, 의사는 결과 도착을 본다(계약 listStaffAlerts, registerPushSubscription 설명)
STAFF_KINDS = (AlertKind.RISK, AlertKind.CALL_STAFF)
CLINICIAN_KINDS = (AlertKind.RESULT_READY,)


def kinds_for(roles: frozenset[str]) -> tuple[AlertKind, ...]:
    """호출자의 역할이 볼 수 있는 알림 종류들."""
    kinds: list[AlertKind] = []
    if UserRole.staff.value in roles:
        kinds += STAFF_KINDS
    if UserRole.clinician.value in roles:
        kinds += CLINICIAN_KINDS
    return tuple(kinds)


def _make(
    session: SessionRecord, kind: AlertKind, alert_id: UUID, now: datetime, dedupe_key: str | None, title: str | None
) -> AlertRecord:
    return AlertRecord(
        alert_id=alert_id,
        kind=kind,
        session_id=session.session_id,
        device_id=None if kind is AlertKind.RESULT_READY else session.device_id,
        questionnaire_title=title,
        dedupe_key=dedupe_key,
        raised_at=now,
    )


def risk(
    session: SessionRecord,
    category: RiskCategory,
    detected_at: datetime,
    alert_id: UUID,
    now: datetime,
    title: str | None,
) -> AlertRecord:
    """위험 신호의 알림. 같은 세션·분류·감지 시각은 같은 키라 한 번만 처리된다(멱등)."""
    key = f"risk:{session.session_id}:{category.value}:{detected_at.isoformat()}"
    return _make(session, AlertKind.RISK, alert_id, now, key, title)


def call_staff(session: SessionRecord, alert_id: UUID, now: datetime, title: str | None) -> AlertRecord:
    """직원 호출 알림."""
    return _make(session, AlertKind.CALL_STAFF, alert_id, now, None, title)


def result_ready(session: SessionRecord, alert_id: UUID, now: datetime, title: str | None) -> AlertRecord:
    """결과 도착 알림(의사에게). 세션마다 한 번이다."""
    return _make(session, AlertKind.RESULT_READY, alert_id, now, f"result:{session.session_id}", title)


def to_contract(alert: AlertRecord) -> StaffAlert:
    """계약의 StaffAlert."""
    body: dict[str, object] = {
        "alert_id": str(alert.alert_id),
        "kind": alert.kind.value,
        "session_id": str(alert.session_id),
        "raised_at": alert.raised_at.isoformat(),
    }
    if alert.device_id is not None:
        body["device_id"] = alert.device_id
    if alert.questionnaire_title is not None:
        body["questionnaire_title"] = alert.questionnaire_title
    if alert.resolved_at is not None:
        body["resolved_at"] = alert.resolved_at.isoformat()
    return StaffAlert.model_validate(body)


def push_payload(alert: AlertRecord) -> WebPushPayload:
    """푸시 메시지 안에 암호화해 담는 내용. 환자 정보는 담지 않는다(D88)."""
    return WebPushPayload.model_validate(
        {"kind": alert.kind.value, "alert_id": str(alert.alert_id), "raised_at": alert.raised_at.isoformat()}
    )


def event_body(record: AlertEventRecord) -> StaffAlertEvent:
    """SSE 이벤트의 data 본문."""
    return StaffAlertEvent.model_validate(
        {
            "event": record.event,
            "sequence": record.sequence,
            "alert": to_contract(record.alert).model_dump(mode="json", exclude_none=True),
        }
    )


def sse_frame(name: AlertEventName, data_json: str, sequence: int | None) -> str:
    """Server-Sent Events 한 건의 글(WHATWG HTML 9.2). heartbeat 와 resync 에는 id 가 없어 재개 위치를 바꾸지 않는다."""
    lines = [f"event: {name.value}"]
    if sequence is not None:
        lines.append(f"id: {sequence}")
    lines.append(f"data: {data_json}")
    return "\n".join(lines) + "\n\n"
