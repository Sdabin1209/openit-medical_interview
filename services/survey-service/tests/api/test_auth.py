"""인증: 신원은 platform 이 넘긴 것만 쓴다(사람 토큰 프로파일 RFC 9068, 기기 헤더, 기계 토큰)."""

import base64
import json

import jwt
import pytest
from tests.support.harness import ISSUER, Harness, xfcc

pytestmark = pytest.mark.anyio


def _unsigned() -> str:
    """서명이 없는 토큰(alg none)을 손으로 만든다."""

    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none', 'typ': 'at+jwt'})}.{part({'sub': 'x', 'aud': 'survey-service'})}."


async def test_missing_token_is_401_with_challenge(harness: Harness) -> None:
    async with harness.client() as c:
        r = await c.get("/v1/staff-alerts")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "case",
    ["expired", "wrong_audience", "wrong_issuer", "wrong_typ", "alg_none", "no_roles_claim", "garbage"],
)
async def test_bad_tokens_are_401(harness: Harness, case: str) -> None:
    keys = harness.keys
    now = harness.clock().timestamp()
    token = {
        "expired": lambda: keys.token(["staff"], exp_in=-10, now=now - 100),
        "wrong_audience": lambda: keys.token(["staff"], audience="model-runtime"),
        "wrong_issuer": lambda: keys.token(["staff"], issuer="https://evil/realms/x"),
        "wrong_typ": lambda: keys.token(["staff"], typ="JWT"),
        "alg_none": lambda: _unsigned(),
        "no_roles_claim": lambda: jwt.encode(
            {
                "iss": ISSUER,
                "aud": "survey-service",
                "sub": "u",
                "exp": int(now) + 60,
                "iat": int(now),
                "jti": "j",
                "client_id": "c",
            },
            keys.private,
            algorithm="RS256",
            headers={"typ": "at+jwt"},
        ),
        "garbage": lambda: "not-a-jwt",
    }[case]()
    async with harness.client() as c:
        r = await c.get("/v1/staff-alerts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, r.text


async def test_forged_signature_is_401(harness: Harness) -> None:
    other = type(harness.keys)(harness.clock)
    async with harness.client() as c:
        r = await c.get("/v1/staff-alerts", headers={"Authorization": f"Bearer {other.token(['staff'])}"})
    assert r.status_code == 401


async def test_role_is_checked_403(harness: Harness) -> None:
    async with harness.client() as c:
        assert (await c.get("/v1/staff-alerts", headers=harness.human("author"))).status_code == 403
        assert (await c.get("/v1/results", headers=harness.human("staff"))).status_code == 403
        assert (await c.get("/v1/cases", headers=harness.human("clinician"))).status_code == 403
        assert (await c.get("/v1/results", headers=harness.machine("risk-engine"))).status_code == 403
        assert (await c.get("/v1/case-exports", headers=harness.machine("hospital"))).status_code == 403


async def test_roles_outside_the_contract_make_the_token_invalid(harness: Harness) -> None:
    """토큰에는 계약의 역할(UserRole)만 실린다(platform 설정, 변경 요청 003). 모르는 역할이 있으면 계약 모델이 거절한다."""
    async with harness.client() as c:
        mixed = harness.keys.token(["offline_access", "staff"])
        assert (await c.get("/v1/staff-alerts", headers={"Authorization": f"Bearer {mixed}"})).status_code == 401
        clean = harness.keys.token(["staff"])
        assert (await c.get("/v1/staff-alerts", headers={"Authorization": f"Bearer {clean}"})).status_code == 200


async def test_device_header_is_required_and_parsed(harness: Harness) -> None:
    async with harness.client() as c:
        assert (await c.get("/v1/sessions/00000000-0000-4000-8000-000000000001/state")).status_code == 401
        bad = {"X-Forwarded-Client-Cert": 'Hash=ab;Subject="O=hospital"'}
        assert (await c.get("/v1/sessions/00000000-0000-4000-8000-000000000001/state", headers=bad)).status_code == 401
        weird = {"X-Forwarded-Client-Cert": 'Subject="CN=bad id!"'}
        assert (
            await c.get("/v1/sessions/00000000-0000-4000-8000-000000000001/state", headers=weird)
        ).status_code == 401
        ok = await c.get("/v1/sessions/00000000-0000-4000-8000-000000000001/state", headers=xfcc("kiosk-01"))
        assert ok.status_code == 404  # 인증은 통과하고 세션이 없다


async def test_machine_caller_is_a_jwt_checked_against_the_caller_table(harness: Harness) -> None:
    """기계 호출자: JWT(client credentials)의 서명·aud·exp 와 realm_access.roles, 호출자 표(ADR 0014)."""
    h = harness
    async with h.client() as c:
        ok = await c.get("/v1/results", headers=h.machine("hospital"))
        assert ok.status_code == 200
        # 표에 없는 호출자는 신원은 맞아도 권한이 없다
        assert (await c.get("/v1/results", headers=h.machine("stranger", "result-reader"))).status_code == 403
        # 토큰의 역할이 표보다 넓어도 표가 허용한 역할만 남는다(교집합)
        wide = h.machine("hospital", "result-reader", "risk-detector", "case-reader")
        assert (await c.get("/v1/results", headers=wide)).status_code == 200
        assert (await c.get("/v1/case-exports", headers=wide)).status_code == 403
        assert (
            await c.post("/v1/risk-signals", json={}, headers=wide)
        ).status_code == 403  # risk-detector 는 표에 없다
        # 표가 허용해도 토큰의 역할에 없으면 권한이 없다
        assert (await c.get("/v1/results", headers=h.machine("hospital", "case-reader"))).status_code == 403


@pytest.mark.parametrize(
    "case", ["wrong_audience", "expired", "wrong_issuer", "wrong_typ", "not_machine_prefix", "unknown_role"]
)
async def test_bad_machine_tokens_are_401(harness: Harness, case: str) -> None:
    h = harness
    now = h.clock().timestamp()
    token = {
        "wrong_audience": lambda: h.keys.token(
            ["result-reader"], client_id="machine-hospital", audience="model-runtime"
        ),
        "expired": lambda: h.keys.token(["result-reader"], client_id="machine-hospital", exp_in=-10, now=now - 100),
        "wrong_issuer": lambda: h.keys.token(["result-reader"], client_id="machine-hospital", issuer="https://evil/r"),
        "wrong_typ": lambda: h.keys.token(["result-reader"], client_id="machine-hospital", typ="JWT"),
        # 기계 역할을 가졌지만 클라이언트 ID 가 machine-<이름> 이 아니면 기계 토큰도 사람 토큰도 아니다
        "not_machine_prefix": lambda: h.keys.token(["result-reader"], client_id="hospital"),
        "unknown_role": lambda: h.keys.token(["result-reader", "superuser"], client_id="machine-hospital"),
    }[case]()
    async with h.client() as c:
        r = await c.get("/v1/results", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, r.text


async def test_the_old_fixed_token_is_no_longer_accepted(harness: Harness) -> None:
    async with harness.client() as c:
        r = await c.get("/v1/results", headers={"Authorization": "Bearer hospital-token"})
    assert r.status_code == 401


async def test_human_token_on_a_machine_only_route_is_403_and_machine_on_a_human_route_is_403(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        assert (await c.post("/v1/risk-signals", json={}, headers=h.human("staff"))).status_code == 403
        assert (await c.get("/v1/staff-alerts", headers=h.machine("hospital"))).status_code == 403
