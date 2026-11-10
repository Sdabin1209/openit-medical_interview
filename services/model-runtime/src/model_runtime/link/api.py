"""link_api: 추출·응답 문장·적재 상태·모델 패키지 읽기·활성화·롤백 요청을 받는 HTTP 서버(계약
openapi/model-runtime.yaml).

인증은 작업마다 계약의 security 요구를 따르고(401 은 틀림, 403 은 역할 없음), 오류는 모두 RFC 9457 problem+json 이다.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Header, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ValidationError

from model_runtime.contract.models import (
    ActivationRequest,
    ExtractionRequest,
    ProblemDetails,
    ResponseGenerationRequest,
    RollbackCommand,
)
from model_runtime.link.auth import Authenticator, forbidden, unauthorized
from model_runtime.link.runtime import Runtime
from model_runtime.types import ActivationOutcome, ServiceFault

PROBLEM_JSON = "application/problem+json"
_DIGEST_PATTERN = r"^sha256:[a-f0-9]{64}$"  # 계약 OciDigest 의 패턴(OCI Image Spec 1.1)
_MAX_ERRORS = 100  # 계약 ProblemFieldErrors 의 maxItems


def _problem(fault: ServiceFault, instance: str) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://openit/problems/{fault.reason.value}" if fault.reason else "about:blank",
        "title": fault.title,
        "status": fault.status,
        "detail": fault.detail,
        "instance": instance,
    }
    if fault.reason:
        body["reason"] = fault.reason.value
    if fault.errors:
        body["errors"] = fault.errors
    ProblemDetails.model_validate(body)  # 낸 값은 계약을 지킨다
    headers = dict(fault.headers)
    if fault.retry_after is not None:
        headers["Retry-After"] = str(fault.retry_after)
    return JSONResponse(body, status_code=fault.status, media_type=PROBLEM_JSON, headers=headers)


def _pointer(location: tuple[Any, ...]) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in location if part != "body"]
    return "/" + "/".join(parts) if parts else ""


def _validation_fault(error: ValidationError | RequestValidationError) -> ServiceFault:
    """요청이 계약을 어겼다(400). 어긋난 칸의 위치만 싣는다. 받은 값은 싣지 않는다(환자 발화가 들어 있을 수 있다)."""
    raw = error.errors(include_input=False) if isinstance(error, ValidationError) else error.errors()
    errors = [{"pointer": _pointer(tuple(item["loc"])), "detail": str(item["msg"])[:200]} for item in raw[:_MAX_ERRORS]]
    return ServiceFault(400, "요청이 계약을 어겼다", "요청의 칸이 계약과 다르다", errors=errors)


def install_error_handlers(app: FastAPI) -> None:
    """ServiceFault 와 검증 오류를 problem+json 으로 낸다."""

    @app.exception_handler(ServiceFault)
    async def on_fault(request: Request, fault: ServiceFault) -> Response:  # pyright: ignore[reportUnusedFunction]
        return _problem(fault, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def on_invalid(request: Request, error: RequestValidationError) -> Response:  # pyright: ignore[reportUnusedFunction]
        return _problem(_validation_fault(error), request.url.path)


async def _json_body(request: Request) -> Any:  # noqa: ANN401
    try:
        return json.loads(await request.body())
    except ValueError as error:
        raise ServiceFault(400, "요청이 계약을 어겼다", "본문이 JSON 이 아니다") from error


def _validated[T: BaseModel](model: type[T], raw: Any) -> T:  # noqa: ANN401
    """요청 본문이 계약 모델을 지키는지 본다. 어기면 400."""
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        raise _validation_fault(error) from error


def api_router(runtime: Runtime, auth: Authenticator) -> APIRouter:
    """계약의 작업 여섯 개."""
    router = APIRouter()

    @router.post("/v1/extractions", tags=["inference"])
    async def extract_action(request: Request, authorization: Annotated[str | None, Header()] = None) -> Response:  # pyright: ignore[reportUnusedFunction]
        await auth.require(authorization, machine_roles=["inference-caller"])
        raw = await _json_body(request)
        _validated(ExtractionRequest, raw)
        digest, output = await runtime.extract(raw)
        return JSONResponse({"package_digest": digest, "output": output})

    @router.post("/v1/responses", tags=["inference"])
    async def generate_response(request: Request, authorization: Annotated[str | None, Header()] = None) -> Response:  # pyright: ignore[reportUnusedFunction]
        await auth.require(authorization, machine_roles=["inference-caller"])
        raw = await _json_body(request)
        _validated(ResponseGenerationRequest, raw)
        digest, text = await runtime.respond(raw)
        return JSONResponse({"package_digest": digest, "text": text})

    @router.get("/v1/model-status", tags=["model"])
    async def get_model_status(authorization: Annotated[str | None, Header()] = None) -> Response:  # pyright: ignore[reportUnusedFunction]
        await auth.require(authorization, ["inference-caller"], ["operator", "release-approver"])
        return JSONResponse(runtime.status().model_dump(mode="json", exclude_none=True))

    @router.get("/v1/model-packages/{package_digest}", tags=["activation"])
    async def get_model_package(  # pyright: ignore[reportUnusedFunction]
        package_digest: Annotated[str, Path(pattern=_DIGEST_PATTERN)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        await auth.require(authorization, human_roles=["operator", "release-approver"])
        manifest = await runtime.describe(package_digest)
        return JSONResponse(manifest.model_dump(mode="json", exclude_none=True))

    @router.post("/v1/model-activations", tags=["activation"])
    async def activate_model_package(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        caller = await auth.require(authorization, human_roles=["release-approver"])
        command = _validated(ActivationRequest, await _json_body(request))
        outcome, status = await runtime.activate(
            command.package_digest.root, command.reason.root, caller.subject or caller.name
        )
        code = 200 if outcome is ActivationOutcome.ALREADY_ACTIVE else 202
        return JSONResponse(status.model_dump(mode="json", exclude_none=True), status_code=code)

    @router.post("/v1/model-rollbacks", tags=["activation"])
    async def rollback_model_package(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        caller = await auth.require(authorization, human_roles=["operator", "release-approver"])
        command = _validated(RollbackCommand, await _json_body(request))
        _, status = await runtime.rollback(
            command.target_package_digest.root, command.reason.root, caller.subject or caller.name
        )
        return JSONResponse(status.model_dump(mode="json", exclude_none=True), status_code=202)

    return router


__all__ = ["api_router", "forbidden", "install_error_handlers", "unauthorized"]
