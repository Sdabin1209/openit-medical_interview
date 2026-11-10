"""/healthz(살아 있음)와 /readyz(의존 준비됨). ADR 0004, 12-Factor 관례."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

ReadinessCheck = Callable[[], Awaitable[bool]]


class Healthz(BaseModel):
    """살아 있음 응답."""

    status: Literal["ok"] = Field(description="프로세스가 요청을 받을 수 있으면 ok.")


class Readyz(BaseModel):
    """준비됨 응답. 비밀·연결 문자열 등 값은 넣지 않고 점검 이름만 낸다."""

    status: Literal["ready", "not_ready"] = Field(description="모든 의존이 준비되면 ready.")
    failed: list[str] = Field(description="준비되지 않은 점검의 이름 목록. 준비됐으면 빈 목록.")


def health_router(checks: Mapping[str, ReadinessCheck]) -> APIRouter:
    """점검 이름 -> 비동기 점검 함수 목록으로 상태 라우터를 만든다."""
    router = APIRouter()

    @router.get("/healthz", response_model=Healthz, tags=["health"])
    async def healthz() -> Healthz:  # pyright: ignore[reportUnusedFunction]
        return Healthz(status="ok")

    @router.get(
        "/readyz",
        response_model=Readyz,
        responses={503: {"model": Readyz, "description": "의존이 준비되지 않음"}},
        tags=["health"],
    )
    async def readyz(response: Response) -> Readyz:  # pyright: ignore[reportUnusedFunction]
        failed: list[str] = []
        for name, check in checks.items():
            try:
                ok = await check()
            except Exception:  # 왜: 점검이 던진 예외 내용(연결 문자열 등)을 응답에 싣지 않는다
                ok = False
            if not ok:
                failed.append(name)
        if failed:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return Readyz(status="not_ready", failed=failed)
        return Readyz(status="ready", failed=[])

    return router
