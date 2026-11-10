"""/healthz(살아 있음), /readyz(의존 준비됨), /metrics(지표). 본문은 계약이다(HealthReport, ProblemDetails, D111)."""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from __PKG__.contract.models import HealthReport, ProblemDetails, ServiceName

ReadinessCheck = Callable[[], Awaitable[bool]]

# 왜 5: 계약 RetryAfterSeconds 의 예시 값(examples: [5])이다. 측정으로 정한 값이 아니며 영역이 측정해 바꾼다
RETRY_AFTER_SECONDS = 5
PROBLEM_JSON = "application/problem+json"


def _report(service: ServiceName, checks: list[dict[str, str]] | None) -> HealthReport:
    body: dict[str, object] = {"status": "pass", "service": service.value}
    if checks is not None:
        body["checks"] = checks
    return HealthReport.model_validate(body)


def health_router(service: ServiceName, checks: Mapping[str, ReadinessCheck]) -> APIRouter:
    """점검 이름 -> 비동기 점검 함수 목록으로 상태 라우터를 만든다."""
    router = APIRouter()

    @router.get("/healthz", response_model=HealthReport, response_model_exclude_none=True, tags=["health"])
    async def healthz() -> HealthReport:  # pyright: ignore[reportUnusedFunction]
        return _report(service, None)

    @router.get("/readyz", response_model=HealthReport, response_model_exclude_none=True, tags=["health"])
    async def readyz(request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        failed: list[str] = []
        for name, check in checks.items():
            try:
                ok = await check()
            except Exception:  # 왜: 점검이 던진 예외 내용(연결 문자열 등)을 응답에 싣지 않는다
                ok = False
            if not ok:
                failed.append(name)
        if failed:
            problem = ProblemDetails.model_validate(
                {
                    "type": "about:blank",
                    "title": "의존이 준비되지 않았다",
                    "status": 503,
                    # 왜 이름만: 연결 문자열·비밀이 새지 않게 점검 이름만 낸다
                    "detail": "준비되지 않은 점검: " + ", ".join(failed),
                    "instance": request.url.path,
                }
            )
            return JSONResponse(
                problem.model_dump(mode="json", exclude_none=True),
                status_code=503,
                media_type=PROBLEM_JSON,
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            )
        report = _report(service, [{"name": name, "status": "pass"} for name in checks])
        return JSONResponse(report.model_dump(mode="json", exclude_none=True))

    @router.get("/metrics", response_class=Response, tags=["health"])
    async def metrics() -> Response:  # pyright: ignore[reportUnusedFunction]
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return router
