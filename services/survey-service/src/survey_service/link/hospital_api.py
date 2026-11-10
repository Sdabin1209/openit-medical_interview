"""link_hospital_api: 결과를 당겨 가는 HTTP 서버(목록, 상세, FHIR R4 QuestionnaireResponse, 확인 표시).

병원 시스템(기계 토큰 result-reader)과 의사(OIDC clinician)가 읽는다. 밀어 보내기는 없다(C10).
읽은 사람과 때를 영역 안 접근 기록에 남긴다(U35). FHIR 조회의 오류만 OperationOutcome 이다.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from survey_service.components import result
from survey_service.contract.models import ResultAcknowledgement, SessionStatus
from survey_service.link import auth as authn
from survey_service.link.common import CursorQuery, LimitQuery, content_of, invalid_cursor, reply
from survey_service.link.problem import ApiError
from survey_service.types import InvalidCursorError, Principal, Runtime, SessionRecord, Tx

FHIR_JSON = "application/fhir+json"


def router(rt: Runtime) -> APIRouter:
    """결과 경로 넷."""
    api = APIRouter()

    async def read(
        tx: Tx, session_id: UUID, who: Principal, *, fhir: bool
    ) -> tuple[SessionRecord, result.SessionResult]:
        found = await tx.get_session(session_id)
        stored = await tx.get_question_set(found.question_set_version_id) if found is not None else None
        if found is None or stored is None:
            raise ApiError(404, fhir=fhir)
        await tx.log_result_access(session_id, who.kind.value, who.subject, rt.now())
        built = result.assemble(found, content_of(stored), await tx.get_acknowledgement(session_id))
        return found, built

    @api.get("/v1/results", tags=["results"])
    async def list_results(  # pyright: ignore[reportUnusedFunction]
        _who: authn.ClinicianOrReader,
        limit: LimitQuery = 30,
        cursor: CursorQuery = None,
        subject_ref: str | None = None,
        status: SessionStatus | None = None,
    ) -> JSONResponse:
        try:
            async with rt.store.transaction() as tx:
                page = await tx.list_results(subject_ref, status, limit, cursor)
                items: list[dict[str, object]] = []
                for found in page.items:
                    stored = await tx.get_question_set(found.question_set_version_id)
                    title = content_of(stored).title.root if stored is not None else None
                    summary = result.summary(found, title, await tx.get_acknowledgement(found.session_id))
                    items.append(summary.model_dump(mode="json", exclude_none=True))
        except InvalidCursorError as error:
            raise invalid_cursor() from error
        body: dict[str, object] = {"items": items}
        if page.next_cursor is not None:
            body["next_cursor"] = page.next_cursor
        return JSONResponse(body)

    @api.get("/v1/results/{session_id}", tags=["results"])
    async def get_result(session_id: UUID, who: authn.ClinicianOrReader) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            _found, built = await read(tx, session_id, who, fhir=False)
        return reply(built)

    @api.get("/v1/results/{session_id}/fhir", tags=["results"])
    async def get_result_fhir(session_id: UUID, who: authn.ClinicianOrReader) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            found, built = await read(tx, session_id, who, fhir=True)
            stored = await tx.get_question_set(found.question_set_version_id)
        if stored is None:
            raise ApiError(404, fhir=True)
        fhir = result.to_fhir(built, content_of(stored), rt.fhir_canonical_base_url)
        return JSONResponse(fhir, media_type=FHIR_JSON)

    @api.post("/v1/results/{session_id}/acknowledgements", tags=["results"])
    async def acknowledge_result(session_id: UUID, who: authn.Clinician) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        async with rt.store.transaction() as tx:
            if await tx.get_session(session_id) is None:
                raise ApiError(404)
            by, at = await tx.acknowledge(session_id, who.subject, rt.now())
            await tx.log_event("result_acknowledged", session_id, rt.now(), {"by": by})
        return reply(
            ResultAcknowledgement.model_validate(
                {"session_id": str(session_id), "acknowledged_by": by, "acknowledged_at": at.isoformat()}
            )
        )

    return api
