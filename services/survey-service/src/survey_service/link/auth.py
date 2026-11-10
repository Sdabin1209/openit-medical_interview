"""인증: 신원은 platform 이 넘긴 것만 쓴다(사람·기계 JWT 접근 토큰, 기기 mTLS 헤더). 본문의 신원은 쓰지 않는다.

- 사람과 기계: JWT 접근 토큰(RFC 9068 프로파일, contracts/README). 서명은 IdP 의 공개 키 집합(JWKS)으로,
  iss·aud·exp·iat 와 typ·alg 를 확인하고 역할은 realm_access.roles 에서 읽는다. 기계 토큰은 client_id 가
  machine-<호출자 이름> 이고 역할이 MachineRole 인 토큰(MachineIdentityClaims)이다. 어느 쪽인지는 값이 계약
  스키마(MachineIdentityClaims, UserIdentityClaims) 중 어느 것에 맞는지로 가른다(ADR 0014).
- 기기: Envoy 표준 헤더 X-Forwarded-Client-Cert 의 Subject CN 이 기기 ID 다. 서비스는 이 헤더를 믿는다. 왜 믿나:
  서비스 컨테이너는 영역 전용 내부 네트워크에서 평문 HTTP 로 듣고 그 네트워크에는 영역 게이트웨이만 닿는다. 게이트웨이는
  클라이언트 인증서를 검증하고 입구의 인증서로 온 요청에서만 헤더를 넘기며 그 밖의 요청에서는 지운다(계약 device_mtls,
  ADR 0015). 그래서 서비스는 헤더의 출처를 따로 확인하지 않는다. 이 근거가 깨지면(서비스가 게이트웨이 밖에 닿으면)
  누구나 기기를 사칭할 수 있으므로 배포가 네트워크 구성을 지켜야 한다.
"""

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Header, Request
from pydantic import ValidationError

from survey_service.contract.models import (
    AccessTokenHeader,
    DeviceId,
    MachineIdentityClaims,
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


# 왜 이 접두어: 계약 MachineOidcClientId 의 형식이 machine-<호출자 이름>(platform-002)이다
MACHINE_CLIENT_PREFIX = "machine-"


def load_machine_callers(table_file: str) -> dict[str, frozenset[str]]:
    """기계 호출자 표 파일(MachineTokenTable)을 읽어 호출자 이름 -> 허용 역할로 만든다.

    왜 client_secret_file 을 읽지 않나: 그 파일은 호출자가 토큰을 받을 때 쓰는 비밀이다. 받는 쪽은 JWT 를 서명으로
    검증하므로 비밀이 필요 없다.
    """
    table = MachineTokenTable.model_validate_json(Path(table_file).read_text(encoding="utf-8"))
    return {entry.client.root: frozenset(role.value for role in entry.roles) for entry in table.tokens}


@dataclass(frozen=True)
class Authenticator:
    """요청의 신원을 가르는 도구. main 이 만들어 라우터에 넣는다."""

    issuer: str
    audience: str
    key_for: KeyFor
    machines: dict[str, frozenset[str]]
    # 왜 주입: exp·iat 를 이 시계로 가른다. 시험이 실제 시각 없이 만료를 정한다(PyJWT 는 시계를 주입받지 않는다)
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def _check_times(self, claims: dict[str, Any]) -> None:
        """exp 가 지났거나 iat·nbf 가 아직 오지 않았으면 거부한다(RFC 7519 4.1.4~4.1.6, 여유 시간 0)."""
        at = self.now().timestamp()
        exp, iat, nbf = claims["exp"], claims["iat"], claims.get("nbf")
        for value in (exp, iat) if nbf is None else (exp, iat, nbf):
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise jwt.InvalidTokenError("시각 클레임이 숫자가 아니다")
        if exp <= at:
            raise jwt.ExpiredSignatureError("exp")
        if iat > at or (nbf is not None and nbf > at):
            raise jwt.ImmatureSignatureError("iat/nbf")

    async def _claims(self, token: str) -> dict[str, Any]:
        """JWT 접근 토큰 검증(RFC 9068). 서명·iss·aud·exp·헤더 중 하나라도 어기면 401."""
        try:
            raw_header = jwt.get_unverified_header(token)
            header = AccessTokenHeader.model_validate(raw_header)
            if header.alg.root.lower() == "none":
                raise ValueError("alg none")
            key = await self.key_for(raw_header.get("kid"))
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[header.alg.root],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub", "jti", "client_id"],
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
            self._check_times(claims)
            return claims
        except (jwt.PyJWTError, ValidationError, ValueError, KeyError) as error:
            raise ApiError(401, authenticate=INVALID_TOKEN) from error

    async def principal(self, token: str) -> Principal:
        """토큰의 호출자. 기계 토큰이면 표의 허용 역할과 토큰의 역할이 모두 허용한 역할만 남긴다(ADR 0014).

        왜 둘의 교집합: 표는 이 서비스가 받기로 한 호출자와 그에게 준 역할이고 토큰의 역할은 IdP 가 부여한 것이다.
        어느 한쪽만 틀려도 권한이 넓어지지 않게 한다. 표에 없는 호출자는 역할이 비어 403 이 된다(신원은 확인됐다).
        """
        claims = await self._claims(token)
        try:
            machine = MachineIdentityClaims.model_validate(claims)
        except ValidationError:
            pass
        else:
            caller = machine.client_id.root.removeprefix(MACHINE_CLIENT_PREFIX)
            granted = frozenset(role.value for role in machine.realm_access.roles)
            return Principal(
                kind=PrincipalKind.MACHINE, subject=caller, roles=granted & self.machines.get(caller, frozenset())
            )
        try:
            human = UserIdentityClaims.model_validate(claims)
        except ValidationError as error:
            raise ApiError(401, authenticate=INVALID_TOKEN) from error
        return Principal(
            kind=PrincipalKind.HUMAN,
            subject=human.sub.root,
            roles=frozenset(role.value for role in human.realm_access.roles),
        )


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
        principal = await auth.principal(_bearer(authorization))
        allowed = {role.value for role in (machines if principal.kind is PrincipalKind.MACHINE else humans)}
        if principal.roles & allowed:
            return principal
        raise ApiError(403)  # 왜 401 이 아닌가: 토큰은 맞고 이 작업의 역할이 없다(D58)

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
