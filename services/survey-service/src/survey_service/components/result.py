"""result: 세션 결과 조립과 FHIR R4 QuestionnaireResponse 변환, 확인 표시.

입력은 세션 상태와 문항 세트, 출력은 결과(SessionResult)와 FHIR 결과다. 병원 시스템은 당겨 가기만 한다(C10).
FHIR 대응은 계약 FhirMapping 의 설명을 따른다: 세션 상태 → status, 빈칸 원인 → data-absent-reason.
"""

from datetime import datetime

from survey_service.contract.models import (
    BlankReason,
    FhirAbsentReason,
    FhirQuestionnaireResponse,
    QuestionFieldSpec,
    QuestionSetContent,
    ResultSummary,
    SessionResult,
    SessionStatus,
    SlotDataType,
)
from survey_service.types import AnswerRecord, BlankRecord, SessionRecord, SlotValue, split_slot, unwrap

# 계약 FhirMapping 의 status_map(ACTIVE·PAUSED 는 진행 중, ENDED_COMPLETE 는 완료, ENDED_PARTIAL·EXPIRED 는 중단)
FHIR_STATUS = {
    SessionStatus.ACTIVE: "in-progress",
    SessionStatus.PAUSED: "in-progress",
    SessionStatus.ENDED_COMPLETE: "completed",
    SessionStatus.ENDED_PARTIAL: "stopped",
    SessionStatus.EXPIRED: "stopped",
}
# 계약 FhirMapping 의 absent_map
FHIR_ABSENT = {
    BlankReason.UNKNOWN: FhirAbsentReason.asked_unknown,
    BlankReason.UNCLEAR: FhirAbsentReason.asked_unknown,
    BlankReason.REASK_LIMIT: FhirAbsentReason.asked_unknown,
    BlankReason.REJECTED: FhirAbsentReason.asked_declined,
    BlankReason.UNASKED: FhirAbsentReason.not_asked,
}
ABSENT_REASON_URL = "http://hl7.org/fhir/StructureDefinition/data-absent-reason"


def _saved(session: SessionRecord) -> list[AnswerRecord]:
    """저장된 답. 다시 물으려 자리만 남긴 칸(값 null, 상태 MISSING·UNCLEAR)은 답이 아니다."""
    return [a for a in session.answers.values() if a.status == "ANSWERED"]


def blanks_of(session: SessionRecord, content: QuestionSetContent) -> list[BlankRecord]:
    """결과의 빈칸: 모델·한도로 비운 칸, 끝내 정하지 못한 칸(UNCLEAR), 묻지 못한 문항(UNASKED)."""
    blanks = list(session.blanks)
    covered = {b.key for b in blanks if b.key is not None}
    for answer in session.answers.values():
        if answer.status != "ANSWERED" and answer.key not in covered:
            parts = split_slot(answer.key)
            if parts is not None:
                blanks.append(BlankRecord(item_id=parts[0], key=answer.key, reason=BlankReason.UNCLEAR))
    answered_items = {parts[0] for a in _saved(session) if (parts := split_slot(a.key)) is not None}
    blank_items = {b.item_id for b in blanks}
    for item in content.bank.items.root:
        item_id = item.item_id.root
        if item_id not in session.asked_items and item_id not in answered_items and item_id not in blank_items:
            blanks.append(BlankRecord(item_id=item_id, key=None, reason=BlankReason.UNASKED))
    return blanks


def assemble(
    session: SessionRecord,
    content: QuestionSetContent,
    acknowledged: tuple[str, datetime] | None,
) -> SessionResult:
    """결과 한 건. 끝나지 않은 세션은 부분 결과로 상태와 함께 나온다. 환자 발화 원문은 담지 않는다."""
    body: dict[str, object] = {
        "session_id": str(session.session_id),
        "questionnaire_id": session.questionnaire_id,
        "questionnaire_title": content.title.root,
        "question_set_version_id": str(session.question_set_version_id),
        "subject_ref": session.subject_ref,
        "device_id": session.device_id,
        "status": session.status.value,
        "started_at": session.started_at.isoformat(),
        "answers": [{"key": a.key, "value": a.value, "precision": a.precision} for a in _saved(session)],
        "blanks": [b.model_dump(mode="json", exclude_none=True) for b in blanks_of(session, content)],
    }
    if session.ended_at is not None:
        body["ended_at"] = session.ended_at.isoformat()
    if acknowledged is not None:
        body["acknowledged_by"] = acknowledged[0]
        body["acknowledged_at"] = acknowledged[1].isoformat()
    return SessionResult.model_validate(body)


def summary(session: SessionRecord, title: str | None, acknowledged: tuple[str, datetime] | None) -> ResultSummary:
    """결과 목록의 한 줄."""
    body: dict[str, object] = {
        "session_id": str(session.session_id),
        "questionnaire_id": session.questionnaire_id,
        "subject_ref": session.subject_ref,
        "status": session.status.value,
        "started_at": session.started_at.isoformat(),
    }
    if title is not None:
        body["questionnaire_title"] = title
    if session.ended_at is not None:
        body["ended_at"] = session.ended_at.isoformat()
    if acknowledged is not None:
        body["acknowledged_at"] = acknowledged[1].isoformat()
    return ResultSummary.model_validate(body)


def _spec(content: QuestionSetContent, key: str) -> QuestionFieldSpec | None:
    parts = split_slot(key)
    if parts is None:
        return None
    for item in content.bank.items.root:
        if item.item_id.root == parts[0]:
            return next((s for s in item.fields.root if s.field_name.root == parts[2]), None)
    return None


def _fhir_answer(spec: QuestionFieldSpec | None, value: SlotValue) -> dict[str, object]:
    """답 하나의 FHIR value[x]. 자료형은 칸 규격이 정한다."""
    if isinstance(value, bool):
        return {"valueBoolean": value}
    if isinstance(value, str):
        if spec is not None and spec.data_type is SlotDataType.option and spec.options is not None:
            label = next((o.label.root for o in spec.options.root if o.option_code.root == value), None)
            coding: dict[str, object] = {"code": value}
            if label is not None:
                coding["display"] = label
            return {"valueCoding": coding}
        return {"valueString": value}
    if isinstance(value, int) or (
        isinstance(value, float) and value.is_integer() and spec is not None and spec.data_type is SlotDataType.integer
    ):
        return {"valueInteger": int(value)}
    return {"valueDecimal": value}


def to_fhir(result: SessionResult, content: QuestionSetContent, canonical_base_url: str) -> dict[str, object]:
    """결과를 FHIR R4 QuestionnaireResponse 로 옮긴다. 빈칸은 answer 없이 data-absent-reason 확장으로 낸다."""
    answers_by_item: dict[str, list[dict[str, object]]] = {}
    for answer in result.answers:
        parts = split_slot(answer.key.root)
        item_id = parts[0] if parts else answer.key.root
        raw = unwrap(answer.value)
        entry: dict[str, object] = {
            "linkId": answer.key.root,
            "answer": [_fhir_answer(_spec(content, answer.key.root), raw)],
        }
        answers_by_item.setdefault(item_id, []).append(entry)
    blanks_by_item: dict[str, list[dict[str, object]]] = {}
    for blank in result.blanks:
        reason = FHIR_ABSENT[blank.reason]
        link = blank.key.root if blank.key is not None else blank.item_id.root
        extension = {"url": ABSENT_REASON_URL, "valueCode": reason.value}
        blanks_by_item.setdefault(blank.item_id.root, []).append({"linkId": link, "extension": [extension]})
    items: list[dict[str, object]] = []
    for item in content.bank.items.root:
        item_id = item.item_id.root
        children = [*answers_by_item.get(item_id, []), *blanks_by_item.get(item_id, [])]
        if children:
            items.append({"linkId": item_id, "text": item.text.root, "item": children})
    authored = result.ended_at if result.ended_at is not None else result.started_at
    base = canonical_base_url.rstrip("/")
    body: dict[str, object] = {
        "resourceType": "QuestionnaireResponse",
        "status": FHIR_STATUS[result.status],
        "questionnaire": f"{base}/{result.questionnaire_id.root}",
        "subject": {"identifier": {"value": result.subject_ref.root}},
        "authored": authored.root.isoformat(),
        "item": items,
    }
    # 왜 검증하고 본문은 그대로 내나: 계약 FhirQuestionnaireResponse 는 필수 칸(resourceType, status)만 검증하는 열린 객체다.
    # 나머지 칸은 FHIR R4 사양이 정본이라 모델로 옮기면 버려진다
    FhirQuestionnaireResponse.model_validate(body)
    return body
