"""시험 도구: 가짜 model-runtime, 임시 DB 로 만든 앱, 서명한 토큰.

왜 가짜 이웃: 다른 영역 없이 혼자 시험해야 한다(D22). 가짜는 계약 타입으로 만든 정해진 출력, 출력 불가, 시간 초과를 낸다.
DB 는 실제 SQLAlchemy 저장소를 임시 SQLite 파일(빠른 시험)이나 PostgreSQL 16 컨테이너(`-m postgres`)에 연다.
"""

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from survey_service.contract.models import (
    ActionExtraction,
    ExtractionRequest,
    ExtractionResult,
    ResponseGenerationRequest,
    ResponseResult,
)
from survey_service.link.auth import Authenticator, MachineCredential
from survey_service.main import create_app, limits_of
from survey_service.store.engine import make_engine, migrate
from survey_service.store.repository import SqlStore
from survey_service.types import AlertRecord, ModelCallError, ModelCallFailure, Runtime
from survey_service.contract.models import PushSubscription, SurveyServiceEnv

DIGEST = "sha256:" + "a" * 64
ISSUER = "https://platform/realms/openit"
BASE = datetime(2026, 11, 10, 9, 0, 0, tzinfo=UTC)


@dataclass
class Clock:
    """고정한 시각. 시험이 앞으로 돌린다."""

    at: datetime = BASE

    def __call__(self) -> datetime:
        return self.at

    def advance(self, seconds: float) -> None:
        self.at += timedelta(seconds=seconds)


@dataclass
class FakeModel:
    """가짜 model-runtime. 정해진 추출 출력과 응답 문장을 차례로 내고, 출력 불가나 시간 초과도 낸다."""

    extractions: deque[ActionExtraction | ModelCallError] = field(default_factory=deque)
    responses: deque[str | ModelCallError] = field(default_factory=deque)
    extract_requests: list[ExtractionRequest] = field(default_factory=list)
    respond_requests: list[ResponseGenerationRequest] = field(default_factory=list)
    version: str | None = "model-io-v2"

    def will_extract(self, body: dict[str, Any] | ModelCallError) -> None:
        self.extractions.append(body if isinstance(body, ModelCallError) else ActionExtraction.model_validate(body))

    def will_respond(self, text: str | ModelCallError) -> None:
        self.responses.append(text)

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        self.extract_requests.append(request)
        item = self.extractions.popleft()
        if isinstance(item, ModelCallError):
            raise item
        return ExtractionResult.model_validate({"package_digest": DIGEST, "output": item.model_dump(mode="json", exclude_none=True)})

    async def respond(self, request: ResponseGenerationRequest) -> ResponseResult:
        self.respond_requests.append(request)
        item = self.responses.popleft()
        if isinstance(item, ModelCallError):
            raise item
        return ResponseResult.model_validate({"package_digest": DIGEST, "text": item})

    async def model_io_version(self) -> str | None:
        return self.version


UNAVAILABLE = ModelCallError(ModelCallFailure.UNAVAILABLE)
DEADLINE = ModelCallError(ModelCallFailure.DEADLINE)


@dataclass
class FakeNotifier:
    """가짜 푸시 전달자. 보낸 알림을 모으고 지정한 주소는 사라졌다고 답한다."""

    sent: list[tuple[AlertRecord, tuple[PushSubscription, ...]]] = field(default_factory=list)
    gone: tuple[str, ...] = ()

    async def push(self, record: AlertRecord, subscriptions: tuple[PushSubscription, ...]) -> tuple[str, ...]:
        self.sent.append((record, subscriptions))
        return self.gone


class Keys:
    """시험용 RSA 키로 접근 토큰을 서명한다(IdP 대신)."""

    def __init__(self) -> None:
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    async def __call__(self, kid: str | None) -> Any:  # noqa: ANN401
        return self.private.public_key()

    def token(self, roles: list[str], *, sub: str = "user-1", audience: str = "survey-service", typ: str = "at+jwt", exp_in: int = 600, issuer: str = ISSUER, now: float | None = None) -> str:
        issued = int(now if now is not None else time.time())
        claims = {
            "iss": issuer, "aud": audience, "sub": sub, "exp": issued + exp_in, "iat": issued, "jti": uuid.uuid4().hex,
            "client_id": "admin-console", "realm_access": {"roles": roles},
        }  # fmt: skip
        return jwt.encode(claims, self.private, algorithm="RS256", headers={"typ": typ, "kid": "k1"})


MACHINES = (
    MachineCredential("hospital", frozenset({"result-reader"}), b"hospital-token"),
    MachineCredential("risk-engine", frozenset({"risk-detector"}), b"risk-token"),
    MachineCredential("model-lab", frozenset({"case-reader"}), b"lab-token"),
)


def xfcc(device: str) -> dict[str, str]:
    """게이트웨이가 넘기는 기기 인증서 헤더."""
    return {"X-Forwarded-Client-Cert": f'Hash={"0" * 64};Subject="CN={device},O=hospital"'}


@dataclass
class Harness:
    """시험이 쓰는 앱과 이웃 가짜 한 벌."""

    app: FastAPI
    runtime: Runtime
    model: FakeModel
    notifier: FakeNotifier
    clock: Clock
    keys: Keys
    engine: AsyncEngine
    ids: list[uuid.UUID]

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://survey-service")

    def human(self, *roles: str, sub: str = "user-1") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.keys.token(list(roles), sub=sub)}"}

    @staticmethod
    def machine(name: str) -> dict[str, str]:
        token = next(c.token for c in MACHINES if c.client == name).decode()
        return {"Authorization": f"Bearer {token}"}


async def build_harness(
    database_url: str,
    *,
    risk: bool = False,
    placements: dict[str, str] | None = None,
) -> Harness:
    """앱을 만든다. 스키마는 마이그레이션으로 올린다(운영과 같은 경로)."""
    engine = make_engine(database_url)
    await migrate(engine)
    clock, model, notifier, keys = Clock(), FakeModel(), FakeNotifier(), Keys()
    counter = {"n": 0}
    ids: list[uuid.UUID] = []

    def new_id() -> uuid.UUID:
        counter["n"] += 1
        value = uuid.UUID(int=counter["n"] + 0x1000)
        ids.append(value)
        return value

    env = SurveyServiceEnv.model_validate(
        {
            "OPENIT_OIDC_ISSUER_URL": ISSUER, "OPENIT_OIDC_AUDIENCE": "survey-service",
            "OPENIT_ROOT_CERTIFICATE_FILE": "/tmp/root.pem", "OPENIT_TLS_CERTIFICATE_FILE": "/tmp/tls.pem",
            "OPENIT_TLS_PRIVATE_KEY_FILE": "/tmp/tls.key", "OPENIT_LISTEN_PORT": "8080",
            "OPENIT_DATABASE_URL": "postgresql://survey@db/survey", "OPENIT_DATABASE_PASSWORD_FILE": "/tmp/pw",
            "OPENIT_MODEL_RUNTIME_URL": "https://model-runtime", "OPENIT_MODEL_RUNTIME_TOKEN_FILE": "/tmp/t",
            "OPENIT_MACHINE_TOKENS_FILE": "/tmp/m.json", "OPENIT_VAPID_PRIVATE_KEY_FILE": "/tmp/v.pem",
            "OPENIT_VAPID_SUBJECT": "mailto:ops@example.org", "OPENIT_EGRESS_PROXY": "http://127.0.0.1:3128",
        }
    )  # fmt: skip
    runtime = Runtime(
        store=SqlStore(engine), model=model, notifier=notifier, now=clock, new_id=new_id, limits=limits_of(env),
        fhir_canonical_base_url="https://example.org/fhir/Questionnaire", risk_detection_enabled=risk,
        device_placements=placements or {}, vapid_public_key="B" + "A" * 86,
    )  # fmt: skip
    authenticator = Authenticator(issuer=ISSUER, audience="survey-service", key_for=keys, machines=MACHINES)
    app = create_app(runtime, authenticator, readiness={"database": runtime.store.ping})
    return Harness(app, runtime, model, notifier, clock, keys, engine, ids)


def sqlite_url(directory: Path) -> str:
    return f"sqlite+aiosqlite:///{directory / 'survey.db'}"


def question_set(questionnaire_id: str = "national-health", title: str = "국가건강검진 문진표") -> dict[str, Any]:
    """시험용 문항 세트 업로드 본문: 질환(Q1), 음주 여부(Q2), 음주량(Q2_1). Q2 가 아니오이면 Q2_1 을 건너뛴다."""
    def spec(item: str, name: str, data_type: str, **extra: Any) -> dict[str, Any]:
        return {"item_id": item, "field_name": name, "data_type": data_type, **extra}

    items = [
        {"item_id": "Q1", "text": "뇌졸중으로 진단받으셨거나 약을 드시나요?",
         "fields": [spec("Q1", "diagnosed", "boolean"), spec("Q1", "on_medication", "boolean")]},
        {"item_id": "Q2", "text": "술을 드시나요?", "fields": [spec("Q2", "answer", "boolean")]},
        {"item_id": "Q2_1", "text": "한 번에 몇 잔 드시나요?",
         "fields": [spec("Q2_1", "amount", "integer", minimum=0, maximum=50, unit="잔")]},
    ]  # fmt: skip
    rules = [
        {"item_id": "Q1", "branches": [{"next_item": "Q2"}]},
        {"item_id": "Q2", "branches": [{"when": {"slot": "Q2.answer", "operator": "EQ", "value": False}, "next_item": "END"}, {"next_item": "Q2_1"}]},
        {"item_id": "Q2_1", "branches": [{"next_item": "END"}]},
    ]  # fmt: skip
    return {
        "questionnaire_id": questionnaire_id,
        "runtime_contract_version": 1,
        "content": {"title": title, "bank": {"items": items}, "flow": {"start_item": "Q1", "rules": rules}},
    }


def value(key: str, val: object, status: str = "ANSWERED", precision: str = "exact") -> dict[str, Any]:
    """추출 출력의 값 하나."""
    return {"key": key, "value": val, "precision": precision, "status": status, "save": status in {"ANSWERED", "CORRECTION"}}


def extraction(action: str, next_item: str, values: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """추출 출력(ActionExtraction) 본문."""
    return {"action": action, "next_item": next_item, "values": values, **extra}
