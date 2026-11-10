"""link_admin_api: 직원·의사·관리자 요청을 받는 HTTP 서버(시작 코드 발급, 개입, 알림, 푸시, 문항 세트, 실패
사례 검토와 내보내기).

사람은 OIDC 토큰의 역할로, model-lab 은 기계 토큰(case-reader)으로 들어온다. 신원은 인증된 값만 쓰고 본문의
신원은 읽지 않는다.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, StreamingResponse

from survey_service.components import alert, failure_case, question_bank, session, start_code, turn
from survey_service.contract.models import (
    AlertEventName,
    CaseReview,
    InterventionAction,
    InterventionDecision,
    ProblemReason,
    PushConfig,
    PushSubscription,
    QuestionSetUpload,
    QuestionSetVersion,
    ReviewStatus,
    SessionStatus,
    StaffAlertEvent,
    StartCodeIssueRequest,
)
from survey_service.link import auth as authn
from survey_service.link.common import CursorQuery, LimitQuery, content_of, invalid_cursor, reply
from survey_service.link.problem import ApiError
from survey_service.types import (
    DuplicateError,
    InvalidCursorError,
    ReviewVerdict,
    Runtime,
    StoredQuestionSet,
)

MAX_CODE_ATTEMPTS = 8  # 왜 8: kiosk_api 와 같다. 100만 개 중 살아 있는 코드와 겹칠 확률이 극히 작다(측정하지 않았다)
# 왜 1초: 알림 스트림이 DB 의 새 이벤트를 보는 간격이다. 직원 알림은 초 단위면 충분하다고 본 선택이며
# 측정하지 않았다(ADR 0004)
STREAM_POLL_SECONDS = 1.0
STREAM_BATCH = 100
IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]
LastEventId = Annotated[int | None, Header(alias="Last-Event-ID", ge=0, le=9007199254740991)]


def _version_body(stored: StoredQuestionSet) -> QuestionSetVersion:
    return QuestionSetVersion.model_validate(
        {
            "question_set_version_id": str(stored.question_set_version_id),
            "questionnaire_id": stored.questionnaire_id,
            "version_number": stored.version_number,
            "runtime_contract_version": stored.runtime_contract_version,
            "content": stored.content,
            "content_hash": stored.content_hash,
            "uploaded_by": stored.uploaded_by,
            "created_at": stored.created_at.isoformat(),
        }
    )


def router(rt: Runtime) -> APIRouter:
    """관리 경로들."""
    api = APIRouter()

    # ------------------------------------------------------------ 시작 코드
    @api.post("/v1/start-codes", tags=["start-codes"])
    async def issue_start_code(  # pyright: ignore[reportUnusedFunction]
        body: StartCodeIssueRequest, key: IdempotencyKey, who: authn.Staff
    ) -> JSONResponse:
        questionnaire = body.questionnaire_id.root if body.questionnaire_id is not None else None
        for _ in range(MAX_CODE_ATTEMPTS):
            try:
                async with rt.store.transaction() as tx:
                    if questionnaire is not None and await tx.active_question_set(questionnaire) is None:
                        raise ApiError(400, errors=[("/questionnaire_id", "활성 문항 세트가 없는 문진표다")])
                    record = start_code.issue(
                        code=start_code.new_code(),
                        subject_ref=body.subject_ref.root,
                        questionnaire_id=questionnaire,
                        issued_by=who.subject,
                        now=rt.now(),
                        ttl_seconds=rt.limits.start_code_ttl_seconds,
                    )
                    issued = await tx.issue_start_code(record, str(key))
                    await tx.log_event("start_code_issued", None, rt.now(), {"issued_by": who.subject})
            except DuplicateError:
                continue
            body_out: dict[str, object] = {
                "code": issued.code,
                "issued_at": issued.issued_at.isoformat(),
                "expires_at": issued.expires_at.isoformat(),
            }
            if issued.questionnaire_id is not None:
                body_out["questionnaire_id"] = issued.questionnaire_id
            return JSONResponse(body_out, status_code=201)
        raise ApiError(503, retry_after=rt.limits.retry_after_seconds)

    # ------------------------------------------------------------ 개입
    @api.post("/v1/sessions/{session_id}/intervention", tags=["staff"])
    async def decide_intervention(  # pyright: ignore[reportUnusedFunction]
        session_id: UUID, body: InterventionDecision, who: authn.Staff
    ) -> JSONResponse:
        async with rt.store.transaction() as tx:
            current = await tx.get_session(session_id, for_update=True)
            if current is None:
                raise ApiError(404)
            updated = current
            if body.action is InterventionAction.RESUME:
                if current.status in session.ENDED:
                    raise ApiError(
                        409, reason=ProblemReason.SESSION_NOT_ACTIVE, retry_after=rt.limits.retry_after_seconds
                    )
                if current.status is SessionStatus.PAUSED:
                    updated = session.resume(current, rt.now())
                    await tx.save_session(updated)
            await tx.resolve_alerts(session_id, alert.STAFF_KINDS, who.subject, rt.now())
            await tx.log_event("intervention", session_id, rt.now(), {"action": body.action.value, "by": who.subject})
            state: dict[str, object] = {"session_id": str(session_id), "status": updated.status.value}
            if updated.pause_reason is not None:
                state["pause_reason"] = updated.pause_reason.value
            if updated.resume_pending and updated.status is SessionStatus.ACTIVE:
                stored = await tx.get_question_set(updated.question_set_version_id)
                if stored is not None:
                    state["resume_text"] = turn.resume_text(content_of(stored), updated.current_item_id)
        return JSONResponse(state)

    # ------------------------------------------------------------ 알림
    @api.get("/v1/staff-alerts", tags=["staff"])
    async def list_staff_alerts(
        who: authn.StaffOrClinician, limit: LimitQuery = 30, cursor: CursorQuery = None
    ) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        try:
            async with rt.store.transaction() as tx:
                page = await tx.list_alerts(alert.kinds_for(who.roles), limit, cursor)
        except InvalidCursorError as error:
            raise invalid_cursor() from error
        body: dict[str, object] = {
            "items": [alert.to_contract(a).model_dump(mode="json", exclude_none=True) for a in page.items]
        }
        if page.next_cursor is not None:
            body["next_cursor"] = page.next_cursor
        return JSONResponse(body)

    @api.get("/v1/staff-alerts/stream", tags=["staff"])
    async def stream_staff_alerts(who: authn.StaffOrClinician, last_event_id: LastEventId = None) -> StreamingResponse:  # pyright: ignore[reportUnusedFunction]
        kinds = alert.kinds_for(who.roles)

        def marker(name: str, sequence: int) -> str:
            """alert 가 없는 이벤트(heartbeat, resync)의 data. id 는 싣지 않아 재개 위치를 바꾸지 않는다(D87)."""
            return StaffAlertEvent.model_validate({"event": name, "sequence": sequence}).model_dump_json(
                exclude_none=True
            )

        async def frames() -> AsyncIterator[str]:
            async with rt.store.transaction() as tx:
                latest = await tx.latest_alert_sequence()
            position = latest
            if last_event_id is not None:
                if last_event_id > latest:
                    # 왜 resync: 서버가 모르는 순번이다(복구 등으로 순번이 되돌아갔다). 화면이 목록을 다시 읽어야 한다
                    yield alert.sse_frame(AlertEventName.resync, marker("resync", latest), None)
                else:
                    position = last_event_id
            idle = 0.0
            while True:
                async with rt.store.transaction() as tx:
                    events = await tx.alert_events_after(position, kinds, STREAM_BATCH)
                    latest = await tx.latest_alert_sequence()
                for event in events:
                    position = event.sequence
                    body = alert.event_body(event).model_dump_json(exclude_none=True)
                    yield alert.sse_frame(AlertEventName(event.event), body, event.sequence)
                    idle = 0.0
                if not events:
                    await asyncio.sleep(STREAM_POLL_SECONDS)
                    idle += STREAM_POLL_SECONDS
                    if idle >= rt.limits.heartbeat_seconds:
                        yield alert.sse_frame(AlertEventName.heartbeat, marker("heartbeat", position), None)
                        idle = 0.0

        return StreamingResponse(frames(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    # ------------------------------------------------------------ 푸시
    @api.get("/v1/push-config", tags=["push"])
    async def get_push_config(_who: authn.StaffOrClinician) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return reply(PushConfig.model_validate({"vapid_public_key": rt.vapid_public_key}))

    @api.post("/v1/push-subscriptions", tags=["push"])
    async def register_push_subscription(body: PushSubscription, who: authn.StaffOrClinician) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            ident, at = await tx.save_push_subscription(who.subject, alert.kinds_for(who.roles), body, rt.now())
        return JSONResponse({"push_subscription_id": str(ident), "registered_at": at.isoformat()}, status_code=201)

    # ------------------------------------------------------------ 문항 세트
    @api.post("/v1/question-set-versions", tags=["question-sets"])
    async def upload_question_set(body: QuestionSetUpload, key: IdempotencyKey, who: authn.Author) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        problems = question_bank.validate(body.content)
        if problems:
            raise ApiError(400, errors=[(p.pointer, p.detail) for p in problems])
        value = StoredQuestionSet(
            question_set_version_id=rt.new_id(),
            questionnaire_id=body.questionnaire_id.root,
            version_number=1,
            runtime_contract_version=body.runtime_contract_version.root,
            content=body.content.model_dump(mode="json", exclude_none=True),
            content_hash=question_bank.content_hash(body.content),
            uploaded_by=who.subject,
            created_at=rt.now(),
        )
        async with rt.store.transaction() as tx:
            stored = await tx.save_question_set(value, str(key))
            await tx.log_event("question_set_uploaded", None, rt.now(), {"questionnaire_id": stored.questionnaire_id})
        return reply(_version_body(stored), 201)

    @api.get("/v1/question-set-versions", tags=["question-sets"])
    async def list_question_set_versions(  # pyright: ignore[reportUnusedFunction]
        _who: authn.Author, limit: LimitQuery = 30, cursor: CursorQuery = None, questionnaire_id: str | None = None
    ) -> JSONResponse:
        try:
            async with rt.store.transaction() as tx:
                page = await tx.list_question_sets(questionnaire_id, limit, cursor)
        except InvalidCursorError as error:
            raise invalid_cursor() from error
        body: dict[str, object] = {
            "items": [_version_body(s).model_dump(mode="json", exclude_none=True) for s in page.items]
        }
        if page.next_cursor is not None:
            body["next_cursor"] = page.next_cursor
        return JSONResponse(body)

    @api.get("/v1/question-set-versions/{question_set_version_id}", tags=["question-sets"])
    async def get_question_set_version(question_set_version_id: UUID, _who: authn.Author) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            stored = await tx.get_question_set(question_set_version_id)
        if stored is None:
            raise ApiError(404)
        return reply(_version_body(stored))

    @api.post("/v1/question-set-versions/{question_set_version_id}/activation", tags=["question-sets"])
    async def activate_question_set(question_set_version_id: UUID, who: authn.Author) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            stored = await tx.get_question_set(question_set_version_id)
            if stored is None:
                raise ApiError(404)
            active = await tx.activate_question_set(stored, who.subject, rt.now())
            await tx.log_event("question_set_activated", None, rt.now(), {"questionnaire_id": stored.questionnaire_id})
        return reply(active)

    # ------------------------------------------------------------ 실패 사례
    @api.get("/v1/cases", tags=["failure-cases"])
    async def list_failure_cases(  # pyright: ignore[reportUnusedFunction]
        _who: authn.Reviewer,
        limit: LimitQuery = 30,
        cursor: CursorQuery = None,
        review_status: ReviewStatus | None = None,
        questionnaire_id: str | None = None,
    ) -> JSONResponse:
        try:
            async with rt.store.transaction() as tx:
                page = await tx.list_cases(review_status, questionnaire_id, limit, cursor)
        except InvalidCursorError as error:
            raise invalid_cursor() from error
        body: dict[str, object] = {
            "items": [failure_case.to_case(c).model_dump(mode="json", exclude_none=True) for c in page.items]
        }
        if page.next_cursor is not None:
            body["next_cursor"] = page.next_cursor
        return JSONResponse(body)

    @api.get("/v1/case-exports", tags=["failure-cases"])
    async def list_failure_case_exports(  # pyright: ignore[reportUnusedFunction]
        _who: authn.CaseReader,
        limit: LimitQuery = 30,
        cursor: CursorQuery = None,
        review_status: ReviewStatus | None = None,
        questionnaire_id: str | None = None,
    ) -> JSONResponse:
        # 왜 CONFIRMED 로 고정하나: 내보내는 것은 검토를 마쳐 실패로 확정한 사례뿐이다(N09). 다른 상태를
        # 달라고 하면 빈 쪽이다
        if review_status is not None and review_status is not ReviewStatus.CONFIRMED:
            return JSONResponse({"items": []})
        try:
            async with rt.store.transaction() as tx:
                page = await tx.list_cases(ReviewStatus.CONFIRMED, questionnaire_id, limit, cursor)
        except InvalidCursorError as error:
            raise invalid_cursor() from error
        items = [
            failure_case.to_export(c).model_dump(mode="json", exclude_none=True)
            for c in page.items
            if failure_case.exportable(c)
        ]
        body: dict[str, object] = {"items": items}
        if page.next_cursor is not None:
            body["next_cursor"] = page.next_cursor
        return JSONResponse(body)

    @api.get("/v1/cases/{case_id}", tags=["failure-cases"])
    async def get_failure_case(case_id: UUID, _who: authn.Reviewer) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            found = await tx.get_case(case_id)
        if found is None:
            raise ApiError(404)
        return reply(failure_case.to_case(found))

    @api.post("/v1/cases/{case_id}/reviews", tags=["failure-cases"])
    async def review_failure_case(case_id: UUID, body: CaseReview, who: authn.Reviewer) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            found = await tx.get_case(case_id)
            if found is None:
                raise ApiError(404)
            decision = failure_case.review(found, body, who.subject, rt.now())
            if decision.verdict is ReviewVerdict.VERSION_MISMATCH:
                raise ApiError(
                    409, reason=ProblemReason.CASE_VERSION_MISMATCH, retry_after=rt.limits.retry_after_seconds
                )
            if decision.verdict is ReviewVerdict.UNCHANGED or decision.next is None:
                return reply(failure_case.to_case(found), 200)
            await tx.save_case_version(decision.next, body)
            await tx.log_event("case_reviewed", None, rt.now(), {"case_id": str(case_id), "by": who.subject})
        return reply(failure_case.to_case(decision.next), 201)

    @api.get("/v1/deidentified-traces/{case_id}", tags=["failure-cases"])
    async def get_deidentified_trace(case_id: UUID, _who: authn.Reviewer) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            found = await tx.get_case(case_id)
        if found is None:
            raise ApiError(404)
        return reply(failure_case.to_trace(found))

    return api
