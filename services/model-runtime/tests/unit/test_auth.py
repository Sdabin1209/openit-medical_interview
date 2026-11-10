"""link_api 인증: 사람과 기계 호출자 모두 JWT 접근 토큰(RFC 9068 검증 프로파일). 401 은 틀림, 403 은 역할 없음."""

import base64
import json
from pathlib import Path
from typing import Any

import httpx2 as httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from model_runtime.link.auth import Authenticator, CallerTable, JwksCache, OidcVerifier, bearer_token
from model_runtime.types import ServiceFault
from support import AUDIENCE, ISSUER, NOW, Identity, fixed_now

pytestmark = pytest.mark.anyio


def machines(tmp_path: Path) -> CallerTable:
    table = {
        "tokens": [
            {"client": "survey-service", "roles": ["inference-caller"], "client_secret_file": "/run/secrets/a"},
            {"client": "model-lab", "roles": ["case-reader"], "client_secret_file": "/run/secrets/b"},
        ]
    }
    (tmp_path / "table.json").write_text(json.dumps(table), encoding="utf-8")
    return CallerTable(tmp_path / "table.json")


def authenticator(tmp_path: Path, identity: Identity, jwks_url: str | None = None) -> Authenticator:
    idp = httpx.AsyncClient(transport=httpx.ASGITransport(app=identity.idp_app()))
    return Authenticator(
        machines(tmp_path), OidcVerifier(JwksCache(idp, ISSUER, jwks_url), ISSUER, AUDIENCE, fixed_now)
    )


async def status_of(call: Any) -> int:  # noqa: ANN401
    try:
        await call
    except ServiceFault as fault:
        return fault.status
    return 200


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer", "Bearer   "])
def test_bearer_header_must_be_well_formed(header: str | None) -> None:
    with pytest.raises(ServiceFault) as info:
        bearer_token(header)
    assert info.value.status == 401 and info.value.headers["WWW-Authenticate"].startswith("Bearer")


async def test_machine_jwt_with_role_in_token_and_table(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    caller = await auth.require(f"Bearer {identity.machine_token()}", machine_roles=["inference-caller"])
    assert (caller.kind, caller.name, caller.subject) == ("machine", "survey-service", None)


async def test_machine_jwt_without_the_role_is_403(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    other = identity.machine_token("model-lab", ("case-reader",))  # 표에도 토큰에도 case-reader 만 있다
    assert await status_of(auth.require(f"Bearer {other}", machine_roles=["inference-caller"])) == 403
    assert (
        await status_of(auth.require(f"Bearer {identity.machine_token(roles=())}", machine_roles=["inference-caller"]))
        == 403
    )


async def test_role_in_token_is_not_enough_when_the_table_does_not_allow_it(tmp_path: Path) -> None:
    """IdP 가 표 밖의 역할이나 표 밖의 호출자에게 역할을 줘도 이 서비스의 호출자 표가 허용하지 않으면 403."""
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    wider = identity.machine_token("model-lab", ("inference-caller", "case-reader"))
    stranger = identity.machine_token("unknown-caller")
    assert await status_of(auth.require(f"Bearer {wider}", machine_roles=["inference-caller"])) == 403
    assert await status_of(auth.require(f"Bearer {stranger}", machine_roles=["inference-caller"])) == 403


async def test_machine_jwt_with_a_role_outside_the_contract_is_401(tmp_path: Path) -> None:
    """토큰에는 계약 MachineRole 만 실린다(platform 이 범위를 제한). 계약 밖 역할이 있으면 모델이 거절한다."""
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    token = identity.machine_token(roles=("inference-caller", "offline_access"))
    assert await status_of(auth.require(f"Bearer {token}", machine_roles=["inference-caller"])) == 401


async def test_machine_jwt_with_a_broken_claim_is_401(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    bad_client = identity.machine_token(client_id="machine-Bad_Name")  # 계약 MachineOidcClientId 의 패턴을 어긴다
    assert await status_of(auth.require(f"Bearer {bad_client}", machine_roles=["inference-caller"])) == 401
    no_realm_access = identity.machine_token(_drop=("realm_access",))  # 계약 MachineIdentityClaims 의 필수 칸이 없다
    assert await status_of(auth.require(f"Bearer {no_realm_access}", machine_roles=["inference-caller"])) == 401


async def test_machine_jwt_is_not_accepted_where_only_people_may_call(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    assert await status_of(auth.require(f"Bearer {identity.machine_token()}", human_roles=["release-approver"])) == 403


async def test_fixed_token_strings_are_no_longer_credentials(tmp_path: Path) -> None:
    auth = authenticator(tmp_path, Identity.new())
    assert (
        await status_of(auth.require("Bearer machine-token-for-survey-service", machine_roles=["inference-caller"]))
        == 401
    )


async def test_machine_jwt_audience_must_be_this_service(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    token = identity.machine_token(aud="survey-service")
    assert await status_of(auth.require(f"Bearer {token}", machine_roles=["inference-caller"])) == 401


async def test_human_token_with_role_gives_sub(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    caller = await auth.require(
        f"Bearer {identity.token(['release-approver'], sub='user-9')}", human_roles=["release-approver"]
    )
    assert (caller.kind, caller.subject) == ("human", "user-9")


async def test_human_token_without_the_role_is_403(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    assert await status_of(auth.require(f"Bearer {identity.token(['staff'])}", human_roles=["release-approver"])) == 403
    assert await status_of(auth.require(f"Bearer {identity.token([])}", human_roles=["release-approver"])) == 403


def b64(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


@pytest.mark.parametrize(
    "case",
    [
        "expired",
        "wrong_issuer",
        "wrong_audience",
        "missing_client_id",
        "missing_jti",
        "missing_iat",
        "typ_jwt",
        "typ_missing",
        "alg_none",
        "hs256",
        "unknown_kid",
        "other_key",
        "garbage",
    ],
)
async def test_access_token_profile_violations_are_401(tmp_path: Path, case: str) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity)
    now = int(NOW.timestamp())
    tokens: dict[str, str] = {
        "expired": identity.token(["release-approver"], exp=now - 10),
        "wrong_issuer": identity.token(["release-approver"], iss="https://evil.test"),
        "wrong_audience": identity.token(["release-approver"], aud="survey-service"),
        "missing_client_id": identity.token(["release-approver"], _drop=("client_id",)),
        "missing_jti": identity.token(["release-approver"], _drop=("jti",)),
        "missing_iat": identity.token(["release-approver"], _drop=("iat",)),
        "typ_jwt": identity.token(["release-approver"], _headers={"typ": "JWT"}),
        "typ_missing": jwt.encode(
            {"iss": ISSUER}, identity.key, algorithm="RS256", headers={"kid": identity.kid, "typ": None}
        ),
        "alg_none": ".".join(
            [
                b64({"alg": "none", "typ": "at+jwt", "kid": identity.kid}),
                b64({"iss": ISSUER, "sub": "x", "aud": AUDIENCE}),
                "",
            ]
        ),
        "hs256": jwt.encode(
            {"iss": ISSUER, "sub": "x", "aud": AUDIENCE},
            "x" * 40,
            algorithm="HS256",
            headers={"typ": "at+jwt", "kid": identity.kid},
        ),
        "unknown_kid": identity.token(["release-approver"], _headers={"kid": "nope"}),
        "other_key": Identity(rsa.generate_private_key(public_exponent=65537, key_size=2048)).token(
            ["release-approver"]
        ),
        "garbage": "a.b.c",
    }
    assert await status_of(auth.require(f"Bearer {tokens[case]}", human_roles=["release-approver"])) == 401


async def test_jwks_is_found_through_discovery_when_no_url_is_given(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity, jwks_url=None)
    assert (await auth.require(f"Bearer {identity.token(['operator'])}", human_roles=["operator"])).kind == "human"


async def test_jwks_url_setting_is_used_when_given(tmp_path: Path) -> None:
    identity = Identity.new()
    auth = authenticator(tmp_path, identity, jwks_url=f"{ISSUER}/protocol/openid-connect/certs")
    assert (await auth.require(f"Bearer {identity.token(['operator'])}", human_roles=["operator"])).kind == "human"


async def test_unknown_kid_does_not_hammer_the_issuer(tmp_path: Path) -> None:
    identity = Identity.new()
    hits: list[str] = []
    app = identity.idp_app()

    @app.middleware("http")
    async def count(request: Any, call_next: Any) -> Any:  # noqa: ANN401
        hits.append(request.url.path)
        return await call_next(request)

    idp = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
    auth = Authenticator(machines(tmp_path), OidcVerifier(JwksCache(idp, ISSUER, None), ISSUER, AUDIENCE, fixed_now))
    bad = identity.token(["operator"], _headers={"kid": "nope"})
    for _ in range(5):
        assert await status_of(auth.require(f"Bearer {bad}", human_roles=["operator"])) == 401
    assert len([h for h in hits if h.endswith("/certs")]) == 1  # 엉터리 토큰 다섯 번에 공개 키 요청은 한 번뿐이다


async def test_unreachable_issuer_is_503_not_401(tmp_path: Path) -> None:
    identity = Identity.new()

    async def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    idp = httpx.AsyncClient(transport=httpx.MockTransport(down))
    auth = Authenticator(machines(tmp_path), OidcVerifier(JwksCache(idp, ISSUER, None), ISSUER, AUDIENCE, fixed_now))
    assert await status_of(auth.require(f"Bearer {identity.token(['operator'])}", human_roles=["operator"])) == 503


def test_caller_table_is_read_with_the_contract_model(tmp_path: Path) -> None:
    table = machines(tmp_path)
    assert table.allowed_roles("machine-survey-service") == {"inference-caller"}
    assert table.allowed_roles("machine-nobody") == frozenset()
    (tmp_path / "bad.json").write_text(
        json.dumps({"tokens": [{"client": "x", "roles": ["inference-caller"], "token_file": "/t"}]})
    )
    with pytest.raises(ValueError, match="client_secret_file"):  # 8.0.0 의 칸 이름(token_file)은 더 받지 않는다
        CallerTable(tmp_path / "bad.json")
