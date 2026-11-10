"""link_api 의 인증: 기계 토큰(bearer)과 사람 접근 토큰(OIDC JWT, RFC 9068).

영역 사이 mTLS(area_mtls)는 TLS 연결에서 서버가 요구한다(serve.py). 여기서는 연결 위에서 토큰을 확인한다.
401 은 토큰이 없거나 틀림, 403 은 인증은 됐으나 역할이 없음이다(D58(2)). 환경 값과 비밀 값은 오류 응답에 넣지 않는다.
"""

from __future__ import annotations

import asyncio
import hmac
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx2 as httpx
import jwt
from jwt import InvalidTokenError, PyJWK

from model_runtime.contract.models import AccessTokenType, MachineTokenTable
from model_runtime.types import ServiceFault

# 왜 비대칭만: RFC 9068 4 는 none 을 거절하라고 한다. 공유 비밀(HS*)은 발급자와 자원 서버가 같은 비밀을 가져야 해서
# JWKS 공개 키 집합(RFC 7517)으로 검증하는 이 구성과 맞지 않는다. IANA JOSE 알고리즘 중 JWKS 로 검증하는 서명
# 알고리즘이다
_ASYMMETRIC = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA")
_REQUIRED_CLAIMS = ("iss", "sub", "aud", "exp", "iat", "jti", "client_id")  # RFC 9068 2.2 의 필수 클레임
# 왜 30: 알 수 없는 kid 가 올 때마다 발급자에게 가면 엉터리 토큰으로 발급자를 두드리게 된다. 공개 키 갱신은 드물어
# 30초면 충분하다고 봤다.
# 측정하지 않았다(ADR 0002)
_JWKS_REFRESH_MIN_SECONDS = 30.0
_WWW_AUTHENTICATE = 'Bearer realm="model-runtime"'


def unauthorized(detail: str) -> ServiceFault:
    """401. WWW-Authenticate 를 함께 낸다."""
    return ServiceFault(401, "인증이 없거나 틀렸다", detail, headers={"WWW-Authenticate": _WWW_AUTHENTICATE})


def forbidden(detail: str) -> ServiceFault:
    """403."""
    return ServiceFault(403, "이 작업을 할 권한이 없다", detail)


def bearer_token(authorization: str | None) -> str:
    """Authorization 머리글에서 bearer 토큰을 꺼낸다(RFC 6750 2.1). 없거나 형식이 다르면 401."""
    if not authorization:
        raise unauthorized("Authorization 머리글이 없다")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized("Authorization 머리글이 Bearer 형식이 아니다")
    return token.strip()


@dataclass(frozen=True)
class _MachineClient:
    name: str
    roles: frozenset[str]
    token: bytes


class MachineTokens:
    """기계 호출자 표(MachineTokenTable)와 토큰 파일. 토큰 값은 파일에서만 읽고 오류에 싣지 않는다(D84)."""

    def __init__(self, table_file: Path) -> None:
        table = MachineTokenTable.model_validate_json(table_file.read_text(encoding="utf-8"))
        clients: list[_MachineClient] = []
        for entry in table.tokens:
            token = Path(entry.token_file.root).read_text(encoding="utf-8").strip()
            if not token:
                raise ValueError(f"기계 호출자 {entry.client.root} 의 토큰 파일이 비었다")
            clients.append(_MachineClient(entry.client.root, frozenset(r.value for r in entry.roles), token.encode()))
        self._clients = clients

    def authenticate(self, token: str) -> tuple[str, frozenset[str]]:
        """토큰이 호출자 표에 있으면 (이름, 역할들). 모두 비교해 시간으로 어느 것이 맞는지 새지 않게
        한다(hmac.compare_digest)."""
        supplied = token.encode()
        matched: _MachineClient | None = None
        for client in self._clients:
            if hmac.compare_digest(client.token, supplied):
                matched = client
        if matched is None:
            raise unauthorized("기계 토큰이 틀렸다")
        return matched.name, matched.roles


class JwksCache:
    """발급자의 서명 공개 키 집합(JWKS, RFC 7517). 알 수 없는 kid 가 오면 갱신하되 간격을 둔다."""

    def __init__(self, http: httpx.AsyncClient, issuer: str, jwks_url: str | None) -> None:
        self._http = http
        self._issuer = issuer.rstrip("/")
        self._jwks_url = jwks_url
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = -_JWKS_REFRESH_MIN_SECONDS
        self._lock = asyncio.Lock()

    async def _resolve_url(self) -> str:
        if self._jwks_url:
            return self._jwks_url
        # OpenID Connect Discovery 1.0 4: 발급자 주소 뒤에 /.well-known/openid-configuration
        response = await self._http.get(f"{self._issuer}/.well-known/openid-configuration")
        response.raise_for_status()
        return str(response.json()["jwks_uri"])

    async def _refresh(self) -> None:
        response = await self._http.get(await self._resolve_url())
        response.raise_for_status()
        self._keys = {jwk.key_id: jwk for jwk in (PyJWK(item) for item in response.json()["keys"]) if jwk.key_id}
        self._fetched_at = time.monotonic()

    async def key_for(self, kid: str | None) -> PyJWK:
        """kid 의 공개 키. 없으면 (간격을 지켜) 한 번 갱신하고 그래도 없으면 401."""
        async with self._lock:
            if kid not in self._keys and time.monotonic() - self._fetched_at >= _JWKS_REFRESH_MIN_SECONDS:
                try:
                    await self._refresh()
                except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError) as error:
                    raise ServiceFault(
                        503, "발급자의 공개 키를 가져오지 못했다", "토큰 서명을 확인할 수 없다", retry_after=5
                    ) from error
            if kid is None or kid not in self._keys:
                raise unauthorized("서명 키를 찾을 수 없다")
            return self._keys[kid]


class OidcVerifier:
    """접근 토큰 검증 프로파일(계약 README, RFC 9068 4)을 그대로 확인한다."""

    def __init__(self, jwks: JwksCache, issuer: str, audience: str) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience

    async def verify(self, token: str) -> Mapping[str, Any]:
        """통과하면 클레임을 돌려준다. 하나라도 어기면 401."""
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as error:
            raise unauthorized("토큰 형식이 틀렸다") from error
        if header.get("typ") not in {t.value for t in AccessTokenType}:
            raise unauthorized("토큰 typ 이 at+jwt 가 아니다")
        algorithm = header.get("alg")
        if algorithm not in _ASYMMETRIC:
            raise unauthorized("허용하지 않는 서명 알고리즘이다")
        key = await self._jwks.key_for(header.get("kid"))
        try:
            claims: Mapping[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except InvalidTokenError as error:
            raise unauthorized("토큰 검증에 실패했다") from error
        return claims

    @staticmethod
    def roles_of(claims: Mapping[str, Any]) -> frozenset[str]:
        """`realm_access.roles` 의 역할들(Keycloak). 모양이 틀리면 역할 없음."""
        access = claims.get("realm_access")
        if not isinstance(access, dict):
            return frozenset()
        roles = cast("dict[str, object]", access).get("roles")
        return (
            frozenset(r for r in cast("list[object]", roles) if isinstance(r, str))
            if isinstance(roles, list)
            else frozenset()
        )


@dataclass(frozen=True)
class Caller:
    """인증을 통과한 호출자. 사람이면 subject 에 토큰의 sub 가 있다."""

    kind: str  # "machine" 또는 "human"
    name: str
    subject: str | None = None


class Authenticator:
    """작업마다 허용하는 신원을 확인한다(계약 security 요구)."""

    def __init__(self, machines: MachineTokens, oidc: OidcVerifier) -> None:
        self._machines = machines
        self._oidc = oidc

    async def require(
        self, authorization: str | None, machine_roles: Sequence[str] = (), human_roles: Sequence[str] = ()
    ) -> Caller:
        """machine_roles 중 하나를 가진 기계 토큰 또는 human_roles 중 하나를 가진 사람 토큰을 받는다."""
        token = bearer_token(authorization)
        if token.count(".") == 2 and human_roles:  # JWT 는 점 둘(RFC 7519 3)
            claims = await self._oidc.verify(token)
            if not set(human_roles) & OidcVerifier.roles_of(claims):
                raise forbidden("필요한 역할이 없다")
            return Caller("human", str(claims["client_id"]), str(claims["sub"]))
        if not machine_roles:
            raise unauthorized("이 작업은 사람 접근 토큰만 받는다")
        name, roles = self._machines.authenticate(token)
        if not set(machine_roles) & roles:
            raise forbidden("필요한 권한이 없다")
        return Caller("machine", name)
