"""link_risk_in: 외부 위험 감지기의 신호를 받는다(N14). 위험 감지는 기본 꺼짐(L11)이고 꺼져 있으면 403
RISK_DETECTION_DISABLED 다.

같은 세션·분류·감지 시각의 신호는 한 번만 처리한다(멱등, 멱등 키 헤더 불필요). 받으면 세션을 멈추고 직원 알림을 만든다.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from survey_service.components import alert, session
from survey_service.contract.models import AlertKind, PauseReason, ProblemReason, RiskSignal, SessionStatus
from survey_service.link import auth as authn
from survey_service.link.common import reply
from survey_service.link.problem import ApiError
from survey_service.types import Runtime


def router(rt: Runtime) -> APIRouter:
    """위험 신호 경로 하나."""
    api = APIRouter()

    @api.post("/v1/risk-signals", tags=["risk"])
    async def receive_risk_signal(body: RiskSignal, _who: authn.RiskDetector) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        if not rt.risk_detection_enabled:
            raise ApiError(403, reason=ProblemReason.RISK_DETECTION_DISABLED)
        session_id = body.session_id.root
        detected = body.detected_at.root
        key = f"risk:{session_id}:{body.category.value}:{detected.isoformat()}"
        async with rt.store.transaction() as tx:
            current = await tx.get_session(session_id, for_update=True)
            if current is None:
                raise ApiError(404)
            known = await tx.find_alert(key)
            if known is not None:
                return reply(alert.to_contract(known), 200)
            if current.status is not SessionStatus.ACTIVE:
                raise ApiError(409, reason=ProblemReason.SESSION_NOT_ACTIVE, retry_after=rt.limits.retry_after_seconds)
            stored = await tx.get_question_set(current.question_set_version_id)
            title = None if stored is None else str(stored.content.get("title", "")) or None
            record = alert.risk(current, body.category, detected, rt.new_id(), rt.now(), title)
            created, _fresh = await tx.create_alert(record)
            await tx.save_session(session.pause(current, PauseReason.RISK_SIGNAL, rt.now()))
            await tx.log_event("risk_signal", session_id, rt.now(), {"category": body.category.value})
        async with rt.store.transaction() as tx:
            subs = await tx.push_subscriptions_for(AlertKind.RISK)
        if subs:
            gone = await rt.notifier.push(created, subs)
            if gone:
                async with rt.store.transaction() as tx:
                    for endpoint in gone:
                        await tx.delete_push_subscription(endpoint)
        return reply(alert.to_contract(created), 201)

    return api
