"""link_api 의 인증: 사람과 기계 호출자 모두 IdP 가 낸 JWT 접근 토큰(RFC 9068)을 받는다(ADR 0005).

영역 사이 mTLS(area_mtls)는 영역 게이트웨이가 끝낸다. 여기서는 평문 연결로 온 토큰을 확인한다. 사람과 기계는 같은 검증
코드(OidcVerifier)를 지나고, client_id 가 machine- 로 시작하면 기계 호출자로 본다(계약 MachineOidcClientId).
401 은 토큰이 없거나 틀림, 403 은 인증은 됐으나 역할이 없음이다(D58(2)). 환경 값과 비밀 값은 오류 응답에 넣지 않는다.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx2 as httpx
import jwt
from jwt import InvalidTokenError, PyJWK
from pydantic import ValidationError

from model_runtime.contract.models import (
    AccessTokenType,
    MachineIdentityClaims,
    MachineTokenTable,
    UserRole,
)
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


_MACHINE_CLIENT_PREFIX = "machine-"  # 계약 MachineOidcClientId 의 접두어(client_id = machine-<호출자 이름>)


class CallerTable:
    """기계 호출자 표(MachineTokenTable, 비밀 없음). client_id 로 호출자를 찾고 허용한 역할을 알려 준다.

    왜 표를 읽나: 토큰의 역할(realm_access)은 IdP 가 낸 값이고, 이 서비스가 어느 호출자에게 어느 역할을 허용하는지는
    표가 정한다. 토큰의 역할과 표의 허용이 모두 있어야 통과시킨다(IdP 설정이 어긋나도 표 밖의 호출자는 못 들어온다).
    표의 client_secret_file 은 토큰을 받는 쪽(호출자)의 비밀이라 이 서비스는 읽지 않는다.
    """

    def __init__(self, table_file: Path) -> None:
        table = MachineTokenTable.model_validate_json(table_file.read_text(encoding="utf-8"))
        self._roles = {entry.client.root: frozenset(role.value for role in entry.roles) for entry in table.tokens}

    def allowed_roles(self, client_id: str) -> frozenset[str]:
        """client_id(machine-<이름>)의 호출자가 표에서 허용받은 역할들. 표에 없으면 비어 있다."""
        name = client_id.removeprefix(_MACHINE_CLIENT_PREFIX)
        return self._roles.get(name, frozenset())


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
        # 왜 use 가 sig 인 키만: RFC 7517 4.2 의 use 는 키의 용도다. Keycloak 의 JWKS 는 암호화용(enc)
        # 키도 내고 PyJWK 가 그 키를 못 만들어 갱신 전체가 실패했다(통합 확인). 서명 키만 쓴다
        signing = [item for item in response.json()["keys"] if item.get("use", "sig") == "sig"]
        self._keys = {jwk.key_id: jwk for jwk in (PyJWK(item) for item in signing) if jwk.key_id}
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


def _known_roles(claims: Mapping[str, Any], known: type[UserRole]) -> frozenset[str]:
    """사람 토큰의 역할 중 계약이 아는 것만."""
    return OidcVerifier.roles_of(claims) & {role.value for role in known}


class Authenticator:
    """작업마다 허용하는 신원을 확인한다(계약 security 요구). 사람과 기계 모두 JWT 를 같은 검증기로 확인한다."""

    def __init__(self, callers: CallerTable, oidc: OidcVerifier) -> None:
        self._callers = callers
        self._oidc = oidc

    async def require(
        self, authorization: str | None, machine_roles: Sequence[str] = (), human_roles: Sequence[str] = ()
    ) -> Caller:
        """machine_roles 중 하나를 가진 기계 토큰 또는 human_roles 중 하나를 가진 사람 토큰을 받는다."""
        claims = await self._oidc.verify(bearer_token(authorization))
        client_id = str(claims["client_id"])
        if client_id.startswith(_MACHINE_CLIENT_PREFIX):
            return self._machine(claims, client_id, machine_roles)
        if not set(human_roles) & _known_roles(claims, UserRole):
            raise forbidden("필요한 역할이 없다")
        return Caller("human", client_id, str(claims["sub"]))

    def _machine(self, claims: Mapping[str, Any], client_id: str, required: Sequence[str]) -> Caller:
        # 왜 클레임을 그대로 검증하나: platform 이 기계 클라이언트의 범위를 제한해
        # 토큰에 MachineRole 만 실린다(model-runtime-006). 계약 밖 역할이 실리면 모델이 거절한다(401)
        try:
            identity = MachineIdentityClaims.model_validate(claims)
        except ValidationError as error:
            raise unauthorized("기계 토큰의 클레임이 계약과 다르다") from error
        granted = {role.value for role in identity.realm_access.roles} & self._callers.allowed_roles(client_id)
        if not set(required) & granted:
            raise forbidden("필요한 권한이 없다")
        return Caller("machine", client_id.removeprefix(_MACHINE_CLIENT_PREFIX))
