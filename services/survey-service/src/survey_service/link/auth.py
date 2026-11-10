"""인증: 신원은 platform 이 넘긴 것만 쓴다(사람 OIDC 토큰, 기기 mTLS 헤더, 기계 토큰). 본문의 신원은 쓰지 않는다.

- 사람: JWT 접근 토큰(RFC 9068 프로파일, contracts/README). 서명은 IdP 의 공개 키 집합(JWKS)으로,
  iss·aud·exp·iat 와 typ·alg 를
  확인하고 역할은 realm_access.roles 에서 읽는다.
- 기기: Envoy 표준 헤더 X-Forwarded-Client-Cert 의 Subject CN 이 기기 ID 다. 서비스는 게이트웨이와의 mTLS
  연결로 온 요청의
  헤더만 믿는다. 이 연결의 보장은 네트워크 구성(영역 게이트웨이만 서비스에 닿는다)이 하고 서비스는 확인할 방법이 없다.
- 기계: 호출자별 토큰 파일(MachineTokenTable). 상수 시간 비교로 맞춘다.
"""

import hmac
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Header, Request
from pydantic import ValidationError

from survey_service.contract.models import (
    AccessTokenHeader,
    DeviceId,
    MachineRole,
    MachineTokenTable,
    UserIdentityClaims,
    UserRole,
)
from survey_service.link.problem import ApiError
from survey_service.types import Principal, PrincipalKind

BEARER = 'Bearer realm="openit"'
# 왜 'Bearer error="invalid_token"': RFC 6750 3 이 만료·서명 오류에 요구하는 도전 모양
INVALID_TOKEN = 'Bearer realm="openit", error="invalid_token"'  # noqa: S105  (RFC 6750 도전 문자열이며 비밀이 아니다)
_SUBJECT = re.compile(r'Subject="(?P<subject>[^"]*)"')
_CN = re.compile(r"(?:^|,)\s*CN=(?P<cn>[^,]+)")

KeyFor = Callable[[str | None], Awaitable[Any]]


@dataclass(frozen=True)
class MachineCredential:
    """기계 호출자 하나: 이름, 허용 권한, 토큰 값(메모리에만 둔다)."""

    client: str
    roles: frozenset[str]
    token: bytes


def load_machine_credentials(table_file: str) -> tuple[MachineCredential, ...]:
    """기계 호출자 표 파일(MachineTokenTable)과 호출자별 토큰 파일을 읽는다. 값은 로그에 남기지 않는다."""
    table = MachineTokenTable.model_validate_json(Path(table_file).read_text(encoding="utf-8"))
    return tuple(
        MachineCredential(
            client=entry.client.root,
            roles=frozenset(role.value for role in entry.roles),
            token=Path(entry.token_file.root).read_text(encoding="utf-8").rstrip("\r\n").encode(),
        )
        for entry in table.tokens
    )


@dataclass(frozen=True)
class Authenticator:
    """요청의 신원을 가르는 도구. main 이 만들어 라우터에 넣는다."""

    issuer: str
    audience: str
    key_for: KeyFor
    machines: tuple[MachineCredential, ...]

    async def human(self, token: str) -> Principal:
        """JWT 접근 토큰 검증(RFC 9068). 하나라도 어기면 401."""
        try:
            raw_header = jwt.get_unverified_header(token)
            header = AccessTokenHeader.model_validate(raw_header)
            if header.alg.root.lower() == "none":
                raise ValueError("alg none")
            key = await self.key_for(raw_header.get("kid"))
            claims = jwt.decode(
                token,
                key,
                algorithms=[header.alg.root],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "jti", "client_id"]},
            )
            checked = UserIdentityClaims.model_validate(claims)
        except (jwt.PyJWTError, ValidationError, ValueError, KeyError) as error:
            raise ApiError(401, authenticate=INVALID_TOKEN) from error
        return Principal(
            kind=PrincipalKind.HUMAN,
            subject=checked.sub.root,
            roles=frozenset(role.value for role in checked.realm_access.roles),
        )

    def machine(self, token: str) -> Principal | None:
        """기계 토큰이면 호출자를, 아니면 None. 왜 전부 비교하나: 맞는 항목에서 멈추면 비교 시간으로 호출자
        수를 엿볼 수 있다."""
        found: MachineCredential | None = None
        for credential in self.machines:
            if hmac.compare_digest(credential.token, token.encode()):
                found = credential
        if found is None:
            return None
        return Principal(kind=PrincipalKind.MACHINE, subject=found.client, roles=found.roles)


def device_id_of(forwarded_client_cert: str | None) -> str:
    """X-Forwarded-Client-Cert 의 Subject CN 에서 기기 ID 를 읽는다. 없거나 틀리면 401."""
    if not forwarded_client_cert:
        raise ApiError(401, authenticate=BEARER)
    subject = _SUBJECT.search(forwarded_client_cert)
    cn = _CN.search(subject["subject"]) if subject else None
    if cn is None:
        raise ApiError(401, authenticate=BEARER)
    try:
        return DeviceId.model_validate(cn["cn"].strip()).root
    except ValidationError as error:
        raise ApiError(401, authenticate=BEARER) from error


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer ") or len(authorization) > 16000:
        raise ApiError(401, authenticate=BEARER)
    return authorization[7:].strip()


Forwarded = Annotated[str | None, Header(alias="X-Forwarded-Client-Cert")]
Authorization = Annotated[str | None, Header()]


def require_device() -> Callable[..., Awaitable[Principal]]:
    """기기(mTLS) 호출자만."""

    async def dependency(x_forwarded_client_cert: Forwarded = None) -> Principal:
        return Principal(kind=PrincipalKind.DEVICE, subject=device_id_of(x_forwarded_client_cert), roles=frozenset())

    return dependency


def require_any(
    *,
    humans: frozenset[UserRole] = frozenset(),
    machines: frozenset[MachineRole] = frozenset(),
    device: bool = False,
) -> Callable[..., Awaitable[Principal]]:
    """계약의 security 요구(대안 목록) 중 하나라도 맞으면 통과한다. 인증이 안 되면 401, 역할이 모자라면 403."""

    async def dependency(
        request: Request, authorization: Authorization = None, x_forwarded_client_cert: Forwarded = None
    ) -> Principal:
        auth: Authenticator = request.app.state.authenticator
        # 왜 헤더가 있으면 기기: 게이트웨이는 기기 인증서가 있는 요청에만 이 헤더를 쓴다
        if device and x_forwarded_client_cert:
            return Principal(
                kind=PrincipalKind.DEVICE, subject=device_id_of(x_forwarded_client_cert), roles=frozenset()
            )
        token = _bearer(authorization)
        principal = auth.machine(token)  # 왜 항상 보나: 이 작업에 권한이 없는 기계 토큰은 401 이 아니라 403 이다
        if principal is not None:
            if principal.roles & {role.value for role in machines}:
                return principal
            raise ApiError(403)
        if not humans:
            raise ApiError(401, authenticate=INVALID_TOKEN)
        principal = await auth.human(token)
        if principal.roles & {role.value for role in humans}:
            return principal
        raise ApiError(403)

    return dependency


# 계약의 security 요구마다 하나씩(OpenAPI 의 대안 목록: 사람 역할 또는 기계 권한 또는 기기). 라우터가
# 매개변수 형으로 쓴다
Device = Annotated[Principal, Depends(require_device())]
DeviceOrStaff = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.staff}), device=True))]
Staff = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.staff})))]
StaffOrClinician = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.staff, UserRole.clinician})))]
Clinician = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.clinician})))]
ClinicianOrReader = Annotated[
    Principal,
    Depends(require_any(humans=frozenset({UserRole.clinician}), machines=frozenset({MachineRole.result_reader}))),
]
Author = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.author})))]
Reviewer = Annotated[Principal, Depends(require_any(humans=frozenset({UserRole.reviewer})))]
RiskDetector = Annotated[Principal, Depends(require_any(machines=frozenset({MachineRole.risk_detector})))]
CaseReader = Annotated[Principal, Depends(require_any(machines=frozenset({MachineRole.case_reader})))]


# 왜 60초: 모르는 kid 가 올 때마다 IdP 를 부르면 가짜 토큰으로 IdP 를 두드릴 수 있다. 키 회전을 반영하면서
# 호출 수를 묶는 선택이며 측정하지 않았다
JWKS_REFETCH_SECONDS = 60.0
JWKS_TIMEOUT_SECONDS = 5.0  # 왜 5: IdP 한 곳에 오래 매이지 않으려는 선택이며 측정하지 않았다


class JwksKeys:
    """IdP 의 공개 키 집합(JWKS, RFC 7517)을 읽어 kid 로 서명 키를 준다. 발급자 디스커버리 문서의 jwks_uri
    를 쓸 수도 있다."""

    def __init__(
        self,
        issuer: str,
        jwks_url: str | None,
        *,
        client: httpx.AsyncClient,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._url = jwks_url
        self._client = client
        self._clock = clock
        self._keys: dict[str | None, Any] = {}
        self._fetched: float | None = None

    async def _refresh(self) -> None:
        url = self._url
        if url is None:
            discovery = await self._client.get(
                f"{self._issuer}/.well-known/openid-configuration", timeout=JWKS_TIMEOUT_SECONDS
            )
            discovery.raise_for_status()
            url = str(discovery.json()["jwks_uri"])
        response = await self._client.get(url, timeout=JWKS_TIMEOUT_SECONDS)
        response.raise_for_status()
        keys: dict[str | None, Any] = {}
        for jwk in response.json()["keys"]:
            if jwk.get("use", "sig") == "sig":
                keys[jwk.get("kid")] = jwt.PyJWK(jwk).key
        self._keys, self._fetched = keys, self._clock()

    async def __call__(self, kid: str | None) -> Any:  # noqa: ANN401
        stale = self._fetched is None or self._clock() - self._fetched >= JWKS_REFETCH_SECONDS
        if kid not in self._keys and stale:
            try:
                await self._refresh()
            except (httpx.HTTPError, KeyError, ValueError) as error:
                raise ApiError(401, authenticate=INVALID_TOKEN) from error
        if kid in self._keys:
            return self._keys[kid]
        if kid is None and len(self._keys) == 1:
            return next(iter(self._keys.values()))
        raise ApiError(401, authenticate=INVALID_TOKEN)
