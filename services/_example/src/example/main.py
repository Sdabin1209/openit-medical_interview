"""조립(의존 주입)과 진입점(ADR 0003). 설정은 환경 변수, 비밀은 파일에서만 읽는다(ADR 0004, 0005)."""

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from example.contract.models import ServiceName
from example.link.health import ReadinessCheck, health_router
from example.store.engine import check_database, make_engine


class SecretError(RuntimeError):
    """비밀을 읽지 못했다. 메시지에는 비밀 이름만 넣고 값과 경로는 넣지 않는다."""


def read_secret(name: str, environ: Mapping[str, str] | None = None) -> str:
    """환경 변수 `<name>_FILE` 이 가리키는 파일에서 비밀을 읽는다(D84).

    왜 파일만: 환경 변수는 프로세스 목록·`docker inspect`·자식 프로세스로 새 나간다.
    """
    env = os.environ if environ is None else environ
    path = env.get(f"{name}_FILE")
    if not path:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: {name}_FILE 이 설정되지 않았다")
    try:
        value = Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as error:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: 파일을 열지 못했다") from error
    if not value:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: 파일이 비어 있다")
    return value


class Settings(BaseSettings):
    """환경 변수 설정(12-Factor 3). 변수 이름은 `OPENIT_` 접두어를 쓴다."""

    model_config = SettingsConfigDict(env_prefix="OPENIT_", extra="ignore")

    service_name: ServiceName = Field(
        default=ServiceName("platform"), description="이 서비스의 이름. 건강 응답(HealthReport.service)에 실린다."
    )
    database_enabled: bool = Field(
        default=False,
        description="true 면 DATABASE_URL_FILE 의 연결 문자열로 DB 준비 점검을 /readyz 에 넣는다.",
    )


def create_app(settings: Settings | None = None, checks: Mapping[str, ReadinessCheck] | None = None) -> FastAPI:
    """앱 팩토리. `uvicorn --factory example.main:create_app` 으로 띄운다."""
    resolved = Settings() if settings is None else settings
    readiness: dict[str, ReadinessCheck] = dict(checks or {})
    if resolved.database_enabled:
        engine = make_engine(read_secret("DATABASE_URL"))

        async def database() -> bool:
            return await check_database(engine)

        readiness["database"] = database
    app = FastAPI(title=resolved.service_name.value)
    app.include_router(health_router(resolved.service_name, readiness))
    return app
