"""설정(환경 입력은 계약 SurveyServiceEnv), 계약과 맞는 한도, 건강 상태, 지표."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from tests.support.harness import Harness

from survey_service.main import create_app
from survey_service.settings import CONTRACT_LIMITS, DEFAULT_START_CODE_TTL, limits_of, load_env

CONTRACT = Path(__file__).resolve().parents[4] / "contracts" / "components.yaml"
REQUIRED = {
    "OPENIT_OIDC_ISSUER_URL": "https://platform/realms/openit", "OPENIT_OIDC_AUDIENCE": "survey-service",
    "OPENIT_ROOT_CERTIFICATE_FILE": "/etc/openit/root.pem", "OPENIT_TLS_CERTIFICATE_FILE": "/etc/openit/tls.pem",
    "OPENIT_TLS_PRIVATE_KEY_FILE": "/run/secrets/tls_key", "OPENIT_LISTEN_PORT": "8080",
    "OPENIT_DATABASE_URL": "postgresql://survey@db:5432/survey", "OPENIT_DATABASE_PASSWORD_FILE": "/run/secrets/db",
    "OPENIT_MODEL_RUNTIME_URL": "https://model-runtime", "OPENIT_MODEL_RUNTIME_TOKEN_FILE": "/run/secrets/mr",
    "OPENIT_MACHINE_TOKENS_FILE": "/etc/openit/machines.json", "OPENIT_VAPID_PRIVATE_KEY_FILE": "/run/secrets/vapid",
    "OPENIT_VAPID_SUBJECT": "mailto:ops@example.org", "OPENIT_EGRESS_PROXY": "http://127.0.0.1:3128",
}  # fmt: skip


def test_env_is_validated_by_the_contract_schema() -> None:
    env = load_env({**REQUIRED, "PATH": "/usr/bin", "HOME": "/root"})  # 모르는 변수는 건너뛴다
    assert env.OPENIT_LISTEN_PORT.root == 8080
    for name in REQUIRED:
        broken = {k: v for k, v in REQUIRED.items() if k != name}
        with pytest.raises(ValidationError):
            load_env(broken)
    with pytest.raises(ValidationError):
        load_env({**REQUIRED, "OPENIT_MODEL_RUNTIME_URL": "http://model-runtime"})  # 영역 사이 호출은 항상 TLS
    with pytest.raises(ValidationError):
        load_env({**REQUIRED, "OPENIT_OIDC_AUDIENCE": "somebody-else"})
    with pytest.raises(ValidationError):
        load_env({**REQUIRED, "SURVEY_START_CODE_TTL_SECONDS": "601"})  # 최대 600초
    with pytest.raises(ValidationError):
        load_env({**REQUIRED, "SURVEY_REASK_LIMIT": "3"})


def test_limits_come_from_env_and_contract() -> None:
    limits = limits_of(load_env(REQUIRED))
    assert limits.start_code_ttl_seconds == DEFAULT_START_CODE_TTL == 300
    assert limits_of(load_env({**REQUIRED, "SURVEY_START_CODE_TTL_SECONDS": "120"})).start_code_ttl_seconds == 120
    assert limits.reask_limit == 2 and limits.idle_seconds == 60


def test_hardcoded_limits_equal_the_contract_constants() -> None:
    """계약이 const 로 못박은 값과 코드의 상수가 어긋나지 않는다."""
    schemas = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    expected = {
        "reask_limit": "ReaskLimit", "idle_seconds": "KioskIdleResetSeconds", "turn_seconds": "SurveyTurnLimitSeconds",
        "extract_seconds": "ExtractClientLimitSeconds", "respond_seconds": "RespondClientLimitSeconds",
        "heartbeat_seconds": "AlertStreamHeartbeatSeconds", "retention_days": "RawUtteranceRetentionDays",
    }  # fmt: skip
    for key, schema in expected.items():
        spec = schemas[schema]
        pinned = spec.get("const", spec.get("minimum"))
        assert spec["minimum"] == spec["maximum"] == pinned == CONTRACT_LIMITS[key], (schema, spec)
    assert schemas["StartCodeTtlSeconds"]["default"] == DEFAULT_START_CODE_TTL
    assert schemas["RetryAfterSeconds"]["maximum"] == 120


@pytest.mark.anyio
async def test_health_ready_and_metrics(harness: Harness) -> None:
    async with harness.client() as c:
        assert (await c.get("/healthz")).json() == {"status": "pass", "service": "survey-service"}
        ready = await c.get("/readyz")
        assert ready.status_code == 200 and ready.json()["checks"] == [{"name": "database", "status": "pass"}]
        metrics = (await c.get("/metrics")).text
        assert re.search(r"^# TYPE turn_duration_seconds histogram", metrics, re.M)
        assert re.search(r"^# TYPE model_call_duration_seconds histogram", metrics, re.M)


@pytest.mark.anyio
async def test_readyz_is_503_without_leaking_when_database_is_down(harness: Harness) -> None:
    async def down() -> bool:
        raise RuntimeError("postgresql://survey:SECRET@db/survey")

    app = create_app(harness.runtime, harness.app.state.authenticator, readiness={"database": down})
    import httpx

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://survey-service") as c:
        r = await c.get("/readyz")
    assert r.status_code == 503 and r.headers["retry-after"].isdigit() and "SECRET" not in r.text
    assert r.headers["content-type"].startswith("application/problem+json")
