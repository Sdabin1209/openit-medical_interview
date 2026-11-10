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

from survey_service.contract.models import DevicePlacementTable, SurveyServiceEnv
from survey_service.link import admin_api, hospital_api, kiosk_api, problem, risk_in
from survey_service.link.auth import Authenticator, JwksKeys, load_machine_credentials
from survey_service.link.health import ReadinessCheck, health_router
from survey_service.link.model_client import HttpModelClient
from survey_service.link.push import WebPushNotifier
from survey_service.settings import SERVICE, limits_of, load_env, read_secret
from survey_service.store.engine import database_url, make_engine, migrate
from survey_service.store.repository import SqlStore
from survey_service.types import Runtime, Store


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
