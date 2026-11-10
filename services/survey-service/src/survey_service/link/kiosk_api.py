"""link_kiosk_api: 키오스크 요청을 받는 HTTP 서버(시작 코드 확인, 세션 시작, 턴, 종료, 상태, 직원 호출).

기기는 mTLS 로 인증되고 게이트웨이가 넘긴 X-Forwarded-Client-Cert 의 CN 이 기기 ID 다. 세션은 시작한 기기만 닿고
다른 기기에는 404 로 존재를 숨긴다(D88 U8). 턴은 같은 turn_id 의 재전송에 같은 결과를 준다(멱등).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from prometheus_client import Histogram

from survey_service.components import alert, question_bank, session, start_code, trace, turn
from survey_service.contract.models import (
    ActionExtraction,
    AlertKind,
    PauseReason,
    ProblemReason,
    QuestionSetContent,
    SessionStartRequest,
    SessionStatus,
    TurnFailureReason,
    TurnRequest,
)
from survey_service.link import auth as authn
from survey_service.link.common import content_of, reply
from survey_service.link.problem import ApiError
from survey_service.types import (
    ModelCallError,
    ModelCallFailure,
    Runtime,
    SessionRecord,
    SlotValue,
    StartCodeVerdict,
    TurnOutcome,
    Tx,
)

# 왜 이 지표: 계약 RequiredPrometheusMetric(turn_duration_seconds). 환자 턴 처리 시간 히스토그램(초, 목표
# 2초 p95 경보의 근거)
TURN_SECONDS = Histogram("turn_duration_seconds", "환자 턴 처리 시간(초)")
# 왜 120: 계약 RetryAfterSeconds 의 최대(Retry-After 로 알릴 수 있는 초의 상한)
MAX_RETRY_AFTER_SECONDS = 120


async def call_twice[T](make: Callable[[], Awaitable[T]]) -> T:
    """같은 요청을 1회 재시도한다(출력 불가는 같은 요청 1회 재시도 뒤 실패 신호, D75). 시간 초과는 다시
    보내지 않는다."""
    try:
        return await make()
    except ModelCallError as error:
        if error.failure is ModelCallFailure.DEADLINE:
            raise
    return await make()


def router(rt: Runtime) -> APIRouter:
    """키오스크 경로 여섯 개(listActiveQuestionnaires 는 직원도 읽는다)."""
    api = APIRouter()

    # ------------------------------------------------------------ 도구
    async def load_owned(tx: Tx, session_id: UUID, device_id: str, *, lock: bool = False) -> SessionRecord:
        found = await tx.get_session(session_id, for_update=lock)
        if found is None or found.device_id != device_id:
            raise ApiError(404)  # 왜 같은 404: 다른 기기의 세션 존재를 숨긴다(D88 U8)
        return found

    async def expire(tx: Tx, current: SessionRecord) -> SessionRecord:
        refreshed = session.expire_if_idle(current, rt.now(), rt.limits.idle_seconds)
        if refreshed is not current:
            await tx.save_session(refreshed)
            await tx.log_event("session_expired", refreshed.session_id, rt.now(), {})
            # 왜 알리나: 유휴로 만료된 문진도 결과(부분 결과)가 생긴다. 의사가 볼 수 있게 결과 도착 알림을 낸다
            await raise_result_ready(tx, refreshed, content_of_title(await content_for(tx, refreshed)))
        return refreshed

    async def touch(tx: Tx, current: SessionRecord) -> SessionRecord:
        """활동(startSession·submitTurn·requestStaffCall)의 시각을 남긴다(유휴 만료의 기준, KioskIdleResetSeconds)."""
        touched = current.model_copy(update={"last_activity_at": rt.now()})
        await tx.save_session(touched)
        return touched

    async def content_for(tx: Tx, current: SessionRecord) -> QuestionSetContent:
        stored = await tx.get_question_set(current.question_set_version_id)
        if stored is None:  # 왜 일어날 수 없나: 세션이 가리키는 버전은 지우지 않는다(한 번 저장하면 바뀌지 않는다)
            raise ApiError(503, retry_after=rt.limits.retry_after_seconds)
        return content_of(stored)

    async def push(alert_id: UUID, kind: AlertKind) -> None:
        """알림을 푸시로 보낸다(저장을 커밋한 뒤). 푸시 서비스가 지운 구독은 정리한다."""
        async with rt.store.transaction() as tx:
            record = await tx.get_alert(alert_id)
            subs = await tx.push_subscriptions_for(kind)
        if record is None or not subs:
            return
        gone = await rt.notifier.push(record, subs)
        if gone:
            async with rt.store.transaction() as tx:
                for endpoint in gone:
                    await tx.delete_push_subscription(endpoint)

    async def raise_result_ready(tx: Tx, ended: SessionRecord, title: str | None) -> UUID | None:
        created, fresh = await tx.create_alert(alert.result_ready(ended, rt.new_id(), rt.now(), title))
        return created.alert_id if fresh else None

    def answers_of(current: SessionRecord) -> dict[str, SlotValue]:
        return {key: a.value for key, a in current.answers.items() if a.status == "ANSWERED"}

    def started_body(started: SessionRecord, content: QuestionSetContent) -> JSONResponse:
        body: dict[str, object] = {
            "session_id": str(started.session_id),
            "questionnaire_id": started.questionnaire_id,
            "questionnaire_title": content.title.root,
            "response_text": started.last_assistant_text,
            "status": started.status.value,
        }
        if started.current_item_id is not None:
            body["current_item_id"] = started.current_item_id
        return JSONResponse(body, status_code=200)

    # ------------------------------------------------------------ 문진표 목록
    @api.get("/v1/questionnaires", tags=["questionnaires"])
    async def list_active_questionnaires(_who: authn.DeviceOrStaff) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            active = await tx.list_active_questionnaires()
        items = [{"questionnaire_id": s.questionnaire_id, "title": content_of(s).title.root} for s in active]
        return JSONResponse({"questionnaires": items})

    # ------------------------------------------------------------ 세션 시작
    @api.post("/v1/sessions", tags=["sessions"])
    async def start_session(body: SessionStartRequest, who: authn.Device) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        now = rt.now()
        window_start = now - timedelta(seconds=rt.limits.start_failure_window_seconds)

        async def fail(error: ApiError) -> ApiError:
            async with rt.store.transaction() as tx:
                await tx.record_start_failure(who.subject, rt.now())
            return error

        async with rt.store.transaction() as tx:
            if await tx.count_start_failures(who.subject, window_start) >= rt.limits.start_failure_limit:
                raise ApiError(429, retry_after=min(rt.limits.start_failure_window_seconds, MAX_RETRY_AFTER_SECONDS))
            code = body.start_code.root
            record = await tx.get_start_code(code)
            verdict = start_code.evaluate(record, who.subject, now)
            if verdict is StartCodeVerdict.REPLAY and record is not None and record.used_session_id is not None:
                previous = await tx.get_session(record.used_session_id)
                if previous is not None:
                    return started_body(previous, await content_for(tx, previous))
        if verdict is not StartCodeVerdict.OK or record is None:
            if verdict is StartCodeVerdict.INVALID:
                raise await fail(ApiError(422, reason=ProblemReason.START_CODE_INVALID))
            if verdict is StartCodeVerdict.EXPIRED:
                raise await fail(ApiError(409, reason=ProblemReason.START_CODE_EXPIRED))
            raise await fail(ApiError(409, reason=ProblemReason.START_CODE_USED))
        # 문진표는 시작 코드에 묶인 것, 없으면 요청의 것, 없으면 기기 배치표의 것, 모두 없으면 활성이 하나일 때 그것이다
        async with rt.store.transaction() as tx:
            wanted = record.questionnaire_id or (body.questionnaire_id.root if body.questionnaire_id else None)
            wanted = wanted or rt.device_placements.get(who.subject)
            if wanted is None:
                active = await tx.list_active_questionnaires()
                if not active:
                    raise ApiError(503, retry_after=rt.limits.retry_after_seconds)
                if len(active) != 1:
                    # 왜 422 이고 코드를 쓰지 않음: 계약 startSession. 키오스크가 고른 값을 더해 같은 코드로 다시 보낸다
                    raise ApiError(422, reason=ProblemReason.QUESTIONNAIRE_REQUIRED)
                wanted = next(iter(active)).questionnaire_id
            stored = await tx.active_question_set(wanted)
        if stored is None:
            raise ApiError(400, errors=[("/questionnaire_id", "활성 문항 세트가 없는 문진표다")])
        content = content_of(stored)
        first = content.flow.start_item.root
        version = await rt.model.model_io_version()
        try:
            async with asyncio.timeout(rt.limits.turn_seconds):
                greeted = await call_twice(
                    lambda: rt.model.respond(
                        turn.start_response_request(content, first, stored.runtime_contract_version)
                    )
                )
        except (ModelCallError, TimeoutError) as error:
            raise ApiError(
                503, reason=ProblemReason.DEADLINE_EXCEEDED, retry_after=rt.limits.retry_after_seconds
            ) from error
        async with rt.store.transaction() as tx:
            latest = await tx.get_start_code(code, for_update=True)
            if start_code.evaluate(latest, who.subject, rt.now()) is not StartCodeVerdict.OK:
                raise ApiError(409, reason=ProblemReason.START_CODE_USED)
            started = session.start(
                session_id=rt.new_id(),
                device_id=who.subject,
                subject_ref=record.subject_ref,
                questionnaire_id=stored.questionnaire_id,
                question_set_version_id=stored.question_set_version_id,
                runtime_contract_version=stored.runtime_contract_version,
                first_item_id=first,
                greeting=greeted.text.root,
                model_io_version=version,
                now=rt.now(),
            )
            await tx.create_session(started)
            await tx.mark_start_code_used(code, who.subject, started.session_id)
            await tx.log_event("session_started", started.session_id, rt.now(), {"device_id": who.subject})
        response = started_body(started, content)
        response.status_code = 201
        return response

    # ------------------------------------------------------------ 턴
    @api.post("/v1/sessions/{session_id}/turns", tags=["sessions"])
    async def submit_turn(session_id: UUID, body: TurnRequest, who: authn.Device) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        began = time.monotonic()
        turn_id = body.turn_id.root
        utterance = body.utterance.root
        async with rt.store.transaction() as tx:
            current = await expire(tx, await load_owned(tx, session_id, who.subject, lock=True))
            if current.status is not SessionStatus.ACTIVE or current.current_item_id is None:
                raise ApiError(409, reason=ProblemReason.SESSION_NOT_ACTIVE, retry_after=rt.limits.retry_after_seconds)
            asked_item = current.current_item_id  # 왜 따로 두나: touch 가 만든 사본은 문항이 있다는 좁힘을 잃는다
            # 왜 touch: 만료 판정을 통과한 submitTurn 은 활동이다(계약). 실패 신호로 끝나도 활동이다
            current = await touch(tx, current)
            content = await content_for(tx, current)
            started = trace.begin(current, turn_id, utterance, rt.now())
            stale = rt.now() - timedelta(seconds=rt.limits.turn_seconds)
            existing = await tx.begin_turn(started, stale)
            if existing is not None:
                if existing.outcome is TurnOutcome.DONE and existing.response is not None:
                    return JSONResponse(existing.response)
                raise ApiError(409, reason=ProblemReason.TURN_IN_PROGRESS, retry_after=rt.limits.retry_after_seconds)

        extraction: ActionExtraction | None = None
        digest: str | None = None
        signal: TurnFailureReason | None = None
        text = ""
        transition = None
        try:
            async with asyncio.timeout(rt.limits.turn_seconds):
                signal = TurnFailureReason.EXTRACTION_UNAVAILABLE
                extracted = await call_twice(
                    lambda: rt.model.extract(turn.extraction_request(current, content, utterance))
                )
                extraction, digest = extracted.output, extracted.package_digest.root
                skip_target = question_bank.next_after(content, asked_item, answers_of(current))
                transition = session.apply_extraction(
                    current, extraction, skip_target=skip_target, reask_limit=rt.limits.reask_limit, now=rt.now()
                )
                if transition.limit_skip:
                    text = turn.limit_skip_text(content, transition.next_item_id)
                else:
                    signal = TurnFailureReason.RESPONSE_UNAVAILABLE
                    request = turn.response_request(
                        session=current,
                        content=content,
                        extraction=extraction,
                        transition=transition,
                        utterance=utterance,
                    )
                    text = (await call_twice(lambda: rt.model.respond(request))).text.root
                signal = None
        except ModelCallError as error:
            if error.failure is ModelCallFailure.DEADLINE:
                signal = TurnFailureReason.DEADLINE_EXCEEDED
        except TimeoutError:
            signal = TurnFailureReason.DEADLINE_EXCEEDED

        ready_alert: UUID | None = None
        async with rt.store.transaction() as tx:
            latest = await load_owned(tx, session_id, who.subject, lock=True)
            if latest.status is not SessionStatus.ACTIVE or latest.last_activity_at != current.last_activity_at:
                # 왜 버리나: 모델을 부르는 동안 세션이 멈추거나 끝났다(위험 신호·직원 개입). 결과를 반영하지 않는다
                await tx.finish_turn(
                    trace.failed(
                        started,
                        signal=signal or TurnFailureReason.DEADLINE_EXCEEDED,
                        response={},
                        extraction=None,
                        package_digest=digest,
                        now=rt.now(),
                    ).model_copy(update={"failure_signal": None})
                )
                raise ApiError(409, reason=ProblemReason.SESSION_NOT_ACTIVE, retry_after=rt.limits.retry_after_seconds)
            if signal is not None or extraction is None or transition is None:
                failure = signal or TurnFailureReason.EXTRACTION_UNAVAILABLE
                failure_body: dict[str, object] = {
                    "turn_id": str(turn_id),
                    "status": latest.status.value,
                    "failure_signal": failure.value,
                    "current_item_id": latest.current_item_id,
                }
                failure_body = {k: v for k, v in failure_body.items() if v is not None}
                await tx.finish_turn(
                    trace.failed(
                        started,
                        signal=failure,
                        response=failure_body,
                        extraction=extraction,
                        package_digest=digest,
                        now=rt.now(),
                    )
                )
                await tx.log_event("turn_failed", session_id, rt.now(), {"signal": failure.value})
                TURN_SECONDS.observe(time.monotonic() - began)
                return JSONResponse(failure_body)
            updated = transition.session.model_copy(update={"last_assistant_text": text})
            response_body: dict[str, object] = {
                "turn_id": str(turn_id),
                "status": updated.status.value,
                "response_text": text,
            }
            if updated.current_item_id is not None:
                response_body["current_item_id"] = updated.current_item_id
            await tx.save_session(updated)
            await tx.finish_turn(
                trace.done(
                    started,
                    extraction=extraction,
                    response_text=text,
                    response=response_body,
                    package_digest=digest,
                    reask_limit_hit=transition.limit_skip,
                    now=rt.now(),
                )
            )
            await tx.log_event("turn_done", session_id, rt.now(), {"action": extraction.action.value})
            if updated.status is SessionStatus.ENDED_COMPLETE:
                ready_alert = await raise_result_ready(tx, updated, content.title.root)
        if ready_alert is not None:
            await push(ready_alert, AlertKind.RESULT_READY)
        TURN_SECONDS.observe(time.monotonic() - began)
        return JSONResponse(response_body)

    # ------------------------------------------------------------ 종료
    @api.post("/v1/sessions/{session_id}/end", tags=["sessions"])
    async def end_session(session_id: UUID, who: authn.Device) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        ready_alert: UUID | None = None
        async with rt.store.transaction() as tx:
            current = await expire(tx, await load_owned(tx, session_id, who.subject, lock=True))
            ended = session.end(current, rt.now())
            if ended is not current:
                await tx.save_session(ended)
                await tx.log_event("session_ended", session_id, rt.now(), {"status": ended.status.value})
                ready_alert = await raise_result_ready(tx, ended, content_of_title(await content_for(tx, ended)))
        if ready_alert is not None:
            await push(ready_alert, AlertKind.RESULT_READY)
        body: dict[str, object] = {"session_id": str(ended.session_id), "status": ended.status.value}
        body["ended_at"] = (ended.ended_at or rt.now()).isoformat()
        return JSONResponse(body)

    # ------------------------------------------------------------ 상태
    @api.get("/v1/sessions/{session_id}/state", tags=["sessions"])
    async def get_session_state(session_id: UUID, who: authn.Device) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            current = await expire(tx, await load_owned(tx, session_id, who.subject))
            body: dict[str, object] = {"session_id": str(current.session_id), "status": current.status.value}
            if current.pause_reason is not None:
                body["pause_reason"] = current.pause_reason.value
            if current.resume_pending and current.status is SessionStatus.ACTIVE:
                body["resume_text"] = turn.resume_text(await content_for(tx, current), current.current_item_id)
        return JSONResponse(body)

    # ------------------------------------------------------------ 직원 호출
    @api.post("/v1/sessions/{session_id}/staff-calls", tags=["sessions"])
    async def request_staff_call(session_id: UUID, who: authn.Device) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            current = await expire(tx, await load_owned(tx, session_id, who.subject, lock=True))
            if current.status not in (SessionStatus.ACTIVE, SessionStatus.PAUSED):
                raise ApiError(409, reason=ProblemReason.SESSION_NOT_ACTIVE, retry_after=rt.limits.retry_after_seconds)
            current = await touch(
                tx, current
            )  # 왜: requestStaffCall 은 세션의 활동이다(계약). 멈추면 멈춘 때가 새 기준이다
            open_call = await tx.open_alert(session_id, AlertKind.CALL_STAFF)
            if open_call is not None:
                created, fresh = open_call, False
            else:
                title = content_of_title(await content_for(tx, current))
                created, fresh = await tx.create_alert(alert.call_staff(current, rt.new_id(), rt.now(), title))
                if current.status is SessionStatus.ACTIVE:
                    await tx.save_session(session.pause(current, PauseReason.STAFF_CALL, rt.now()))
                await tx.log_event("staff_call", session_id, rt.now(), {})
        await push(created.alert_id, AlertKind.CALL_STAFF)
        return reply(alert.to_contract(created), 201 if fresh else 200)

    return api


def content_of_title(content: QuestionSetContent) -> str:
    """문항 세트의 제목."""
    return content.title.root
