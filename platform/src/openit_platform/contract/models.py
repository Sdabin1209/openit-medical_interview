# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class AccessTokenType(StrEnum):
    """
    JWT 접근 토큰의 JOSE 헤더 typ 값. 서비스는 두 표기 중 하나가 아닌 토큰을 거절한다
    """

    at_jwt = 'at+jwt'
    application_at_jwt = 'application/at+jwt'


class AcmeDirectoryUrl(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['https://acme-v02.api.letsencrypt.org/directory'],
            max_length=8000,
            pattern='^https://',
        ),
    ]
    """
    ACME 서버의 디렉터리 주소(공개 입구 인증서를 공인 ACME CA 에서 받을 때)
    """


class AlertHeartbeatInterval(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['5m'], max_length=32, pattern='^([1-9][0-9]*(ms|s|m|h|d|w|y))+$'
        ),
    ]
    """
    서버 전체가 멈췄음을 수신처가 알아차리게 하는 생존 신호(Watchdog 경보)를 보내는 간격(Prometheus 기간 표기)
    """


class AlertReceiverUrl(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['mailto:alerts@example.org'],
            max_length=8000,
            pattern='^(https://|mailto:)',
        ),
    ]
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


class ConfigFilePath(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['/etc/openit/machine-tokens.json'], max_length=4096, pattern='^/'
        ),
    ]
    """
    비밀이 아닌 설정 파일 또는 폴더의 절대 경로
    """


class DatabaseUrl(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['postgresql://survey-db:5432/survey'],
            max_length=8000,
            pattern='^postgresql://',
        ),
    ]
    """
    자기 영역 데이터베이스의 접속 주소(비밀번호는 넣지 않는다)
    """


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


class LogLevel(StrEnum):
    """
    표준 출력으로 내는 로그의 최소 수준
    """

    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


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


class MachineOidcClientId(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['machine-survey-service'],
            max_length=71,
            pattern='^machine-[a-z]([a-z0-9-]{0,61}[a-z0-9])?$',
        ),
    ]
    """
    기계 호출자의 Keycloak 클라이언트 식별자(client_id 클레임). machine- 다음에 호출자 이름(MachineClientName)이 온다
    """


class MachineRole(StrEnum):
    """
    기계 토큰에 부여하는 권한 이름. 작업마다 받는 영역이 요구한다
    """

    result_reader = 'result-reader'
    risk_detector = 'risk-detector'
    inference_caller = 'inference-caller'
    case_reader = 'case-reader'


class MachineSubjectId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['0b8c7d3e-91a4-4c1f-8e55-3a6d2f4b7c10'], max_length=255)
    ]
    """
    기계 호출자의 서비스 계정 식별자(토큰의 sub 값)
    """


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


class OidcIssuerUrl(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['https://platform/realms/openit'],
            max_length=8000,
            pattern='^https://',
        ),
    ]
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


class SmtpSmarthost(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['smtp.example.org:587'],
            max_length=259,
            pattern='^[A-Za-z0-9.-]{1,253}:(6553[0-5]|655[0-2][0-9]|65[0-4][0-9]{2}|6[0-4][0-9]{3}|[1-5][0-9]{4}|[1-9][0-9]{0,3})$',
        ),
    ]
    """
    감시 경보 메일을 내보낼 SMTP 서버의 호스트와 포트(호스트:포트)
    """


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


class UnprivilegedListenPort(RootModel[int]):
    root: Annotated[int, Field(examples=[8443], ge=1024, le=65535)]
    """
    비 root 프로세스가 열 수 있는 TCP 포트 번호(1024 이상). 입구(Envoy)와 영역 게이트웨이(Caddy)는 비 root 로 돌아 낮은 포트를 열지 못한다
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


class MachineRealmAccessClaim(BaseModel):
    """
    기계 접근 토큰 안의 역할 묶음(Keycloak realm_access 클레임). 역할은 기계 권한(MachineRole)이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    roles: Annotated[list[MachineRole], Field(max_length=4)]
    """
    이 호출자에게 부여된 권한들
    """


class MachineTokenEntry(BaseModel):
    """
    기계 호출자 하나와 그에게 허용한 권한, 그 호출자의 Keycloak 기계 클라이언트 비밀이 든 파일의 경로
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    client: MachineClientName
    """
    호출자 이름
    """
    client_secret_file: SecretFilePath
    """
    호출자의 Keycloak 기계 클라이언트 비밀 파일의 경로(클라이언트 ID 는 machine-<client>, 값은 이 표에 적지 않는다)
    """
    roles: Annotated[list[MachineRole], Field(max_length=4)]
    """
    이 호출자에게 허용한 권한들
    """


class MachineTokenTable(BaseModel):
    """
    기계 호출자 표(호출자 이름, 권한, 클라이언트 비밀 파일의 경로. 비밀은 없다). platform 이 이 표로 Keycloak 기계 클라이언트와 그 서비스 계정의 역할을 만들고 배포가 파일로 준다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    tokens: Annotated[list[MachineTokenEntry], Field(max_length=4)]
    """
    호출자별 권한과 클라이언트 비밀 파일
    """


class PlatformEnv(BaseModel):
    """
    deploy 가 platform 에 주는 환경 입력
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    OPENIT_ACME_DIRECTORY_URL: AcmeDirectoryUrl | None = None
    """
    ACME 서버 디렉터리 주소(공개 입구 인증서 방식이 acme-public 일 때 필수). 필요한 컴포넌트: gateway
    """
    OPENIT_ALERT_HEARTBEAT_INTERVAL: AlertHeartbeatInterval | None = None
    """
    생존 신호(Watchdog 경보)를 보내는 간격(선택). 필요한 컴포넌트: monitoring
    """
    OPENIT_ALERT_RECEIVER_URL: AlertReceiverUrl
    """
    감시 경보 수신처. 필요한 컴포넌트: monitoring
    """
    OPENIT_ALERT_SMTP_SMARTHOST: SmtpSmarthost | None = None
    """
    감시 경보 메일을 내보낼 SMTP 서버(OPENIT_ALERT_RECEIVER_URL 이 mailto 일 때 필수, 선택). 필요한 컴포넌트: monitoring
    """
    OPENIT_CA_MODE: CaMode
    """
    사설 CA 의 방식. 필요한 컴포넌트: ca
    """
    OPENIT_CA_PASSWORD_FILE: SecretFilePath
    """
    사설 CA(step-ca)의 키 암호 파일. 필요한 컴포넌트: ca
    """
    OPENIT_DEVICE_ALLOWLIST_FILE: ConfigFilePath
    """
    기기 허용 목록 파일(DeviceAllowlist 모양). 필요한 컴포넌트: gateway
    """
    OPENIT_DEVICE_CA_CERTIFICATE_FILE: ConfigFilePath
    """
    기기 인증서를 발급하는 조직 PKI 의 루트 인증서 파일. 필요한 컴포넌트: gateway
    """
    OPENIT_EXPOSURES_DIR: ConfigFilePath
    """
    영역들의 노출 선언(Exposure)을 모은 폴더. 공개 입구가 이것으로 경로를 구성하고 같은 공개 경로를 두 영역이 열면 시작하지 않는다. 필요한 컴포넌트: gateway
    """
    OPENIT_IDP_ADMIN_PASSWORD_FILE: SecretFilePath
    """
    사람 인증(Keycloak)의 초기 admin 계정 임시 비밀번호 파일. 필요한 컴포넌트: identity
    """
    OPENIT_IDP_DATABASE_PASSWORD_FILE: SecretFilePath
    """
    사람 인증 데이터베이스 비밀번호 파일. 필요한 컴포넌트: identity
    """
    OPENIT_IDP_DATABASE_URL: DatabaseUrl
    """
    사람 인증(Keycloak) 데이터베이스 접속 주소. 필요한 컴포넌트: identity
    """
    OPENIT_INGRESS_CERTIFICATE_FILE: ConfigFilePath | None = None
    """
    조직이 발급한 입구 인증서 파일(OPENIT_INGRESS_CERTIFICATE_MODE 가 organization 일 때 필수, 선택). 필요한 컴포넌트: gateway
    """
    OPENIT_INGRESS_CERTIFICATE_MODE: IngressCertificateMode
    """
    공개 입구 인증서를 얻는 방식. 필요한 컴포넌트: gateway, ca
    """
    OPENIT_INGRESS_PRIVATE_KEY_FILE: SecretFilePath | None = None
    """
    조직이 발급한 입구 인증서의 개인키 파일(OPENIT_INGRESS_CERTIFICATE_MODE 가 organization 일 때 필수, 선택). 필요한 컴포넌트: gateway
    """
    OPENIT_LISTEN_PORT: UnprivilegedListenPort
    """
    공개 입구가 요청을 받는 포트. 필요한 컴포넌트: gateway
    """
    OPENIT_LOG_LEVEL: LogLevel | None = None
    """
    로그 수준. 필요한 컴포넌트: 모든 컴포넌트
    """
    OPENIT_MACHINE_TOKENS_FILE: ConfigFilePath
    """
    호출자 표 파일(MachineTokenTable 모양, 비밀은 없다). 입구가 기계 토큰 경로를 가르고 identity 가 Keycloak 기계 클라이언트와 역할을 만든다. 필요한 컴포넌트: gateway, identity
    """
    OPENIT_OIDC_ISSUER_URL: OidcIssuerUrl
    """
    사람 인증(OIDC) 발급자 주소. 서비스가 접근 토큰의 iss 를 확인할 때 쓴다. 필요한 컴포넌트: identity, identity_proxy, gateway
    """
    OPENIT_PUBLIC_NAMES: Annotated[
        list[HostName] | None, Field(max_length=32, min_length=1)
    ] = None
    """
    입구 인증서의 이름(SAN)이자 입구가 서비스하는 이름들. OPENIT_OIDC_ISSUER_URL 의 호스트가 이 안에 있어야 한다(선택). 필요한 컴포넌트: gateway, ca
    """
    OPENIT_SERVICE_PORT: UnprivilegedListenPort | None = None
    """
    입구와 감시가 영역 서비스(https://<서비스 이름>)에 접속하는 포트(선택). 모든 영역 서비스가 같은 포트를 쓰며, 서비스 컨테이너가 영역 안 평문 HTTP 로 듣는 OPENIT_LISTEN_PORT 와는 별개다(요청은 영역 게이트웨이가 받는다). 필요한 컴포넌트: gateway, monitoring
    """
    OPENIT_TLS_ROOT_CERTIFICATE_FILE: ConfigFilePath
    """
    영역 사이 TLS 의 루트 인증서 파일(모든 서비스에 OPENIT_ROOT_CERTIFICATE_FILE 로 나눠 준다). 필요한 컴포넌트: ca, gateway
    """
    OPENIT_TRUST_LIST_FILE: ConfigFilePath
    """
    신뢰할 CA 인증서 묶음 파일(조직 CA 방식이면 조직 CA 를 넣는다). 필요한 컴포넌트: gateway
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


class MachineIdentityClaims(BaseModel):
    """
    서비스가 기계 호출의 JWT 접근 토큰에서 반드시 확인하는 클레임(RFC 9068 의 필수 클레임과 기계 권한). 모양은 UserIdentityClaims 를 따르되 client_id 는 machine-<호출자 이름> 이고 역할은 MachineRole 이다. 서명은 IdP 공개 키(JWKS)로 검증하고 그 밖의 클레임은 허용한다. 열린 객체라 allOf 로 객체 유형만 요구한다
    """

    aud: TokenAudienceClaim
    """
    이 토큰을 받는 서비스. 자기 이름이 없으면 거절한다
    """
    client_id: MachineOidcClientId
    """
    토큰을 받은 기계 클라이언트
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
    realm_access: MachineRealmAccessClaim
    """
    부여된 기계 권한
    """
    sub: MachineSubjectId
    """
    기계 호출자의 서비스 계정 식별자
    """


class EgressTarget(RootModel[ServiceName | ExternalEgressTarget]):
    root: ServiceName | ExternalEgressTarget
    """
    나가는 호출 상대 하나(이 계약의 서비스 또는 영역 밖의 호스트와 포트). 서비스 이름 platform 은 사람·기계 토큰의 발급자(OIDC 발급자 주소의 호스트와 포트)로 나가는 터널을 뜻한다. 발급자 주소는 설치처 값이라 선언에 못 박지 못한다. 토큰 검증(JWKS)이나 기계 토큰 발급이 필요한 서비스는 egress 에 platform 을 선언한다
    """


class Exposure(BaseModel):
    """
    영역이 선언하는 노출 경로와 나가는 호출 상대. deploy 가 이것으로 게이트웨이 구성을 만들고, 경로가 겹치면 시작하지 않는다. 노출 선언은 경로와 대상만 정한다. 경로가 요구하는 역할의 정본은 OpenAPI 3.1 의 작업 security 요구이고 입구 설정 생성기가 노출 선언과 계약 작업의 인증 요구를 곱해 라우트를 만든다(입구가 읽는 것은 영역 코드가 아니라 헤드 소유 계약이다)
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
