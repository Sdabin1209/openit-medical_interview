"""오류 응답: 모든 오류는 RFC 9457 Problem Details(application/problem+json)다. FHIR 조회만 OperationOutcome.

상태 코드는 RFC 9110 의 뜻을 따르고 상태 코드로 가를 수 없는 사유는 reason 이다(계약 ProblemReason).
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from survey_service.contract.models import ProblemDetails, ProblemReason

PROBLEM_JSON = "application/problem+json"
FHIR_JSON = "application/fhir+json"
_TITLES = {
    400: "요청이 계약과 맞지 않다",
    401: "인증이 필요하거나 틀렸다",
    403: "권한이 없다",
    404: "대상이 없다",
    405: "허용하지 않는 방법이다",
    409: "지금 상태와 충돌한다",
    422: "값을 처리할 수 없다",
    429: "시도가 너무 잦다",
    503: "지금은 처리할 수 없다",
}


class ApiError(Exception):
    """계약이 정의한 오류 응답 하나. 처리기가 problem+json 으로 바꾼다."""

    def __init__(
        self,
        status: int,
        *,
        reason: ProblemReason | None = None,
        detail: str | None = None,
        retry_after: int | None = None,
        authenticate: str | None = None,
        errors: list[tuple[str, str]] | None = None,
        fhir: bool = False,
    ) -> None:
        super().__init__(f"{status} {reason.value if reason else ''}")
        self.status, self.reason, self.detail = status, reason, detail
        self.retry_after, self.authenticate, self.errors, self.fhir = retry_after, authenticate, errors, fhir


def problem_body(
    status: int,
    instance: str,
    *,
    reason: ProblemReason | None,
    detail: str | None,
    errors: list[tuple[str, str]] | None,
) -> dict[str, object]:
    """ProblemDetails 본문. 환자 발화와 비밀 값은 넣지 않는다."""
    body: dict[str, object] = {
        "type": f"https://openit/problems/{reason.value}" if reason is not None else "about:blank",
        "title": _TITLES.get(status, "오류"),
        "status": status,
        "instance": instance[:8000],
    }
    if reason is not None:
        body["reason"] = reason.value
    if detail is not None:
        body["detail"] = detail[:4000]
    if errors:
        body["errors"] = [{"pointer": pointer, "detail": why[:4000]} for pointer, why in errors[:100]]
    return ProblemDetails.model_validate(body).model_dump(mode="json", exclude_none=True)


def _fhir_body(status: int) -> dict[str, object]:
    code = {401: "login", 403: "forbidden", 404: "not-found"}.get(status, "transient")
    return {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": code}]}


def respond(error: ApiError, instance: str) -> JSONResponse:
    """ApiError 를 계약의 오류 응답으로."""
    headers: dict[str, str] = {}
    if error.retry_after is not None:
        headers["Retry-After"] = str(error.retry_after)
    if error.authenticate is not None:
        headers["WWW-Authenticate"] = error.authenticate
    if error.fhir or instance.endswith("/fhir"):
        return JSONResponse(_fhir_body(error.status), error.status, headers, media_type=FHIR_JSON)
    body = problem_body(error.status, instance, reason=error.reason, detail=error.detail, errors=error.errors)
    return JSONResponse(body, error.status, headers, media_type=PROBLEM_JSON)


def install(app: FastAPI) -> None:
    """오류 처리기를 건다. 요청 검증 실패는 400(경로의 식별자가 틀리면 404), 모르는 경로는 404."""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, error: ApiError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return respond(error, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, error: RequestValidationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        fields: list[tuple[str, str]] = []
        in_path = False
        for item in error.errors():
            where = [str(x) for x in item["loc"]]
            in_path = in_path or where[0] == "path"
            fields.append(("/" + "/".join(where[1:] or where), str(item["msg"])))
        status = 404 if in_path else 400
        fhir = request.url.path.endswith("/fhir")
        return respond(ApiError(status, errors=None if status == 404 else fields, fhir=fhir), request.url.path)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, error: StarletteHTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return respond(ApiError(error.status_code, detail=None), request.url.path)
