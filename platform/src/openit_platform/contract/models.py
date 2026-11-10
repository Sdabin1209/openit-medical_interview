# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, RootModel


class AccessTokenType(StrEnum):
    """
    JWT 접근 토큰의 JOSE 헤더 typ 값. 서비스는 두 표기 중 하나가 아닌 토큰을 거절한다
    """

    at_jwt = 'at+jwt'
    application_at_jwt = 'application/at+jwt'


class AlertReceiverUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['mailto:alerts@example.org'])]
    """
    감시 경보를 받을 주소(https 웹훅 또는 mailto)
    """


class AlertStreamHeartbeatSeconds(RootModel[Literal[15]]):
    root: Annotated[Literal[15], Field(ge=15, le=15)]
    """
    알림 스트림이 아무 이벤트가 없을 때 heartbeat 를 보내는 간격(초)
    """


class CaMode(StrEnum):
    """
    영역 사이 TLS 를 발급하는 사설 CA 의 방식
    """

    self = 'self'
    organization = 'organization'


class DeviceId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['kiosk-01'], max_length=64, pattern='^[A-Za-z0-9._-]+$')
    ]
    """
    키오스크 기기의 식별자. 기기 인증서 주체의 CN 값이다
    """


class DeviceSerialNumber(RootModel[str]):
    root: Annotated[
        str, Field(examples=['1a2b3c4d'], max_length=40, pattern='^[0-9a-f]{1,40}$')
    ]
    """
    기기 인증서의 일련번호(소문자 16진수)
    """


class ExposureAudience(StrEnum):
    """
    경로를 누구에게 여는지
    """

    HUMAN_OIDC = 'HUMAN_OIDC'
    DEVICE_MTLS = 'DEVICE_MTLS'
    MACHINE_TOKEN = 'MACHINE_TOKEN'
    EXTERNAL_MACHINE_TOKEN = 'EXTERNAL_MACHINE_TOKEN'
    DENIED = 'DENIED'


class ForwardedClientCertValue(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                'Hash=468ed33be74eee6556d90c0149c1309e9ba61d6425303443c0748a02dd8de688;Subject="CN=kiosk-01"'
            ],
            max_length=8000,
        ),
    ]
    """
    Envoy 의 X-Forwarded-Client-Cert 헤더 값(By, Hash, Subject, URI 같은 요소를 세미콜론으로 이은 글). 기기 ID 는 Subject 의 CN 이다
    """


class GatewayConnectLimitSeconds(RootModel[Literal[1]]):
    root: Annotated[Literal[1], Field(ge=1, le=1)]
    """
    영역 게이트웨이가 상류에 연결하는 데 쓰는 상한(초)
    """


class GatewayPatientRouteLimitSeconds(RootModel[Literal[55]]):
    root: Annotated[Literal[55], Field(ge=55, le=55)]
    """
    환자·직원 경로에서 게이트웨이가 상류의 응답 머리글을 기다리는 상한(초)
    """


class HostName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['inference.example.org'],
            max_length=253,
            pattern='^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])\\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\\-]{0,61}[A-Za-z0-9])$',
        ),
    ]
    """
    서버를 가리키는 DNS 호스트 이름(예를 들어 survey-service 나 inference.example)
    """


class HttpMethodName(StrEnum):
    """
    경로에 허용하는 HTTP 메서드
    """

    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class IngressCertificateMode(StrEnum):
    """
    공개 입구가 쓰는 TLS 인증서를 얻는 방식
    """

    acme_public = 'acme-public'
    organization = 'organization'
    private = 'private'


class Ipv4Address(RootModel[IPv4Address]):
    root: Annotated[IPv4Address, Field(examples=['192.0.2.10'])]
    """
    IPv4 주소(점으로 구분한 십진 표기)
    """


class Ipv6Address(RootModel[IPv6Address]):
    root: Annotated[IPv6Address, Field(examples=['2001:db8::10'])]
    """
    IPv6 주소(콜론 표기, IPv4 가 섞인 표기 포함)
    """


class JwsAlgorithmName(RootModel[str]):
    root: Annotated[str, Field(max_length=16)]
    """
    JWS 서명 알고리즘 이름(예를 들어 RS256, ES256). none 은 허용하지 않는다
    """


class ListenPort(RootModel[int]):
    root: Annotated[int, Field(examples=[8080], ge=1, le=65535)]
    """
    서비스가 요청을 받는 TCP 포트 번호
    """


class MachineClientName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['survey-service'],
            max_length=63,
            pattern='^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$',
        ),
    ]
    """
    기계 토큰을 쓰는 호출자의 이름(서비스 이름 또는 외부 시스템 이름)
    """


class MachineRole(StrEnum):
    """
    기계 토큰에 부여하는 권한 이름. 작업마다 받는 영역이 요구한다
    """

    result_reader = 'result-reader'
    risk_detector = 'risk-detector'
    inference_caller = 'inference-caller'
    case_reader = 'case-reader'


class NumericDate(RootModel[int]):
    root: Annotated[int, Field(examples=[1783684200], ge=0, le=253402300799)]
    """
    JWT 의 시각 클레임(1970-01-01T00:00:00Z 부터의 초)
    """


class OidcClientId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['admin-console'], max_length=255, min_length=1)
    ]
    """
    토큰을 받은 클라이언트의 식별자(client_id 클레임)
    """


class OidcIssuerUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['https://platform/realms/openit'])]
    """
    사람 인증(OIDC) 발급자의 주소. 설치처마다 다르다
    """


class PreferredUsername(RootModel[str]):
    root: Annotated[str, Field(examples=['dr.kim'], max_length=255)]
    """
    사람이 읽는 계정 이름(화면 표시용). 권한 판단에는 쓰지 않는다
    """


class RoutePathPrefix(RootModel[str]):
    root: Annotated[str, Field(examples=['/v1/results'], max_length=8000, pattern='^/')]
    """
    노출하는 경로의 앞부분(항상 /로 시작)
    """


class SecretFilePath(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['/run/secrets/openit_database_password'],
            max_length=4096,
            pattern='^/',
        ),
    ]
    """
    비밀 값이 든 파일의 절대 경로. 값은 환경 변수나 설정에 적지 않고 이 파일에서만 읽는다
    """


class ServiceName(StrEnum):
    """
    계약에 나오는 상시 서비스(컨테이너 이미지가 하나인 단위)의 이름. 상시 서버가 없는 학습 파이프라인(model-lab)과 도구(deploy)는 서비스가 아니다
    """

    survey_service = 'survey-service'
    model_runtime = 'model-runtime'
    platform = 'platform'
    kiosk_frontend = 'kiosk-frontend'
    admin_console = 'admin-console'


class TokenAudienceClaim1(RootModel[list[ServiceName]]):
    root: Annotated[list[ServiceName], Field(max_length=5, min_length=1)]
    """
    접근 토큰의 aud 클레임. RFC 9068 은 문자열 하나나 문자열 배열을 허용하며, 이 프로젝트는 자기 서비스 이름이 aud 에 들어 있는 토큰만 받는다(로컬 프로파일)
    """


class TokenAudienceClaim(RootModel[ServiceName | TokenAudienceClaim1]):
    root: ServiceName | TokenAudienceClaim1
    """
    접근 토큰의 aud 클레임. RFC 9068 은 문자열 하나나 문자열 배열을 허용하며, 이 프로젝트는 자기 서비스 이름이 aud 에 들어 있는 토큰만 받는다(로컬 프로파일)
    """


class TokenId(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['c0a8f3a2-7a41-4b86-9b5e-0d1e2f3a4b5c'],
            max_length=255,
            min_length=1,
        ),
    ]
    """
    토큰의 고유 식별자(jti 클레임)
    """


class UserId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['6f1c1c52-8e0e-4f1f-9a16-2b3d4c5e6f70'], max_length=255)
    ]
    """
    사람 계정의 고유 식별자(OIDC 의 sub 값). 승인·검토·확인 기록에 남는다
    """


class UserRole(StrEnum):
    """
    사람 계정에 부여하는 역할. Keycloak 의 realm 역할 이름과 같다
    """

    staff = 'staff'
    clinician = 'clinician'
    author = 'author'
    reviewer = 'reviewer'
    release_approver = 'release-approver'
    operator = 'operator'
    admin = 'admin'


class AccessTokenHeader(BaseModel):
    """
    서비스가 JWT 접근 토큰의 JOSE 헤더에서 확인하는 칸. 그 밖의 헤더 칸은 허용한다
    """

    alg: JwsAlgorithmName
    """
    서명 알고리즘. none 이면 거절한다
    """
    typ: AccessTokenType
    """
    토큰 종류. at+jwt 가 아니면 거절한다
    """


class DeviceAllowEntry(BaseModel):
    """
    공개 입구가 허용하는 키오스크 기기 인증서 하나
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    device_id: DeviceId
    """
    기기 식별자(인증서 주체 CN)
    """
    serial_number: DeviceSerialNumber
    """
    허용하는 인증서의 일련번호
    """


class DeviceAllowlist(BaseModel):
    """
    공개 입구에 deploy 가 파일로 주는 키오스크 기기 허용 목록. 등록·회전·폐기는 이 목록을 바꾸는 것이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    devices: Annotated[list[DeviceAllowEntry], Field(max_length=1000)]
    """
    허용하는 기기 인증서들
    """


class ExposureRoute(BaseModel):
    """
    영역이 노출하는 경로 하나와 그 대상
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    audience: ExposureAudience
    """
    이 경로를 여는 대상
    """
    methods: Annotated[list[HttpMethodName], Field(max_length=4, min_length=1)]
    """
    허용하는 메서드들
    """
    path_prefix: RoutePathPrefix
    """
    노출하는 경로의 앞부분
    """


class HostAddress(RootModel[HostName | Ipv4Address | Ipv6Address]):
    root: HostName | Ipv4Address | Ipv6Address
    """
    서버의 호스트 이름 또는 IP 주소
    """


class MachineTokenEntry(BaseModel):
    """
    기계 호출자 하나와 그에게 허용한 권한, 토큰이 든 파일의 경로
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    client: MachineClientName
    """
    호출자 이름
    """
    roles: Annotated[list[MachineRole], Field(max_length=4)]
    """
    이 호출자에게 허용한 권한들
    """
    token_file: SecretFilePath
    """
    토큰 값이 든 파일의 경로(값은 이 표에 적지 않는다)
    """


class MachineTokenTable(BaseModel):
    """
    받는 영역이 기계 호출자를 가르는 표(배포가 파일로 준다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    tokens: Annotated[list[MachineTokenEntry], Field(max_length=4)]
    """
    호출자별 권한과 토큰 파일
    """


class RealmAccessClaim(BaseModel):
    """
    OIDC 접근 토큰 안의 역할 묶음(Keycloak realm_access 클레임)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    roles: Annotated[list[UserRole], Field(max_length=7)]
    """
    이 사람에게 부여된 역할들
    """


class UserIdentityClaims(BaseModel):
    """
    서비스가 반드시 확인하는 JWT 접근 토큰 클레임(RFC 9068 의 필수 클레임 iss, exp, aud, sub, client_id, iat, jti 와 역할). 서명은 IdP 공개 키(JWKS)로 서비스가 검증하고 그 밖의 클레임은 허용한다. 열린 객체라 allOf 로 객체 유형만 요구한다
    """

    aud: TokenAudienceClaim
    """
    이 토큰을 받는 서비스. 자기 이름이 없으면 거절한다
    """
    client_id: OidcClientId
    """
    토큰을 받은 클라이언트
    """
    exp: NumericDate
    """
    토큰이 만료되는 때. 지난 토큰은 거절한다
    """
    iat: NumericDate
    """
    토큰을 발급한 때
    """
    iss: OidcIssuerUrl
    """
    토큰을 발급한 IdP 의 주소. 환경 입력의 발급자와 같아야 한다
    """
    jti: TokenId
    """
    토큰의 고유 식별자
    """
    preferred_username: PreferredUsername | None = None
    """
    화면 표시용 계정 이름
    """
    realm_access: RealmAccessClaim
    """
    부여된 역할
    """
    sub: UserId
    """
    사람 계정 식별자
    """


class ExternalEgressTarget(BaseModel):
    """
    영역 밖(설치처 밖 포함)의 나가는 호출 상대 하나. 호스트는 설치처 설정에서 온다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    host: HostAddress
    """
    상대의 호스트 이름 또는 IP 주소
    """
    port: ListenPort
    """
    상대의 포트
    """


class EgressTarget(RootModel[ServiceName | ExternalEgressTarget]):
    root: ServiceName | ExternalEgressTarget
    """
    나가는 호출 상대 하나(이 계약의 서비스 또는 영역 밖의 호스트와 포트)
    """


class Exposure(BaseModel):
    """
    영역이 선언하는 노출 경로와 나가는 호출 상대. deploy 가 이것으로 게이트웨이 구성을 만들고, 경로가 겹치면 시작하지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    egress: Annotated[list[EgressTarget], Field(max_length=32)]
    """
    나가는 호출이 닿을 수 있는 상대들(서비스와 영역 밖 호스트)
    """
    routes: Annotated[list[ExposureRoute], Field(max_length=29)]
    """
    노출 경로들
    """
