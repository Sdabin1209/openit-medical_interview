"""조립(의존 주입)과 진입점(ADR 0003). 설정은 환경 변수, 비밀은 파일에서만 읽는다(ADR 0004, 0005).

환경 입력의 모양은 계약 SurveyServiceEnv 가 정한다(받아들이는 조건은 전부 스키마에 둔다). 여기서는 읽어서 검증하고
각 링크 컴포넌트에 필요한 값만 건넨다.
"""

import os
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI
from starlette.types import Lifespan

from survey_service.contract.models import DevicePlacementTable, ServiceName, SurveyServiceEnv
from survey_service.link import admin_api, hospital_api, kiosk_api, problem, risk_in
from survey_service.link.auth import Authenticator, JwksKeys, load_machine_credentials
from survey_service.link.health import ReadinessCheck, health_router
from survey_service.link.model_client import HttpModelClient
from survey_service.link.push import WebPushNotifier
from survey_service.store.engine import database_url, make_engine, migrate
from survey_service.store.repository import SqlStore
from survey_service.types import Limits, Runtime, Store

SERVICE = ServiceName.survey_service
# 왜 이 값들: 한도는 계약이 값을 const 로 못박은 것(ReaskLimit 2, KioskIdleResetSeconds 60, SurveyTurnLimitSeconds 50,
# ExtractClientLimitSeconds 21, RespondClientLimitSeconds 26, AlertStreamHeartbeatSeconds 15,
# RawUtteranceRetentionDays 180)을 따른다.
# 계약과 어긋나지 않는지는 tests/unit/test_limits.py 가 계약 파일과 견준다
CONTRACT_LIMITS = {
    "reask_limit": 2,
    "idle_seconds": 60,
    "turn_seconds": 50,
    "extract_seconds": 21,
    "respond_seconds": 26,
    "heartbeat_seconds": 15,
    "retention_days": 180,
}
DEFAULT_START_CODE_TTL = 300  # 계약 StartCodeTtlSeconds 의 default
# 왜 10회·300초: NIST SP 800-63B 5.2.2 는 실패 시도에 한도를 두라고만 정하고 값은 정하지 않는다. 6자리
# 코드(100만 가지)를
# 기기당 5분에 10번으로 묶으면 코드 유효 시간(최대 600초) 안에 맞힐 확률이 10^-5 수준이다(ADR 0002, 측정하지 않은 선택)
START_FAILURE_LIMIT = 10
START_FAILURE_WINDOW_SECONDS = 300
RETRY_AFTER_SECONDS = 5  # 계약 RetryAfterSeconds 의 예시 값. 측정으로 정한 값이 아니다


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


def load_env(environ: Mapping[str, str]) -> SurveyServiceEnv:
    """환경 변수에서 계약 SurveyServiceEnv 를 읽어 검증한다(모르는 변수는 건너뛴다. 모양이 틀리면 ValidationError)."""
    fields = set(SurveyServiceEnv.model_fields)
    return SurveyServiceEnv.model_validate({key: value for key, value in environ.items() if key in fields})


def limits_of(env: SurveyServiceEnv) -> Limits:
    """환경 입력과 계약 한도로 영역 한도를 만든다."""
    ttl = (
        env.SURVEY_START_CODE_TTL_SECONDS.root
        if env.SURVEY_START_CODE_TTL_SECONDS is not None
        else DEFAULT_START_CODE_TTL
    )
    return Limits(
        start_code_ttl_seconds=ttl,
        start_failure_limit=START_FAILURE_LIMIT,
        start_failure_window_seconds=START_FAILURE_WINDOW_SECONDS,
        retry_after_seconds=RETRY_AFTER_SECONDS,
        **CONTRACT_LIMITS,
    )


def create_app(
    runtime: Runtime,
    authenticator: Authenticator,
    *,
    readiness: Mapping[str, ReadinessCheck] | None = None,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    """앱 팩토리. 의존은 모두 밖에서 넣는다(시험은 가짜 이웃과 임시 DB 를 넣는다)."""
    app = FastAPI(title=SERVICE.value, lifespan=lifespan)
    app.state.authenticator = authenticator
    problem.install(app)
    app.include_router(health_router(SERVICE, readiness or {}))
    app.include_router(kiosk_api.router(runtime))
    app.include_router(admin_api.router(runtime))
    app.include_router(hospital_api.router(runtime))
    app.include_router(risk_in.router(runtime))
    return app


def _placements(env: SurveyServiceEnv) -> dict[str, str]:
    if env.SURVEY_DEVICE_PLACEMENTS_FILE is None:
        return {}
    table = DevicePlacementTable.model_validate_json(
        Path(env.SURVEY_DEVICE_PLACEMENTS_FILE.root).read_text(encoding="utf-8")
    )
    return {p.device_id.root: p.questionnaire_id.root for p in table.placements}


def build(environ: Mapping[str, str] | None = None) -> FastAPI:
    """운영 조립: 환경 입력을 읽어 DB·이웃·인증을 만든다. `uvicorn --factory survey_service.main:build` 로 띄운다."""
    source = os.environ if environ is None else environ
    env = load_env(source)
    engine = make_engine(
        database_url(str(env.OPENIT_DATABASE_URL.root), read_secret("OPENIT_DATABASE_PASSWORD", source))
    )
    store: Store = SqlStore(engine)
    limits = limits_of(env)
    proxy = str(env.OPENIT_EGRESS_PROXY.root)
    root = env.OPENIT_ROOT_CERTIFICATE_FILE.root
    model = HttpModelClient(
        str(env.OPENIT_MODEL_RUNTIME_URL.root),
        read_secret("OPENIT_MODEL_RUNTIME_TOKEN", source),
        limits,
        egress_proxy=proxy,
        root_certificate=root,
    )
    notifier = WebPushNotifier(
        env.OPENIT_VAPID_PRIVATE_KEY_FILE.root, str(env.OPENIT_VAPID_SUBJECT.root), egress_proxy=proxy
    )
    idp = httpx.AsyncClient(verify=root)
    jwks_url = str(env.OPENIT_OIDC_JWKS_URL.root) if env.OPENIT_OIDC_JWKS_URL is not None else None
    authenticator = Authenticator(
        issuer=str(env.OPENIT_OIDC_ISSUER_URL.root),
        audience=env.OPENIT_OIDC_AUDIENCE.value,
        key_for=JwksKeys(str(env.OPENIT_OIDC_ISSUER_URL.root), jwks_url, client=idp),
        machines=load_machine_credentials(env.OPENIT_MACHINE_TOKENS_FILE.root),
    )
    runtime = Runtime(
        store=store,
        model=model,
        notifier=notifier,
        now=lambda: datetime.now(UTC),
        new_id=uuid4,
        limits=limits,
        fhir_canonical_base_url=str(env.SURVEY_FHIR_CANONICAL_BASE_URL.root)
        if env.SURVEY_FHIR_CANONICAL_BASE_URL
        else "",
        risk_detection_enabled=bool(env.SURVEY_RISK_DETECTION_ENABLED.root)
        if env.SURVEY_RISK_DETECTION_ENABLED
        else False,
        device_placements=_placements(env),
        vapid_public_key=notifier.public_key,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        await migrate(
            engine
        )  # 왜 시작 때: 영역 DB 의 스키마는 이 영역이 소유하고 head 가 아니면 /readyz 가 준비되지 않는다
        yield
        await model.close()
        await notifier.close()
        await idp.aclose()
        await engine.dispose()

    return create_app(runtime, authenticator, readiness={"database": store.ping}, lifespan=lifespan)
