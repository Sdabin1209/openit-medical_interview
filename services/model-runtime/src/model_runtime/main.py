"""조립(의존 주입)과 진입점(ADR 0003). 설정은 환경 변수, 비밀은 파일에서만 읽는다(ADR 0004, 0005)."""

import os
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx2 as httpx
from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from model_runtime.components.release import Release
from model_runtime.contract.models import InferenceEngineUrl, LogLevel, ModelProfileName, OciRepositoryName, ServiceName
from model_runtime.link.api import api_router, install_error_handlers
from model_runtime.link.auth import Authenticator, CallerTable, JwksCache, OidcVerifier
from model_runtime.link.engine import VllmEngine
from model_runtime.link.health import ReadinessCheck, health_router
from model_runtime.link.hosts import install_hosts_table, read_hosts_table
from model_runtime.link.registry import OciPackageSource, basic_credentials
from model_runtime.link.runtime import RESPOND_LIMIT_SECONDS, Runtime
from model_runtime.store.profiles import load_profile
from model_runtime.store.release_log import ReleaseLogFile
from model_runtime.types import AdapterRegistry, ChatEngine, PackageSource

SERVICE_NAME = ServiceName(
    "model-runtime"
)  # 건강 응답(HealthReport.service)에 실리는 이 서비스의 이름. 계약 ServiceName 의 값
_STATE_FOLDER = "model-runtime"  # 왜: 캐시 폴더 안에서 기반 모델 가중치(엔진이 쓴다)와 이 서비스의 상태를 가른다


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
    """환경 변수 설정(12-Factor 3). 변수 이름은 계약 ModelRuntimeEnv 와 같다(`OPENIT_` 접두어, 시험이 어긋남을 본다)."""

    model_config = SettingsConfigDict(env_prefix="OPENIT_", extra="ignore")

    root_certificate_file: Path = Field(description="신뢰할 사설 CA 의 루트 인증서 파일(영역 사이 TLS 의 신뢰 앵커).")
    tls_certificate_file: Path = Field(
        description="이 서비스가 이웃(레지스트리)을 부를 때 보이는 클라이언트 인증서 파일."
    )
    tls_private_key_file: Path = Field(description="클라이언트 인증서에 짝인 개인키 파일.")
    listen_port: int = Field(
        ge=1, le=65535, description="영역 안 평문 HTTP 로 요청을 받을 포트(TLS 는 영역 게이트웨이가 끝낸다)."
    )
    log_level: LogLevel = Field(default=LogLevel.INFO, description="로그 수준.")
    egress_proxy: str | None = Field(default=None, description="나가는 호출이 지나는 게이트웨이 터널 주소.")
    oidc_issuer_url: str = Field(description="사람·기계 접근 토큰의 허용 발급자(iss).")
    oidc_jwks_url: str | None = Field(
        default=None, description="발급자의 서명 공개 키 집합 주소. 없으면 디스커버리 문서에서 얻는다."
    )
    oidc_audience: ServiceName = Field(description="접근 토큰의 aud 에 있어야 하는 이 서비스의 이름.")
    registry_url: str = Field(description="모델 패키지를 digest 로 받을 레지스트리 주소(OCI Distribution).")
    registry_repository: OciRepositoryName = Field(description="모델 패키지가 올라 있는 레지스트리 저장소 이름.")
    registry_credentials_file: Path = Field(
        description="레지스트리에서 받을 때 보일 자격 파일. 내용은 `사용자:비밀번호` 한 줄(HTTP 기본 인증, RFC 7617)."
    )
    machine_tokens_file: Path = Field(
        description="이 서비스를 부르는 기계 호출자 표 파일(MachineTokenTable, 비밀 없음)."
    )
    model_profile: ModelProfileName = Field(
        description="GPU 크기별 프로파일 이름. 영역 안 프로파일 표(profiles.json)의 이름."
    )
    model_cache_dir: Path = Field(
        description="유지되는 폴더. 기반 모델 가중치와 이 서비스의 상태(활성화 기록, 받은 패키지)가 든다."
    )
    hosts_table_file: Path | None = Field(
        default=None, description="다른 서버의 레지스트리와 이웃을 찾는 이름 표 파일(HostsTable). 같은 서버면 없다."
    )
    inference_engine_url: InferenceEngineUrl = Field(description="영역 안 추론 엔진(vLLM 의 OpenAI 호환 서버) 주소.")


@dataclass
class Dependencies:
    """바깥과 닿는 부품. 시험은 가짜 레지스트리·엔진으로 바꿔 끼운다."""

    source: PackageSource
    chat: ChatEngine
    adapters: AdapterRegistry
    authenticator: Authenticator
    engine_ready: ReadinessCheck
    closers: list[Callable[[], object]] = field(default_factory=lambda: list[Callable[[], object]]())


def default_dependencies(settings: Settings) -> Dependencies:
    """설정에서 실제 부품을 만든다. 비밀은 파일에서 읽는다."""
    closers: list[Callable[[], object]] = []
    if settings.hosts_table_file is not None:
        closers.append(install_hosts_table(read_hosts_table(settings.hosts_table_file)))
    source = OciPackageSource(
        settings.registry_url,
        settings.registry_repository.root,
        basic_credentials(read_secret("OPENIT_REGISTRY_CREDENTIALS")),
        settings.root_certificate_file,
        settings.egress_proxy,
        (settings.tls_certificate_file, settings.tls_private_key_file),
    )
    http = httpx.AsyncClient(verify=str(settings.root_certificate_file), proxy=settings.egress_proxy, timeout=10.0)
    engine = VllmEngine(settings.inference_engine_url.root, load_profile(settings.model_profile.root).base_model.root)
    oidc = OidcVerifier(
        JwksCache(http, settings.oidc_issuer_url, settings.oidc_jwks_url),
        settings.oidc_issuer_url,
        settings.oidc_audience.value,
    )
    return Dependencies(
        source=source,
        chat=engine,
        adapters=engine,
        authenticator=Authenticator(CallerTable(settings.machine_tokens_file), oidc),
        engine_ready=engine.healthy,
        closers=[source.close, *closers],
    )


def create_app(
    settings: Settings,
    deps: Dependencies | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    respond_limit_seconds: float = RESPOND_LIMIT_SECONDS,
) -> FastAPI:
    """앱 팩토리. 시작할 때 저장된 기록에서 활성 패키지를 스스로 적재한다."""
    resolved = deps or default_dependencies(settings)
    state_dir = settings.model_cache_dir / _STATE_FOLDER
    registry = CollectorRegistry()
    runtime = Runtime(
        release=Release(ReleaseLogFile(state_dir)),
        source=resolved.source,
        chat=resolved.chat,
        adapters=resolved.adapters,
        workdir=state_dir,
        installed_version=version("openit-model_runtime"),
        base_model=load_profile(settings.model_profile.root).base_model.root,
        registry=registry,
        clock=clock,
        respond_limit_seconds=respond_limit_seconds,
    )

    async def store_writable() -> bool:
        state_dir.mkdir(parents=True, exist_ok=True)
        return os.access(state_dir, os.W_OK)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        await runtime.start()
        try:
            yield
        finally:
            await runtime.aclose()
            for close in resolved.closers:
                close()

    app = FastAPI(title=SERVICE_NAME.value, lifespan=lifespan)
    install_error_handlers(app)
    app.state.runtime = runtime
    checks: dict[str, ReadinessCheck] = {"store": store_writable, "engine": resolved.engine_ready}
    app.include_router(health_router(SERVICE_NAME, checks, registry))
    app.include_router(api_router(runtime, resolved.authenticator))
    return app
