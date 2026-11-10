# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class AccessTokenType(StrEnum):
    """
    JWT 접근 토큰의 JOSE 헤더 typ 값. 서비스는 두 표기 중 하나가 아닌 토큰을 거절한다
    """

    at_jwt = 'at+jwt'
    application_at_jwt = 'application/at+jwt'


class ActionReason(StrEnum):
    """
    절차의 사유(모델 입출력 v2). NEXT 와 CORRECT 에는 붙지 않는다
    """

    CONFLICT_WITH_PREVIOUS = 'CONFLICT_WITH_PREVIOUS'
    CONFLICT_MAX_BELOW_USUAL = 'CONFLICT_MAX_BELOW_USUAL'
    CONFLICT_DOES_NOT_DRINK = 'CONFLICT_DOES_NOT_DRINK'
    REQUEST_SKIP = 'REQUEST_SKIP'
    REFUSED = 'REFUSED'
    OUT_OF_SCHEMA = 'OUT_OF_SCHEMA'
    ASK_PURPOSE = 'ASK_PURPOSE'
    OFF_TOPIC = 'OFF_TOPIC'
    UNCERTAIN = 'UNCERTAIN'
    MISSING = 'MISSING'
    OUT_OF_RANGE = 'OUT_OF_RANGE'
    UNKNOWN_UNIT = 'UNKNOWN_UNIT'
    VAGUE_QUANTITY = 'VAGUE_QUANTITY'
    OTHER_BEVERAGE = 'OTHER_BEVERAGE'
    BEVERAGE_MISSING = 'BEVERAGE_MISSING'
    MISSING_NUMBER = 'MISSING_NUMBER'
    RANGE_SPANS_OPTIONS = 'RANGE_SPANS_OPTIONS'
    INVALID_OPTION = 'INVALID_OPTION'
    COUNT_EXCEEDS_DAYS = 'COUNT_EXCEEDS_DAYS'
    UNPARSED_VALUE = 'UNPARSED_VALUE'


class AlertEventName(StrEnum):
    """
    알림 스트림(SSE)의 이벤트 이름
    """

    alert = 'alert'
    resolved = 'resolved'
    heartbeat = 'heartbeat'
    resync = 'resync'


class AlertId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    직원 알림 하나의 식별자
    """


class AlertKind(StrEnum):
    """
    알림의 종류
    """

    RISK = 'RISK'
    CALL_STAFF = 'CALL_STAFF'
    RESULT_READY = 'RESULT_READY'


class AlertStreamHeartbeatSeconds(RootModel[Literal[15]]):
    root: Annotated[Literal[15], Field(ge=15, le=15)]
    """
    알림 스트림이 아무 이벤트가 없을 때 heartbeat 를 보내는 간격(초)
    """


class AuthenticateChallenge(RootModel[str]):
    root: Annotated[str, Field(examples=['Bearer realm="openit"'], max_length=8000)]
    """
    WWW-Authenticate 헤더 값(예를 들어 Bearer realm 과 error 를 담은 도전)
    """


class BackupSnapshotId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['79766175'], max_length=64, pattern='^[0-9a-f]{8,64}$')
    ]
    """
    백업 스냅샷 하나의 식별자(restic 스냅샷 ID 의 16진수 표기)
    """


class BlankReason(StrEnum):
    """
    결과에서 칸이 비어 있는 원인. 모델 사유에서 옮기는 규칙은 HOLD(UNCERTAIN)가 UNKNOWN, SKIP(REFUSED)이 REJECTED, SKIP(REQUEST_SKIP)이 REJECTED, 값을 정하지 못한 REASK(UNCLEAR 계열)가 UNCLEAR, 서비스가 한도로 건너뛴 것이 REASK_LIMIT, 묻지 못한 것이 UNASKED 다
    """

    UNKNOWN = 'UNKNOWN'
    REJECTED = 'REJECTED'
    UNCLEAR = 'UNCLEAR'
    REASK_LIMIT = 'REASK_LIMIT'
    UNASKED = 'UNASKED'


class CaseId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    실패 사례 하나의 식별자
    """


class CaseVersion(RootModel[int]):
    root: Annotated[int, Field(examples=[2], ge=1, le=2147483647)]
    """
    같은 사례의 검토 버전 순번(검토 내용이 바뀔 때마다 오른다)
    """


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


class DatabaseUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['postgresql://survey-db:5432/survey'])]
    """
    자기 영역 데이터베이스의 접속 주소(비밀번호는 넣지 않는다)
    """


class DeidentifiedUtterance(RootModel[str]):
    root: Annotated[
        str, Field(examples=['중풍 진단 받았고 약도 먹어요'], max_length=300)
    ]
    """
    비식별 처리를 마친 환자 발화(개인정보를 뺀 글)
    """


class DeviceId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['kiosk-01'], max_length=64, pattern='^[A-Za-z0-9._-]+$')
    ]
    """
    키오스크 기기의 식별자. 기기 인증서 주체의 CN 값이다
    """


class EgressProxyUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['http://127.0.0.1:3128'])]
    """
    영역 게이트웨이의 나가는 CONNECT 터널 주소. Exposure.egress 에 선언한 상대에게만 닿는다
    """


class EventSequence(RootModel[int]):
    root: Annotated[int, Field(examples=[42], ge=0, le=9007199254740991)]
    """
    알림 스트림 이벤트의 순번(SSE id). 재연결 때 Last-Event-ID 로 이어 받는다
    """


class ExplainStreakLimit(RootModel[int]):
    root: Annotated[int, Field(examples=[3], ge=3, le=3)]
    """
    한 문항에서 질문의 뜻·대상을 묻는 말만 이어질 수 있는 횟수. 닿으면 서비스가 고정 문장으로 직원 도움을 안내한다. 모델 입출력 v2 에는 이 분류가 없어 모델 입출력 v3 부터 동작한다
    """


class ExtractClientLimitSeconds(RootModel[Literal[21]]):
    root: Annotated[Literal[21], Field(ge=21, le=21)]
    """
    survey-service 가 추출 요청을 기다리는 상한(초)
    """


class ExtractionAction(StrEnum):
    """
    LoRA-A 가 이번 말에 대해 고른 절차(action)
    """

    NEXT = 'NEXT'
    CORRECT = 'CORRECT'
    REASK = 'REASK'
    CONFIRM = 'CONFIRM'
    HOLD = 'HOLD'
    SKIP = 'SKIP'
    REDIRECT = 'REDIRECT'


class FailureKind(StrEnum):
    """
    실패 사례를 찾아낸 탐지 규칙
    """

    EXTRACT_FAILED = 'EXTRACT_FAILED'
    REASK_STREAK = 'REASK_STREAK'


class FhirAbsentReason(StrEnum):
    """
    FHIR 의 data-absent-reason 코드 중 빈칸 표현에 쓰는 것
    """

    unknown = 'unknown'
    asked_unknown = 'asked-unknown'
    asked_declined = 'asked-declined'
    not_asked = 'not-asked'


class FhirCanonicalBaseUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['https://example.org/fhir/Questionnaire'])]
    """
    문진표의 정본 URL 을 만드는 기준 주소. 문진표의 canonical URL 은 이 주소 뒤에 슬래시와 문진표 식별자를 붙인 값이다. 설치처마다 다르다
    """


class FhirIssueCode(StrEnum):
    """
    FHIR OperationOutcome 문제 하나의 종류(이 계약의 FHIR 조회가 내는 값만 둔 부분집합)
    """

    login = 'login'
    forbidden = 'forbidden'
    not_found = 'not-found'
    transient = 'transient'


class FhirIssueSeverity(StrEnum):
    """
    FHIR OperationOutcome 문제 하나의 심각도
    """

    fatal = 'fatal'
    error = 'error'
    warning = 'warning'
    information = 'information'


class FhirOutcomeResourceType(RootModel[Literal['OperationOutcome']]):
    root: Literal['OperationOutcome']
    """
    FHIR 오류 리소스 유형 이름
    """


class FhirResourceType(RootModel[Literal['QuestionnaireResponse']]):
    root: Literal['QuestionnaireResponse']
    """
    FHIR 리소스 유형 이름
    """


class FhirResponseStatus(StrEnum):
    """
    FHIR R4 QuestionnaireResponse.status 의 코드 집합
    """

    in_progress = 'in-progress'
    completed = 'completed'
    amended = 'amended'
    entered_in_error = 'entered-in-error'
    stopped = 'stopped'


class FlowComparison(StrEnum):
    """
    건너뛰기 조건의 비교 연산
    """

    EQ = 'EQ'
    NE = 'NE'
    LT = 'LT'
    LE = 'LE'
    GT = 'GT'
    GE = 'GE'


class FlowTarget(RootModel[str]):
    root: Annotated[
        str, Field(examples=['Q4_1'], max_length=12, pattern='^(END|[A-Za-z0-9_.]+)$')
    ]
    """
    순서표와 LoRA-A 출력이 가리키는 다음 자리. 문항 식별자 또는 끝을 뜻하는 END
    """


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


class HealthCheckName(RootModel[str]):
    root: Annotated[str, Field(examples=['database'], max_length=63)]
    """
    점검 항목의 이름(예를 들어 database)
    """


class HealthStatus(StrEnum):
    """
    건강 점검 하나 또는 전체의 결과
    """

    pass_ = 'pass'
    warn = 'warn'
    fail = 'fail'


class HttpStatus(RootModel[int]):
    root: Annotated[int, Field(examples=[503], ge=400, le=599)]
    """
    오류 응답의 HTTP 상태 코드(클라이언트 오류 4xx, 서버 오류 5xx)
    """


class IdempotencyKeyValue(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    쓰기 요청의 재전송을 가리는 멱등 키(클라이언트가 만든 UUID)
    """


class ImageRevision(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['0123456789abcdef0123456789abcdef01234567'],
            max_length=64,
            pattern='^[0-9a-f]{40,64}$',
        ),
    ]
    """
    이미지를 만든 소스의 커밋 해시(소문자 16진수)
    """


class Int32Positive(RootModel[int]):
    root: Annotated[int, Field(examples=[3], ge=1, le=2147483647)]
    """
    1부터 시작하는 순번(32비트 정수 범위)
    """


class InterventionAction(StrEnum):
    """
    직원이 알림에 대해 내리는 결정
    """

    ACKNOWLEDGE = 'ACKNOWLEDGE'
    RESUME = 'RESUME'


class InterventionDecision(BaseModel):
    """
    직원이 멈춘 세션에 대해 내리는 개입 결정
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: InterventionAction
    """
    직원의 결정
    """


class JobExitCode(IntEnum):
    """
    잡이 끝나며 내는 종료 코드
    """

    integer_0 = 0
    integer_75 = 75
    integer_1 = 1


class JobName(StrEnum):
    """
    deploy 의 스케줄러가 한 번 실행하는 잡의 이름
    """

    IMPORT_DATASET = 'IMPORT_DATASET'
    PREPARE = 'PREPARE'
    TRAIN = 'TRAIN'
    EVALUATE = 'EVALUATE'
    PUBLISH = 'PUBLISH'
    DETECT_FAILURES = 'DETECT_FAILURES'
    PURGE_EXPIRED = 'PURGE_EXPIRED'
    BACKUP = 'BACKUP'
    RESTORE = 'RESTORE'
    OFFSITE_SYNC = 'OFFSITE_SYNC'
    RESTORE_TEST = 'RESTORE_TEST'


class JobTimeoutSeconds(RootModel[int]):
    root: Annotated[int, Field(examples=[600], ge=1, le=259200)]
    """
    잡 한 번이 끝나야 하는 시간 상한(초). deploy 가 이 값보다 큰 가장 작은 300초 배수를 주기로 정한다
    """


class JsonPointer(RootModel[str]):
    root: Annotated[str, Field(examples=['/user_utterance'], max_length=8000)]
    """
    요청 본문 안에서 잘못된 값의 위치(JSON 포인터)
    """


class JwsAlgorithmName(RootModel[str]):
    root: Annotated[str, Field(max_length=16)]
    """
    JWS 서명 알고리즘 이름(예를 들어 RS256, ES256). none 은 허용하지 않는다
    """


class KioskIdleResetSeconds(RootModel[Literal[60]]):
    root: Annotated[Literal[60], Field(ge=60, le=60)]
    """
    키오스크가 환자의 입력 없이 기다리다 세션을 초기화하는 시간(초). 멈춘 세션은 만료하지 않는다
    """


class KioskProgressNoticeSeconds(RootModel[Literal[1]]):
    root: Annotated[Literal[1], Field(ge=1, le=1)]
    """
    키오스크가 응답이 늦을 때 진행 표시를 보이기 시작하는 시간(초)
    """


class KioskRequestLimitSeconds(RootModel[Literal[60]]):
    root: Annotated[Literal[60], Field(ge=60, le=60)]
    """
    키오스크가 서버 응답을 기다리는 실패 판정 상한(초)
    """


class KioskRetryBudgetSeconds(RootModel[Literal[120]]):
    root: Annotated[Literal[120], Field(ge=120, le=120)]
    """
    키오스크가 같은 요청을 다시 보내는 데 쓸 수 있는 총 시간(초)
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


class MachineRole(StrEnum):
    """
    기계 토큰에 부여하는 권한 이름. 작업마다 받는 영역이 요구한다
    """

    result_reader = 'result-reader'
    risk_detector = 'risk-detector'
    inference_caller = 'inference-caller'
    case_reader = 'case-reader'


class MinimumModelIoVersion(RootModel[Literal['model-io-v3']]):
    root: Literal['model-io-v3']
    """
    기능이 켜지는 모델 입출력의 최소 버전(model-io-v3)
    """


class ModelExtractLimitSeconds(RootModel[Literal[20]]):
    root: Annotated[Literal[20], Field(ge=20, le=20)]
    """
    추론 서버가 추출 하나를 마치는 상한(초)
    """


class ModelIoFeature(StrEnum):
    """
    모델 입출력 v3 에 의존해 v3 가 활성이기 전까지 꺼져 있는 기능
    """

    CONFIRMING_STATE = 'CONFIRMING_STATE'
    MEANING_ASKED_EXEMPTION = 'MEANING_ASKED_EXEMPTION'
    STAFF_HELP_AFTER_EXPLAIN = 'STAFF_HELP_AFTER_EXPLAIN'


class ModelIoFeatureRequirement(BaseModel):
    """
    기능 하나와 그것이 켜지는 조건(활성 모델 패키지의 model_io_version 이 최소 버전 이상). 그 전에는 서비스가 기능을 켜지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    feature: ModelIoFeature
    """
    조건이 걸린 기능
    """
    minimum_model_io_version: MinimumModelIoVersion
    """
    기능을 켜는 최소 모델 입출력 버전
    """


class ModelIoFeatureRequirements1(BaseModel):
    """
    v3 의존 기능 셋과 켜지는 조건의 표(ModelIoFeature 값마다 정확히 하나)
    """


class ModelIoFeatureRequirements(
    RootModel[list[ModelIoFeatureRequirement] | ModelIoFeatureRequirements1]
):
    """
    v3 의존 기능 셋과 켜지는 조건의 표(ModelIoFeature 값마다 정확히 하나)
    """

    root: Annotated[
        list[ModelIoFeatureRequirement] | ModelIoFeatureRequirements1,
        Field(max_length=3, min_length=3),
    ]
    """
    v3 의존 기능 셋과 켜지는 조건의 표(ModelIoFeature 값마다 정확히 하나)
    """


class ModelIoVersion(StrEnum):
    """
    모델 패키지의 어댑터가 학습한 입출력 형식의 버전. 서비스의 모델 통신 컴포넌트는 활성 모델 패키지의 이 버전에 맞는 것만 모델과 이야기한다. 다음 버전의 후보는 contracts/model-io-v3-proposal.md 에 있고 활성이 아니다
    """

    model_io_v2 = 'model-io-v2'


class ModelLoadState(StrEnum):
    """
    추론 서버의 모델 적재 상태
    """

    NOT_LOADED = 'NOT_LOADED'
    LOADING = 'LOADING'
    READY = 'READY'
    FAILED = 'FAILED'


class ModelRespondLimitSeconds(RootModel[Literal[25]]):
    root: Annotated[Literal[25], Field(ge=25, le=25)]
    """
    추론 서버가 응답 생성 하나를 마치는 상한(초)
    """


class NoValue(RootModel[None]):
    root: None
    """
    값이 없음을 뜻하는 null(모름·거절·빠짐 등 저장할 값이 없는 칸)
    """


class NumericDate(RootModel[int]):
    root: Annotated[int, Field(examples=[1783684200], ge=0, le=253402300799)]
    """
    JWT 의 시각 클레임(1970-01-01T00:00:00Z 부터의 초)
    """


class OciDigest(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            ],
            max_length=71,
            pattern='^sha256:[a-f0-9]{64}$',
        ),
    ]
    """
    OCI 레지스트리의 내용 주소(digest). 알고리즘 이름 sha256, 콜론, 소문자 16진수 64자다. 모델 패키지(OCI 아티팩트)와 그 안의 파일을 가리킨다
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


class OidcJwksUrl(RootModel[AnyUrl]):
    root: Annotated[
        AnyUrl,
        Field(
            examples=['https://platform/realms/openit/protocol/openid-connect/certs']
        ),
    ]
    """
    발급자의 JWT 서명 공개 키 집합(JWKS) 주소. 없으면 발급자의 디스커버리 문서(.well-known/openid-configuration)의 jwks_uri 를 쓴다
    """


class OptionCode(RootModel[str]):
    root: Annotated[
        str, Field(examples=['days_10_29'], max_length=20, pattern='^[a-z0-9_]+$')
    ]
    """
    선택지 하나의 코드(예를 들어 days_10_29, current, bottle)
    """


class OptionLabel(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['과거에는 피웠으나 현재 피우지 않음'], max_length=38, min_length=1
        ),
    ]
    """
    선택지 하나의 환자용 이름
    """


class OutOfSchemaNote(RootModel[str]):
    root: Annotated[str, Field(examples=['손발이 저림'], max_length=70)]
    """
    문진표에 없는 건강 이야기를 요약한 짧은 말(예를 들어 손발이 저림)
    """


class PageCursor(RootModel[str]):
    root: Annotated[
        str, Field(examples=['eyJrIjoiM2YyYjhjMWUiLCJzIjoiYWJjIn0'], max_length=96)
    ]
    """
    다음 쪽을 가리키는 불투명 값. 서버가 만들고 클라이언트는 해석하지 않는다
    """


class PageLimit(RootModel[int]):
    root: Annotated[int, Field(examples=[30], ge=1, le=100)] = 30
    """
    한 번에 받을 항목의 최대 개수
    """


class PauseReason(StrEnum):
    """
    세션이 멈춘 까닭. 직원 화면과 지표가 구분한다
    """

    RISK_SIGNAL = 'RISK_SIGNAL'
    STAFF_CALL = 'STAFF_CALL'


class PeerBaseUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['https://model-runtime'])]
    """
    이웃 서비스의 기준 주소(항상 TLS)
    """


class PreferredUsername(RootModel[str]):
    root: Annotated[str, Field(examples=['dr.kim'], max_length=255)]
    """
    사람이 읽는 계정 이름(화면 표시용). 권한 판단에는 쓰지 않는다
    """


class ProblemDetail(RootModel[str]):
    root: Annotated[
        str,
        Field(examples=['모델 출력이 합격 조건을 끝내 지키지 못했다'], max_length=4000),
    ]
    """
    이번 오류가 일어난 까닭의 사람용 설명. 환자 발화와 비밀 값은 넣지 않는다
    """


class ProblemFieldError(BaseModel):
    """
    요청의 칸 하나가 계약을 어긴 내용. 위치와 까닭
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    detail: ProblemDetail
    """
    그 칸이 어긋난 까닭
    """
    pointer: JsonPointer
    """
    잘못된 값이 있는 요청 본문 안의 위치
    """


class ProblemFieldErrors(RootModel[list[ProblemFieldError]]):
    """
    한 요청에서 어긋난 칸들의 목록
    """

    root: Annotated[list[ProblemFieldError], Field(max_length=100)]
    """
    한 요청에서 어긋난 칸들의 목록
    """


class ProblemInstance(RootModel[str]):
    root: Annotated[str, Field(examples=['/v1/extractions'], max_length=8000)]
    """
    이번 오류 발생 하나를 가리키는 URI 참조(보통 요청 경로)
    """


class ProblemReason(StrEnum):
    """
    오류의 세부 사유. 상태 코드로 나뉘지 않는 경우를 클라이언트가 가르는 값. 각 값에 그 값을 내는 작업을 적었다
    """

    OUTPUT_INVALID = 'OUTPUT_INVALID'
    TURN_IN_PROGRESS = 'TURN_IN_PROGRESS'
    START_CODE_INVALID = 'START_CODE_INVALID'
    START_CODE_EXPIRED = 'START_CODE_EXPIRED'
    START_CODE_USED = 'START_CODE_USED'
    SESSION_NOT_ACTIVE = 'SESSION_NOT_ACTIVE'
    MODEL_NOT_LOADED = 'MODEL_NOT_LOADED'
    QUESTION_BANK_VERSION_MISMATCH = 'QUESTION_BANK_VERSION_MISMATCH'
    DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'
    CASE_VERSION_MISMATCH = 'CASE_VERSION_MISMATCH'
    PACKAGE_INVALID = 'PACKAGE_INVALID'
    ROLLBACK_TARGET_INVALID = 'ROLLBACK_TARGET_INVALID'
    RISK_DETECTION_DISABLED = 'RISK_DETECTION_DISABLED'


class ProblemTitle(RootModel[str]):
    root: Annotated[
        str, Field(examples=['모델 출력이 합격 조건을 지키지 못했다'], max_length=200)
    ]
    """
    오류 종류의 짧은 사람용 이름. 같은 종류면 항상 같다
    """


class ProblemType(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['https://openit/problems/OUTPUT_INVALID'])]
    """
    오류의 종류를 가리키는 절대 URI(scheme 이 있는 URI). 기본은 about:blank 다. 이 계약의 서버는 사유가 있으면 https://openit/problems/<ProblemReason 값> 을 쓴다
    """


class ProcessedCount(RootModel[int]):
    root: Annotated[int, Field(examples=[3], ge=0, le=2147483647)]
    """
    잡이 처리한 항목의 수
    """


class PrometheusExposition(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                '# TYPE turn_duration_seconds histogram\nturn_duration_seconds_count 1\n'
            ],
            max_length=8388608,
        ),
    ]
    """
    Prometheus 텍스트 노출 형식의 지표 본문. 8 MiB 는 바이트 상한이라 HTTP 본문 계층(Content-Length)에서 강제하고 maxLength 는 글자 수의 상한이며 둘은 따로다. 서비스는 RequiredPrometheusMetric 에 적힌 지표(turn_duration_seconds, model_call_duration_seconds)를 해당 서비스에서 반드시 낸다
    """


class PushAuthSecret(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['tBHItJI5svbpez7KI4CCXg'],
            max_length=22,
            pattern='^[A-Za-z0-9_-]{22}$',
        ),
    ]
    """
    푸시 구독의 인증 비밀(16옥텟을 base64url 로 쓴 22자)
    """


class PushEndpoint(RootModel[AnyUrl]):
    root: Annotated[
        AnyUrl,
        Field(
            examples=[
                'https://updates.push.services.mozilla.com/wpush/v2/gAAAAABexample'
            ]
        ),
    ]
    """
    브라우저 푸시 서비스가 정한 구독 주소. 이 주소로 푸시 메시지를 보낸다
    """


class PushPublicKey(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM'
            ],
            max_length=87,
            pattern='^[A-Za-z0-9_-]{87}$',
        ),
    ]
    """
    P-256 비압축 공개키를 base64url(패딩 없음)로 쓴 값(65옥텟이 87자)
    """


class PushSubscriptionId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    저장한 푸시 구독 하나의 식별자
    """


class QuestionItemId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['Q1.D01'], max_length=12, pattern='^[A-Za-z0-9_.]+$')
    ]
    """
    문항 하나의 식별자(예를 들어 Q8_1, Q1.D01)
    """


class QuestionOption(BaseModel):
    """
    선택지 하나(코드와 환자용 이름)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    label: OptionLabel
    """
    환자에게 보이는 이름
    """
    option_code: OptionCode
    """
    저장되는 선택지 코드
    """


class QuestionOptions(RootModel[list[QuestionOption]]):
    """
    한 칸의 선택지들
    """

    root: Annotated[list[QuestionOption], Field(max_length=23)]
    """
    한 칸의 선택지들
    """


class QuestionSetVersionId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    문진표 한 벌의 확정된 버전 하나의 식별자
    """


class QuestionText(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['혹시 뇌졸중으로 진단받으셨거나 현재 약물 치료 중이신가요?'],
            max_length=124,
            min_length=1,
        ),
    ]
    """
    문항 하나의 환자용 질문 문장
    """


class QuestionnaireId(RootModel[str]):
    root: Annotated[
        str,
        Field(examples=['national-health'], max_length=63, pattern='^[A-Za-z0-9_-]+$'),
    ]
    """
    문진표(환자가 답하는 하나의 질문 묶음)의 식별자. 버전이 바뀌어도 같다
    """


class QuestionnaireTitle(RootModel[str]):
    root: Annotated[
        str, Field(examples=['국가건강검진 문진표'], max_length=200, min_length=1)
    ]
    """
    문진표의 제목. 결과와 선택 화면에 보인다
    """


class RawUtteranceRetentionDays(RootModel[int]):
    root: Annotated[int, Field(examples=[180], ge=180, le=180)]
    """
    검토용 환자 발화 원문을 보존하는 일수
    """


class ReaskLimit(RootModel[int]):
    root: Annotated[int, Field(examples=[2], ge=2, le=2)]
    """
    한 문항에서 REASK 와 CONFIRM 이 이어질 수 있는 되묻기 횟수의 한도(처음 질문 1회에 되묻기 2회). 그 뒤에도 정해지지 않으면 서비스가 문항을 건너뛰고(SKIP) 결과에 빈칸 원인 REASK_LIMIT 를 남긴다. 환자에게는 서비스의 고정 안내 문장을 보이고 LoRA-B 에 거짓 사유를 보내지 않는다
    """


class RepeatKey(RootModel[str]):
    root: Annotated[
        str, Field(examples=['makgeolli'], max_length=18, pattern='^[a-z]*$')
    ]
    """
    같은 칸이 여러 번 쓰일 때 구분하는 반복 키(술 종류: soju, beer, spirits, makgeolli, wine). 빈 문자열은 술 종류를 모르는 값의 키이고 저장하지 않는 값(save 거짓)에만 쓴다. 저장하는 값(save 참)에는 반복 키가 있어야 한다
    """


class RepeatKeys(RootModel[list[RepeatKey]]):
    """
    한 칸이 가질 수 있는 반복 키들
    """

    root: Annotated[list[RepeatKey], Field(max_length=10)]
    """
    한 칸이 가질 수 있는 반복 키들
    """


class RespondClientLimitSeconds(RootModel[Literal[26]]):
    root: Annotated[Literal[26], Field(ge=26, le=26)]
    """
    survey-service 가 응답 생성 요청을 기다리는 상한(초)
    """


class ResponseAction(StrEnum):
    """
    LoRA-B 가 문장을 만들 때의 절차
    """

    START = 'START'
    NEXT = 'NEXT'
    CORRECT = 'CORRECT'
    REASK = 'REASK'
    CONFIRM = 'CONFIRM'
    HOLD = 'HOLD'
    SKIP = 'SKIP'
    REDIRECT = 'REDIRECT'


class ResponseNextType(StrEnum):
    """
    응답 뒤에 가는 자리의 종류
    """

    NEXT = 'NEXT'
    SAME = 'SAME'
    END = 'END'


class ResponseSentence(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['뇌졸중 진단을 받으셨고 약도 드시는군요. 다음 질문입니다.'],
            max_length=344,
            min_length=1,
        ),
    ]
    """
    환자에게 보여 주고 읽어 줄 응답 문장. 음성으로 읽을 때도 기기 안에서만 처리하고 외부로 보내지 않는다
    """


class RetryAfterSeconds(RootModel[int]):
    root: Annotated[int, Field(examples=[5], ge=0, le=120)]
    """
    클라이언트가 같은 요청을 다시 보내기 전에 기다릴 초
    """


class ReviewStatus(StrEnum):
    """
    실패 사례의 검토 상태
    """

    UNREVIEWED = 'UNREVIEWED'
    CONFIRMED = 'CONFIRMED'
    DISMISSED = 'DISMISSED'


class ReviewedInput(RootModel[str]):
    root: Annotated[
        str, Field(examples=['중풍 진단 받았고 약도 먹어요'], max_length=300)
    ]
    """
    검토자가 개인정보를 빼고 고쳐 쓴 환자 발화
    """


class RiskCategory(StrEnum):
    """
    위험 신호의 분류(임상 검토 전의 보수적 임시 목록)
    """

    SELF_HARM = 'SELF_HARM'
    CHEST_PAIN = 'CHEST_PAIN'
    DYSPNEA = 'DYSPNEA'
    ALTERED_CONSCIOUSNESS = 'ALTERED_CONSCIOUSNESS'
    SEVERE_BLEEDING = 'SEVERE_BLEEDING'
    PARALYSIS = 'PARALYSIS'


class RiskDetectionEnabled(RootModel[bool]):
    root: bool = False
    """
    위험 감지를 켤지(참이면 켠다). 기본은 꺼짐이다
    """


class RiskSourceName(RootModel[str]):
    root: Annotated[str, Field(examples=['risk-engine'], max_length=63)]
    """
    위험 신호를 낸 감지기의 이름
    """


class RuntimeContractVersion(RootModel[int]):
    root: Annotated[int, Field(examples=[1], ge=1, le=2147483647)]
    """
    문항 은행과 칸 키의 정수 버전. 모델 패키지가 학습한 값과 다르면 적재와 승인을 거부한다
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


class ServerSentEventStream(RootModel[bytes]):
    root: Annotated[
        bytes, Field(json_schema_extra={'contentMediaType': 'text/event-stream'})
    ]
    """
    알림 스트림의 응답 본문 전체(Server-Sent Events 형식의 글자 스트림). 끝이 없는 스트림이라 길이 상한이 없다. 이벤트 하나의 data 는 StaffAlertEvent 다
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


class SessionId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    문진 세션 하나의 식별자. 서버가 발급한다
    """


class SessionStatePollSeconds(RootModel[Literal[2]]):
    root: Annotated[Literal[2], Field(ge=2, le=2)]
    """
    키오스크가 세션 상태를 읽는 간격(초)
    """


class SessionStatus(StrEnum):
    """
    세션의 상태
    """

    ACTIVE = 'ACTIVE'
    PAUSED = 'PAUSED'
    ENDED_COMPLETE = 'ENDED_COMPLETE'
    ENDED_PARTIAL = 'ENDED_PARTIAL'
    EXPIRED = 'EXPIRED'


class Sha256Digest(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            ],
            max_length=64,
            pattern='^[0-9a-f]{64}$',
        ),
    ]
    """
    내용의 SHA-256 해시(소문자 16진수 64자)
    """


class SlotDataType(StrEnum):
    """
    칸이 받는 값의 자료형
    """

    boolean = 'boolean'
    integer = 'integer'
    number = 'number'
    option = 'option'
    text = 'text'


class SlotKey(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['duration_minutes'], max_length=32, pattern='^[a-z][a-z0-9_]*$'
        ),
    ]
    """
    문항 안의 칸 하나의 이름(예를 들어 days, use_pattern, duration_minutes). 데이터셋의 field_name 이다
    """


class SlotNumber(RootModel[float]):
    root: Annotated[
        float, Field(examples=[3], ge=-9007199254740991.0, le=9007199254740991.0)
    ]
    """
    칸에 담기는 수 값 또는 그 최소·최대 한계(정수도 포함). 칸마다의 허용 범위는 칸 규격(QuestionFieldSpec)이 정한다
    """


class SlotRefString(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['Q7_1[soju].amount'],
            max_length=44,
            pattern='^[A-Za-z0-9_.]+(\\[[a-z]+\\])?\\.[a-z][a-z0-9_]*$',
        ),
    ]
    """
    문항과 칸을 한 문자열로 가리키는 값. 문항ID.칸키(예 Q1.D01.diagnosed)이고 술처럼 반복 키가 있으면 문항ID[반복키].칸키(예 Q7_1[soju].amount)다
    """


class SlotRefStrings(RootModel[list[SlotRefString]]):
    """
    칸들의 목록
    """

    root: Annotated[list[SlotRefString], Field(max_length=8)]
    """
    칸들의 목록
    """


class SlotText(RootModel[str]):
    root: Annotated[str, Field(examples=['어지러움이 있음'], max_length=300)]
    """
    자유 글 칸의 값
    """


class SlotUnit(RootModel[str]):
    root: Annotated[str, Field(examples=['day/week'], max_length=16)]
    """
    수 칸의 단위 이름(년, 개비, day/week, minute 등)
    """


class StaffHelpNotice(RootModel[bool]):
    root: bool
    """
    이 응답이 서비스의 고정 문장으로 직원 도움을 안내하는지(참이면 안내). 안전과 닿는 안내 문장은 모델이 아니라 서비스가 쓴다. 모델 입출력 v3 부터 쓰인다
    """


class StartCodeTtlSeconds(RootModel[int]):
    root: Annotated[int, Field(examples=[300], ge=1, le=600)] = 300
    """
    시작 코드의 유효 시간(초)
    """


class StartCodeValue(RootModel[str]):
    root: Annotated[str, Field(examples=['482910'], max_length=6, pattern='^[0-9]{6}$')]
    """
    직원이 발급한 일회용 시작 코드(6자리 숫자, 환자가 키오스크 키패드로 입력한다)
    """


class StoredSlotStatus(StrEnum):
    """
    서비스가 저장하고 있는 칸 하나의 상태
    """

    ANSWERED = 'ANSWERED'
    MISSING = 'MISSING'
    UNCLEAR = 'UNCLEAR'


class SubjectRef(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['subj-000123'],
            max_length=64,
            min_length=1,
            pattern='^[A-Za-z0-9.-]{1,64}$',
        ),
    ]
    """
    문진 대상자를 가리키는 불투명 참조값. 환자 식별 정보(이름·생년월일 등)가 아니다. 설치처의 의료 정보 시스템이 같은 값으로 결과를 당겨 간다
    """


class SurveyTurnLimitSeconds(RootModel[Literal[50]]):
    root: Annotated[Literal[50], Field(ge=50, le=50)]
    """
    survey-service 가 환자 턴 하나를 마치는 총 마감(초)
    """


class TimeBudgetTable(BaseModel):
    """
    영역 사이 시간 상한의 표. 바깥이 안쪽보다 길다(키오스크 > 게이트웨이 > survey 턴 > 클라이언트 > 추론 서버, 사람 화면 > 게이트웨이 > 서버). 값은 목표(SLO 2초)가 아니라 실패 판정 상한이다. 실제 설정 입력은 이 값 이하로 둔다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    alert_stream_heartbeat: AlertStreamHeartbeatSeconds
    """
    알림 스트림이 아무 이벤트가 없을 때 heartbeat 를 보내는 간격(초)
    """
    extract_client: ExtractClientLimitSeconds
    """
    survey-service 가 추출 요청을 기다리는 상한(초)
    """
    gateway_connect: GatewayConnectLimitSeconds
    """
    영역 게이트웨이가 상류에 연결하는 데 쓰는 상한(초)
    """
    gateway_patient_route: GatewayPatientRouteLimitSeconds
    """
    환자·직원 경로에서 게이트웨이가 상류의 응답 머리글을 기다리는 상한(초)
    """
    kiosk_idle_reset: KioskIdleResetSeconds
    """
    키오스크가 입력 없이 기다리다 세션을 초기화하는 시간(초)
    """
    kiosk_progress_notice: KioskProgressNoticeSeconds
    """
    키오스크가 응답이 늦을 때 진행 표시를 보이기 시작하는 시간(초)
    """
    kiosk_request: KioskRequestLimitSeconds
    """
    키오스크가 서버 응답을 기다리는 실패 판정 상한(초)
    """
    kiosk_retry_budget: KioskRetryBudgetSeconds
    """
    키오스크가 같은 요청을 다시 보내는 데 쓸 수 있는 총 시간(초)
    """
    model_extract: ModelExtractLimitSeconds
    """
    추론 서버가 추출 하나를 마치는 상한(초)
    """
    model_respond: ModelRespondLimitSeconds
    """
    추론 서버가 응답 생성 하나를 마치는 상한(초)
    """
    respond_client: RespondClientLimitSeconds
    """
    survey-service 가 응답 생성 요청을 기다리는 상한(초)
    """
    session_state_poll: SessionStatePollSeconds
    """
    키오스크가 세션 상태를 읽는 간격(초)
    """
    survey_turn: SurveyTurnLimitSeconds
    """
    survey-service 가 환자 턴 하나를 마치는 총 마감(초)
    """


class Timestamp(RootModel[AwareDatetime]):
    root: Annotated[AwareDatetime, Field(examples=['2026-11-10T09:30:00+09:00'])]
    """
    일이 일어난 때. UTC 오프셋을 포함한 RFC 3339 날짜-시각
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


class TurnFailureReason(StrEnum):
    """
    턴이 값을 만들지 못한 까닭. 세션 상태는 바뀌지 않으므로 같은 발화를 다시 보낼 수 있다
    """

    EXTRACTION_UNAVAILABLE = 'EXTRACTION_UNAVAILABLE'
    RESPONSE_UNAVAILABLE = 'RESPONSE_UNAVAILABLE'
    DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'


class TurnId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    환자 발화 한 턴의 식별자. 클라이언트가 만들고 같은 값을 다시 보내면 같은 결과를 받는다(멱등)
    """


class TurnResponse(BaseModel):
    """
    한 턴의 처리 결과. 다음에 보일 문장과 세션 상태를 담는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    current_item_id: QuestionItemId | None = None
    """
    다음에 묻는 문항(끝났으면 없다)
    """
    failure_signal: TurnFailureReason | None = None
    """
    턴이 값을 만들지 못했을 때의 신호
    """
    pause_reason: PauseReason | None = None
    """
    멈췄다면 그 까닭
    """
    response_text: ResponseSentence | None = None
    """
    화면에 보일 문장(실패 신호일 때는 없다)
    """
    staff_help_notice: StaffHelpNotice | None = None
    """
    직원 도움 안내 문장이 들어 있는지
    """
    status: SessionStatus
    """
    턴 처리 뒤 세션 상태
    """
    turn_id: TurnId
    """
    응답이 가리키는 턴
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


class UtteranceText(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['뇌졸중 진단 받았고 약도 먹고 있어요'],
            max_length=300,
            min_length=1,
        ),
    ]
    """
    환자가 한 턴에 한 말(음성은 기기 안에서 글자로 바꾼 값)
    """


class ValuePrecision(StrEnum):
    """
    추출한 값이 정확한지 대략인지
    """

    exact = 'exact'
    approximate = 'approximate'
    unspecified = 'unspecified'


class ValueSave(RootModel[bool]):
    root: bool
    """
    이 값을 문진 DB 에 저장하는지(참이면 저장). ANSWERED 와 CORRECTION 만 참이다
    """


class ValueStatus(StrEnum):
    """
    추출한 값 하나의 상태
    """

    ANSWERED = 'ANSWERED'
    CORRECTION = 'CORRECTION'
    MISSING = 'MISSING'
    UNCLEAR = 'UNCLEAR'
    CONFLICT = 'CONFLICT'
    UNKNOWN = 'UNKNOWN'
    REJECTED = 'REJECTED'


class VapidSubject(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['mailto:ops@example.org'])]
    """
    웹 푸시 서버가 푸시 서비스에 밝히는 연락처(mailto 또는 https 주소)
    """


class WebPushPayload(BaseModel):
    """
    푸시 메시지 안에 암호화해 담는 알림 내용. 환자 정보는 담지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    alert_id: AlertId
    """
    알림 식별자(눌렀을 때 화면이 이 알림을 연다)
    """
    kind: AlertKind
    """
    알림 종류
    """
    raised_at: Timestamp
    """
    알림이 생긴 때
    """


class YesNoAnswer(RootModel[bool]):
    root: bool
    """
    예 또는 아니오 칸의 값(예이면 참)
    """


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


class ActiveQuestionSet(BaseModel):
    """
    문진표 하나의 지금 활성인 문항 세트 버전과 활성화 기록
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    activated_at: Timestamp
    """
    활성화한 때
    """
    activated_by: UserId
    """
    활성화한 사람(OIDC 접근 토큰의 sub)
    """
    question_set_version_id: QuestionSetVersionId
    """
    활성인 버전
    """
    questionnaire_id: QuestionnaireId
    """
    문진표 식별자
    """
    runtime_contract_version: RuntimeContractVersion
    """
    그 버전의 문항 은행과 칸 키의 정수 버전
    """


class ConditionValue(RootModel[YesNoAnswer | SlotNumber | OptionCode]):
    root: YesNoAnswer | SlotNumber | OptionCode
    """
    건너뛰기 조건이 비교하는 값(예 또는 아니오, 수, 선택지 코드 중 하나)
    """


class DevicePlacement(BaseModel):
    """
    키오스크 기기 하나에 기본으로 배치하는 문진표
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    device_id: DeviceId
    """
    기본 문진표를 배치할 키오스크 기기
    """
    questionnaire_id: QuestionnaireId
    """
    그 기기의 기본 문진표
    """


class DevicePlacementTable(BaseModel):
    """
    deploy 가 survey-service 에 파일로 주는 기기별 기본 문진표 배치표. 서버는 mTLS 로 확인된 기기 ID 로 기본 문진표를 고른다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    placements: Annotated[list[DevicePlacement], Field(max_length=1000)]
    """
    기기별 기본 문진표 배치들
    """


class FhirAbsentMapEntry(BaseModel):
    """
    결과의 빈칸 원인 하나가 FHIR 빈칸 사유의 무엇이 되는지
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    absent_reason: FhirAbsentReason
    """
    FHIR 빈칸 사유
    """
    blank_reason: BlankReason
    """
    결과의 빈칸 원인
    """


class FhirIssue(BaseModel):
    """
    OperationOutcome 안의 문제 하나. FHIR R4 가 필수로 정한 칸(severity, code)만 검증하고 그 밖의 칸은 허용한다
    """

    code: FhirIssueCode
    """
    문제의 종류
    """
    severity: FhirIssueSeverity
    """
    문제의 심각도
    """


class FhirOperationOutcome(BaseModel):
    """
    FHIR R4 OperationOutcome 리소스. FHIR 조회가 실패했을 때의 본문이며 필수 칸(resourceType, issue)만 검증하고 나머지는 FHIR 사양이 정본이다. 열린 객체라 allOf 로 객체 유형만 요구한다
    """

    issue: Annotated[list[FhirIssue], Field(max_length=100, min_length=1)]
    """
    문제들(FHIR R4 가 하나 이상을 요구한다)
    """
    resourceType: FhirOutcomeResourceType
    """
    리소스 유형(항상 OperationOutcome)
    """


class FhirQuestionnaireResponse(BaseModel):
    """
    문진 결과를 FHIR R4 QuestionnaireResponse 로 낸 것. 칸의 정의는 HL7 FHIR R4 사양(https://hl7.org/fhir/R4/questionnaireresponse.html)이 정본이라 이 계약은 다시 정의하지 않고 필수 칸(resourceType, status)만 검증한다. 나머지 칸의 검증은 FHIR 검증기가 FHIR JSON Schema 로 한다. 열린 객체라 allOf 로 객체 유형만 요구한다. 대응 규칙은 FhirMapping 이다
    """

    resourceType: FhirResourceType
    """
    리소스 유형(항상 QuestionnaireResponse)
    """
    status: FhirResponseStatus
    """
    응답의 상태. FHIR R4 가 필수로 정한 칸이다
    """


class FhirStatusMapEntry(BaseModel):
    """
    세션 상태 하나가 FHIR status 의 무엇이 되는지
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    fhir_status: FhirResponseStatus
    """
    FHIR status
    """
    session_status: SessionStatus
    """
    세션 상태
    """


class FlowCondition(BaseModel):
    """
    분기가 선택되는 조건(칸 값과 비교)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    operator: FlowComparison
    """
    비교 연산
    """
    slot: SlotRefString
    """
    비교할 칸
    """
    value: ConditionValue
    """
    비교 대상 값
    """


class HealthCheck(BaseModel):
    """
    건강 점검 항목 하나의 결과
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    name: HealthCheckName
    """
    점검한 의존 또는 기능의 이름
    """
    observed_at: Timestamp | None = None
    """
    이 항목을 마지막으로 점검한 때
    """
    status: HealthStatus
    """
    이 항목의 점검 결과
    """


class HealthChecks(RootModel[list[HealthCheck]]):
    """
    건강 점검 항목들
    """

    root: Annotated[list[HealthCheck], Field(max_length=100)]
    """
    건강 점검 항목들
    """


class HealthReport(BaseModel):
    """
    서비스의 건강 점검 응답 본문(application/json). /healthz 와 /readyz 가 낸다. 모양은 만료된 초안을 참고한 자체 모양이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    checks: HealthChecks | None = None
    """
    의존별 점검 결과(/readyz 에서만)
    """
    revision: ImageRevision | None = None
    """
    실행 중인 이미지의 소스 커밋
    """
    service: ServiceName
    """
    응답한 서비스
    """
    status: HealthStatus
    """
    전체 결과. /healthz 는 프로세스 생존만, /readyz 는 의존 준비까지 본다
    """


class JobDeclaration(BaseModel):
    """
    영역이 선언하는 잡 하나(이름과 시간 상한)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    job: JobName
    """
    잡 이름
    """
    timeout_seconds: JobTimeoutSeconds
    """
    이 잡의 시간 상한
    """


class JobRunInput(BaseModel):
    """
    잡 한 번을 실행할 때 인자로 주는 입력. 같은 입력은 같은 결과를 낸다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    job: JobName
    """
    실행할 잡
    """
    requested_at: Timestamp
    """
    스케줄러가 실행을 요청한 때(잡이 시각을 스스로 읽지 않고 이 값을 쓴다)
    """
    snapshot_id: BackupSnapshotId | None = None
    """
    RESTORE 일 때 복구할 스냅샷
    """


class JobRunResult(BaseModel):
    """
    잡 한 번의 실행 결과(표준 출력에 JSON 한 줄로 낸다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    exit_code: JobExitCode
    """
    종료 코드
    """
    finished_at: Timestamp
    """
    끝난 때
    """
    job: JobName
    """
    실행한 잡
    """
    processed_count: ProcessedCount | None = None
    """
    처리한 항목 수
    """
    snapshot_id: BackupSnapshotId | None = None
    """
    BACKUP 이 만든 스냅샷
    """
    started_at: Timestamp
    """
    시작한 때
    """


class JobsDeclaration(BaseModel):
    """
    이미지가 가진 잡들의 선언. 영역은 실행 일정을 모른다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    jobs: Annotated[list[JobDeclaration], Field(max_length=11)]
    """
    잡들
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


class ModelStatus(BaseModel):
    """
    추론 서버가 지금 적재한 모델 패키지와 적재 상태, 활성화 기록
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    activated_at: Timestamp | None = None
    """
    활성화한 때
    """
    activated_by: UserId | None = None
    """
    활성화한 승인자(OIDC 접근 토큰의 sub)
    """
    loaded_at: Timestamp | None = None
    """
    적재를 마친 때
    """
    model_io_version: ModelIoVersion | None = None
    """
    적재한 모델 패키지의 모델 입출력 형식 버전(적재 전이면 없다)
    """
    package_digest: OciDigest | None = None
    """
    활성인 모델 패키지(활성화된 적이 없으면 없다)
    """
    previous_package_digest: OciDigest | None = None
    """
    바로 앞에 활성이었던 모델 패키지(롤백 대상 후보)
    """
    runtime_contract_version: RuntimeContractVersion | None = None
    """
    적재한 모델 패키지가 학습한 문항 은행 버전(적재 전이면 없다)
    """
    state: ModelLoadState
    """
    적재 상태
    """


class ProblemDetails(BaseModel):
    """
    모든 오류 응답의 본문(application/problem+json). 4xx 와 5xx 모두 이 모양이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    detail: ProblemDetail | None = None
    """
    이번 오류의 설명
    """
    errors: ProblemFieldErrors | None = None
    """
    요청 본문에서 어긋난 칸들(검증 실패일 때만)
    """
    instance: ProblemInstance | None = None
    """
    이번 오류 발생을 가리키는 URI 참조
    """
    reason: ProblemReason | None = None
    """
    상태 코드만으로 가를 수 없는 세부 사유
    """
    status: HttpStatus
    """
    응답의 HTTP 상태 코드
    """
    title: ProblemTitle
    """
    오류 종류의 짧은 이름
    """
    type: ProblemType
    """
    오류 종류를 가리키는 URI 참조
    """


class PushConfig(BaseModel):
    """
    브라우저가 푸시를 구독할 때 쓰는 서버의 VAPID 공개키
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    vapid_public_key: PushPublicKey
    """
    서버가 보유한 VAPID 공개키
    """


class PushKeys(BaseModel):
    """
    푸시 메시지를 암호화하는 데 쓰는 구독 키 한 쌍
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    auth: PushAuthSecret
    """
    구독 인증 비밀
    """
    p256dh: PushPublicKey
    """
    브라우저의 P-256 공개키
    """


class PushSubscription(BaseModel):
    """
    브라우저가 만든 웹 푸시 구독. 구독한 사람의 계정에 묶어 저장한다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    endpoint: PushEndpoint
    """
    구독 주소
    """
    keys: PushKeys
    """
    구독 키
    """


class PushSubscriptionRegistered(BaseModel):
    """
    푸시 구독을 저장한 결과
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    push_subscription_id: PushSubscriptionId
    """
    저장한 구독의 식별자
    """
    registered_at: Timestamp
    """
    저장한 때
    """


class QuestionFieldSpec(BaseModel):
    """
    칸 하나의 규격(자료형, 단위, 허용 범위, 반복 키, 선택지). 추론 서버가 출력 값을 이 규격으로 보증한다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    data_type: SlotDataType
    """
    칸이 받는 값의 자료형
    """
    exclusive_minimum: SlotNumber | None = None
    """
    수 칸이 이 값보다 커야 한다(이 값은 제외)
    """
    field_name: SlotKey
    """
    칸의 이름
    """
    item_id: QuestionItemId
    """
    칸이 속한 문항
    """
    maximum: SlotNumber | None = None
    """
    수 칸이 받는 최댓값(포함)
    """
    minimum: SlotNumber | None = None
    """
    수 칸이 받는 최솟값(포함)
    """
    options: QuestionOptions | None = None
    """
    선택지 칸의 선택지들
    """
    repeat_keys: RepeatKeys | None = None
    """
    반복 키가 있는 칸이면 그 키들(없으면 빈 키 하나만 쓴다). 빈 반복 키는 술 종류를 모르는 값을 가리키며 저장하지 않는 값(save 거짓)에만 쓰인다. 저장하는 값(save 참)에는 반복 키가 있어야 한다(SQL.md 6.1, labels.py _key)
    """
    unit: SlotUnit | None = None
    """
    수 칸의 단위
    """


class QuestionFieldSpecs(RootModel[list[QuestionFieldSpec]]):
    """
    칸 규격들
    """

    root: Annotated[list[QuestionFieldSpec], Field(max_length=104)]
    """
    칸 규격들
    """


class QuestionItem(BaseModel):
    """
    문항 하나(식별자, 질문 문장, 받을 칸들)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    fields: QuestionFieldSpecs
    """
    이 문항이 받는 칸들의 규격
    """
    item_id: QuestionItemId
    """
    문항 식별자
    """
    text: QuestionText
    """
    질문 문장
    """


class QuestionItems(RootModel[list[QuestionItem]]):
    """
    문항들
    """

    root: Annotated[list[QuestionItem], Field(max_length=62)]
    """
    문항들
    """


class QuestionnaireSummary(BaseModel):
    """
    활성 문진표 하나의 요약(선택 화면에 보일 만큼)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    questionnaire_id: QuestionnaireId
    """
    문진표 식별자
    """
    title: QuestionnaireTitle
    """
    문진표 제목
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


class ResponseNext(BaseModel):
    """
    응답 뒤에 가는 자리(종류, 문항, 그 문항의 질문 문장). 질문 문장은 survey-service 가 가진 문항 세트의 문장이다(데이터셋 표가 아니다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    question_id: QuestionItemId | None = None
    """
    가는 문항(END 에는 없다)
    """
    text: QuestionText | None = None
    """
    가는 문항의 질문 문장(문항 세트의 문장, END 에는 없다)
    """
    type: ResponseNextType
    """
    자리의 종류
    """


class ResponseResult(BaseModel):
    """
    LoRA-B 가 만든 응답 문장과 처리한 모델 패키지
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    package_digest: OciDigest
    """
    이 문장을 만든 모델 패키지(OCI 매니페스트 digest)
    """
    text: ResponseSentence
    """
    환자에게 보일 문장
    """


class ResultAcknowledgement(BaseModel):
    """
    의사가 결과를 확인했다는 기록
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    acknowledged_at: Timestamp
    """
    확인한 때
    """
    acknowledged_by: UserId
    """
    확인한 의사(요청의 인증된 사용자)
    """
    session_id: SessionId
    """
    확인한 결과의 세션
    """


class ResultBlank(BaseModel):
    """
    결과에서 비어 있는 칸 하나와 그 원인. 환자 발화 원문은 담지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    item_id: QuestionItemId
    """
    비어 있는 문항
    """
    key: SlotRefString | None = None
    """
    비어 있는 칸(반복 키가 있는 칸은 Q7_1[soju].amount 처럼 반복 키까지 가린다). 문항 전체가 비어 있으면 없다
    """
    reason: BlankReason
    """
    비어 있는 원인
    """


class ResultSummary(BaseModel):
    """
    결과 목록의 한 줄
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    acknowledged_at: Timestamp | None = None
    """
    의사가 확인한 때(아직이면 없다)
    """
    ended_at: Timestamp | None = None
    """
    끝난 때
    """
    questionnaire_id: QuestionnaireId
    """
    문진표
    """
    questionnaire_title: QuestionnaireTitle | None = None
    """
    문진표 제목
    """
    session_id: SessionId
    """
    세션
    """
    started_at: Timestamp
    """
    시작한 때
    """
    status: SessionStatus
    """
    세션 상태
    """
    subject_ref: SubjectRef
    """
    문진 대상자 참조값
    """


class RiskSignal(BaseModel):
    """
    외부 위험 감지기가 보내는 위험 신호 하나
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    category: RiskCategory
    """
    위험의 분류
    """
    detected_at: Timestamp
    """
    감지한 때
    """
    session_id: SessionId
    """
    신호가 가리키는 세션
    """
    source: RiskSourceName | None = None
    """
    감지기의 이름
    """


class SessionEnded(BaseModel):
    """
    세션 종료 결과
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    ended_at: Timestamp
    """
    끝난 때
    """
    session_id: SessionId
    """
    끝난 세션
    """
    status: SessionStatus
    """
    끝난 뒤 상태(ENDED_PARTIAL 또는 ENDED_COMPLETE)
    """


class SessionStartRequest(BaseModel):
    """
    키오스크가 세션을 시작하는 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    questionnaire_id: QuestionnaireId | None = None
    """
    환자가 고른 문진표. 코드에 문진표가 묶여 있지 않고 기기 배치도 없을 때만 쓴다
    """
    start_code: StartCodeValue
    """
    환자가 입력한 일회용 시작 코드
    """


class SessionStarted(BaseModel):
    """
    세션 시작 결과. 첫 인사 문장과 첫 문항을 담는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    current_item_id: QuestionItemId | None = None
    """
    지금 묻는 문항
    """
    questionnaire_id: QuestionnaireId
    """
    이 세션이 쓰는 문진표
    """
    questionnaire_title: QuestionnaireTitle | None = None
    """
    이 세션이 쓰는 문진표의 제목
    """
    response_text: ResponseSentence
    """
    화면에 보일 첫 문장
    """
    session_id: SessionId
    """
    새 세션의 식별자
    """
    status: SessionStatus
    """
    세션 상태(시작 직후는 ACTIVE)
    """


class SessionState(BaseModel):
    """
    키오스크가 2초마다 확인하는 세션 상태. 직원이 정지를 풀었는지 알리는 용도다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    pause_reason: PauseReason | None = None
    """
    멈춘 세션이면 그 까닭
    """
    resume_text: ResponseSentence | None = None
    """
    정지가 풀린 뒤 다음 발화 턴을 받기 전까지 환자에게 보일 문장
    """
    session_id: SessionId
    """
    확인한 세션
    """
    status: SessionStatus
    """
    지금 상태
    """


class SlotAnswer(RootModel[YesNoAnswer | SlotNumber | OptionCode | SlotText | NoValue]):
    root: YesNoAnswer | SlotNumber | OptionCode | SlotText | NoValue
    """
    칸 하나에 담긴 값(예 또는 아니오, 수, 선택지 코드, 자유 글, 값 없음 중 하나)
    """


class StaffAlert(BaseModel):
    """
    직원 또는 의사에게 가는 알림 하나
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    alert_id: AlertId
    """
    알림 식별자
    """
    device_id: DeviceId | None = None
    """
    직원이 찾아가야 할 키오스크 기기(결과 알림에는 없다)
    """
    kind: AlertKind
    """
    알림 종류
    """
    questionnaire_title: QuestionnaireTitle | None = None
    """
    세션의 문진표 제목
    """
    raised_at: Timestamp
    """
    알림이 생긴 때
    """
    resolved_at: Timestamp | None = None
    """
    직원이 풀거나 확인한 때(아직이면 없다)
    """
    session_id: SessionId
    """
    알림이 가리키는 세션
    """


class StaffAlertEvent(BaseModel):
    """
    알림 스트림이 보내는 이벤트 하나의 data 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    alert: StaffAlert | None = None
    """
    alert 와 resolved 이벤트가 가리키는 알림
    """
    event: AlertEventName
    """
    이벤트 이름
    """
    sequence: EventSequence
    """
    이벤트 순번
    """


class StaffAlertPage(BaseModel):
    """
    직원 알림 목록 한 쪽
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: Annotated[list[StaffAlert], Field(max_length=100)]
    """
    알림들(최근 것이 먼저)
    """
    next_cursor: PageCursor | None = None
    """
    다음 쪽을 받을 커서(마지막 쪽이면 없다)
    """


class StartCode(BaseModel):
    """
    발급된 일회용 시작 코드와 유효 기한
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    code: StartCodeValue
    """
    환자가 키오스크에 입력할 코드
    """
    expires_at: Timestamp
    """
    이 때가 지나면 코드를 쓸 수 없다
    """
    issued_at: Timestamp
    """
    코드를 발급한 때
    """
    questionnaire_id: QuestionnaireId | None = None
    """
    코드에 묶인 문진표(요청에서 정했을 때만)
    """


class StartCodeIssueRequest(BaseModel):
    """
    직원이 시작 코드 발급을 요청하는 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    questionnaire_id: QuestionnaireId | None = None
    """
    미리 정할 문진표. 없으면 기기 배치나 환자 선택을 따른다
    """
    subject_ref: SubjectRef
    """
    이 코드로 시작할 문진 대상자의 참조값
    """


class StoredSlot(BaseModel):
    """
    서비스가 저장하고 있는 칸 하나(어느 칸인지, 저장된 값, 상태)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    key: SlotRefString
    """
    저장된 칸
    """
    status: StoredSlotStatus
    """
    칸의 상태
    """
    value: SlotAnswer
    """
    저장된 값(다시 물은 칸이면 null)
    """


class StoredSlots(RootModel[list[StoredSlot]]):
    """
    이번 턴을 반영하기 전에 세션에 저장된 모든 칸 값과 다시 묻는 중인 칸의 목록. 배열의 순서가 모델 입력 state 에서 칸을 놓을 순서다. 같은 칸이 다시 나오면 값은 나중 것을 쓰고 자리는 처음 나온 자리를 쓴다(a_state 가 dict 에 쓰는 규칙). 이 중 어느 문항의 칸을 모델 입력에 넣을지는 model-runtime 이 정한다
    """

    root: Annotated[list[StoredSlot], Field(max_length=136)]
    """
    이번 턴을 반영하기 전에 세션에 저장된 모든 칸 값과 다시 묻는 중인 칸의 목록. 배열의 순서가 모델 입력 state 에서 칸을 놓을 순서다. 같은 칸이 다시 나오면 값은 나중 것을 쓰고 자리는 처음 나온 자리를 쓴다(a_state 가 dict 에 쓰는 규칙). 이 중 어느 문항의 칸을 모델 입력에 넣을지는 model-runtime 이 정한다
    """


class SurveyServiceEnv(BaseModel):
    """
    deploy 가 survey-service 에 주는 환경 입력. 비밀은 NAME_FILE 경로로만 준다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    OPENIT_DATABASE_PASSWORD_FILE: SecretFilePath
    """
    문진 데이터베이스 비밀번호 파일. 필요한 컴포넌트: store
    """
    OPENIT_DATABASE_URL: DatabaseUrl
    """
    문진 데이터베이스 접속 주소. 필요한 컴포넌트: store
    """
    OPENIT_EGRESS_PROXY: EgressProxyUrl
    """
    나가는 호출이 지나는 게이트웨이 터널. 필요한 컴포넌트: link_model_client, link_push
    """
    OPENIT_LISTEN_PORT: ListenPort
    """
    요청을 받을 포트. 필요한 컴포넌트: link_kiosk_api, link_admin_api, link_hospital_api
    """
    OPENIT_LOG_LEVEL: LogLevel | None = None
    """
    로그 수준. 필요한 컴포넌트: 모든 컴포넌트
    """
    OPENIT_MACHINE_TOKENS_FILE: ConfigFilePath
    """
    이 서비스를 부르는 기계 호출자 표 파일(MachineTokenTable 모양). 필요한 컴포넌트: link_hospital_api, link_risk_in, 실패 사례를 내보내는 link_admin_api
    """
    OPENIT_MODEL_RUNTIME_TOKEN_FILE: SecretFilePath
    """
    model-runtime 에 보일 기계 토큰 파일. 필요한 컴포넌트: link_model_client
    """
    OPENIT_MODEL_RUNTIME_URL: PeerBaseUrl
    """
    추론을 부를 model-runtime 주소. 필요한 컴포넌트: link_model_client
    """
    OPENIT_OIDC_AUDIENCE: ServiceName
    """
    이 서비스의 이름. 접근 토큰의 aud 에 이 이름이 있어야 받는다. 필요한 컴포넌트: link_admin_api
    """
    OPENIT_OIDC_ISSUER_URL: OidcIssuerUrl
    """
    사람 접근 토큰의 허용 발급자(iss). 다른 발급자의 토큰은 거절한다. 필요한 컴포넌트: link_admin_api
    """
    OPENIT_OIDC_JWKS_URL: OidcJwksUrl | None = None
    """
    발급자의 서명 공개 키 집합 주소(없으면 발급자의 디스커버리 문서에서 얻는다). 필요한 컴포넌트: link_admin_api
    """
    OPENIT_ROOT_CERTIFICATE_FILE: ConfigFilePath
    """
    신뢰할 사설 CA(또는 조직 CA)의 루트 인증서 파일. 영역 사이 TLS 의 신뢰 앵커다. 필요한 컴포넌트: link_kiosk_api, link_admin_api, link_hospital_api, link_model_client
    """
    OPENIT_TLS_CERTIFICATE_FILE: ConfigFilePath
    """
    이 서비스의 인증서 파일(영역 사이 mTLS 의 서버·클라이언트 인증서, 사설 CA 가 발급). 필요한 컴포넌트: link_kiosk_api, link_admin_api, link_hospital_api, link_model_client
    """
    OPENIT_TLS_PRIVATE_KEY_FILE: SecretFilePath
    """
    이 서비스의 TLS 개인키 파일. 필요한 컴포넌트: link_kiosk_api, link_admin_api, link_hospital_api
    """
    OPENIT_VAPID_PRIVATE_KEY_FILE: SecretFilePath
    """
    웹 푸시 VAPID 개인키 파일. 필요한 컴포넌트: link_push
    """
    OPENIT_VAPID_SUBJECT: VapidSubject
    """
    VAPID 연락처. 필요한 컴포넌트: link_push
    """
    SURVEY_DEVICE_PLACEMENTS_FILE: ConfigFilePath | None = None
    """
    기기별 기본 문진표 배치표 파일(DevicePlacementTable 모양). 필요한 컴포넌트: session
    """
    SURVEY_EXPLAIN_STREAK_LIMIT: ExplainStreakLimit | None = None
    """
    설명 요청 연속 한도. 필요한 컴포넌트: session
    """
    SURVEY_FHIR_CANONICAL_BASE_URL: FhirCanonicalBaseUrl | None = None
    """
    FHIR 결과의 questionnaire 정본 URL 의 기준 주소. 필요한 컴포넌트: result
    """
    SURVEY_RAW_UTTERANCE_RETENTION_DAYS: RawUtteranceRetentionDays | None = None
    """
    검토용 환자 발화 원문 보존 일수. 필요한 컴포넌트: trace, failure_case
    """
    SURVEY_REASK_LIMIT: ReaskLimit | None = None
    """
    되묻기 한도. 필요한 컴포넌트: session
    """
    SURVEY_RISK_DETECTION_ENABLED: Annotated[
        RiskDetectionEnabled | None, Field(validate_default=True)
    ] = False
    """
    위험 감지 사용 여부. 필요한 컴포넌트: link_risk_in
    """
    SURVEY_START_CODE_TTL_SECONDS: Annotated[
        StartCodeTtlSeconds | None, Field(validate_default=True)
    ] = 300
    """
    시작 코드 유효 시간. 필요한 컴포넌트: start_code
    """


class TurnRequest(BaseModel):
    """
    환자 발화 한 턴을 서버에 보내는 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    turn_id: TurnId
    """
    이 턴의 식별자(재전송 때 같은 값)
    """
    utterance: UtteranceText
    """
    환자의 발화
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


class ActiveQuestionnaireList(BaseModel):
    """
    지금 활성인 문항 세트가 있는 문진표 목록
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    questionnaires: Annotated[list[QuestionnaireSummary], Field(max_length=100)]
    """
    문진표 요약들
    """


class ExtractedValue(BaseModel):
    """
    LoRA-A 가 이번 말에서 뽑은 칸 값 하나. status 와 save 의 짝, value 가 null 인 status 는 이 스키마가 아니라 ActionExtractionRules(SAVE_RULE)가 정한다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    key: SlotRefString
    """
    값이 들어갈 칸
    """
    precision: ValuePrecision
    """
    값의 정확도
    """
    save: ValueSave
    """
    저장 여부
    """
    status: ValueStatus
    """
    값의 상태
    """
    value: SlotAnswer
    """
    뽑은 값(저장할 값이 없으면 null)
    """


class ExtractedValues(RootModel[list[ExtractedValue]]):
    """
    뽑은 칸 값들
    """

    root: Annotated[list[ExtractedValue], Field(max_length=8)]
    """
    뽑은 칸 값들
    """


class FhirMapping(BaseModel):
    """
    문진 결과(SessionResult)를 FHIR R4 QuestionnaireResponse 로 옮기는 규칙(데이터). questionnaire 는 FhirCanonicalBaseUrl 에 슬래시와 문진표 식별자를 붙인 정본 URL 이다. item.linkId 는 문항이면 문항 식별자이고 칸이면 SlotRefString 이다. subject.identifier.value 는 SubjectRef 다. 저장된 답은 item.answer 로, 빈칸은 answer 없이 data-absent-reason 확장으로 낸다. FHIR 조회의 오류는 OperationOutcome 이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    absent_map: Annotated[list[FhirAbsentMapEntry], Field(max_length=5)]
    """
    빈칸 원인에서 FHIR 빈칸 사유로 가는 대응(UNKNOWN 과 UNCLEAR 와 REASK_LIMIT 는 asked-unknown, REJECTED 는 asked-declined, UNASKED 는 not-asked)
    """
    status_map: Annotated[list[FhirStatusMapEntry], Field(max_length=5)]
    """
    세션 상태에서 FHIR status 로 가는 대응(ACTIVE 와 PAUSED 는 in-progress, ENDED_COMPLETE 는 completed, ENDED_PARTIAL 과 EXPIRED 는 stopped)
    """


class FlowBranch(BaseModel):
    """
    분기 하나. 조건이 맞으면 다음 자리로 간다. 조건이 없으면 앞 분기가 모두 맞지 않을 때의 기본 경로다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    next_item: FlowTarget
    """
    조건이 맞을 때 가는 다음 자리
    """
    when: FlowCondition | None = None
    """
    이 분기를 고르는 조건
    """


class FlowRule(BaseModel):
    """
    문항 하나 다음에 어디로 가는지의 분기들. 앞에서부터 처음 맞는 분기를 쓴다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    branches: Annotated[list[FlowBranch], Field(max_length=4)]
    """
    분기들(순서가 의미를 가진다)
    """
    item_id: QuestionItemId
    """
    이 규칙이 다음을 정하는 문항
    """


class QuestionBank(BaseModel):
    """
    한 문진표의 문항 정의 전체(문항 은행)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: QuestionItems
    """
    문항들
    """


class QuestionFlowTable(BaseModel):
    """
    문항 순서와 건너뛰기 규칙 표. 추론 서버가 출력의 다음 문항을 이 표로 보증하고 채운다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    rules: Annotated[list[FlowRule], Field(max_length=62)]
    """
    문항별 다음 규칙
    """
    start_item: QuestionItemId
    """
    첫 문항
    """


class QuestionSetContent(BaseModel):
    """
    문진표 한 벌의 내용(제목, 문항 은행, 순서표)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    bank: QuestionBank
    """
    문항 정의
    """
    flow: QuestionFlowTable
    """
    순서와 건너뛰기
    """
    title: QuestionnaireTitle
    """
    문진표 제목
    """


class QuestionSetUpload(BaseModel):
    """
    문항 세트를 올리는 본문. 올린 사람은 본문이 아니라 인증된 사용자에서 얻는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    content: QuestionSetContent
    """
    문진표 내용
    """
    questionnaire_id: QuestionnaireId
    """
    올릴 문진표(이미 있으면 새 버전이 된다)
    """
    runtime_contract_version: RuntimeContractVersion
    """
    올리는 문항 은행과 칸 키의 정수 버전
    """


class QuestionSetVersion(BaseModel):
    """
    올린 문항 세트의 한 버전. 한 번 저장하면 바뀌지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    content: QuestionSetContent
    """
    문진표 내용
    """
    content_hash: Sha256Digest
    """
    내용의 해시(서버가 계산한다)
    """
    created_at: Timestamp
    """
    버전을 저장한 때
    """
    question_set_version_id: QuestionSetVersionId
    """
    이 버전의 식별자
    """
    questionnaire_id: QuestionnaireId
    """
    문진표 식별자
    """
    runtime_contract_version: RuntimeContractVersion
    """
    문항 은행과 칸 키의 정수 버전
    """
    uploaded_by: UserId
    """
    올린 사람(OIDC 접근 토큰의 sub)
    """
    version_number: Int32Positive
    """
    같은 문진표 안의 버전 순번(서버가 올린다)
    """


class QuestionSetVersionPage(BaseModel):
    """
    저장한 문항 세트 버전 목록 한 쪽
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: Annotated[list[QuestionSetVersion], Field(max_length=100)]
    """
    문항 세트 버전들(최근 것이 먼저)
    """
    next_cursor: PageCursor | None = None
    """
    다음 쪽 커서
    """


class ResponseGenerationRequest(BaseModel):
    """
    추론 서버에 LoRA-B 응답 문장 생성을 요청하는 본문. 행동과 사유, A 출력의 값·칸·노트, 환자의 말, 저장된 칸 값, 다음 자리의 구조화된 값만 싣는다. 모델 입력에 들어가는 글(topic, known, ask, previous, current, hold)은 model-runtime 이 데이터셋 정본의 표와 규칙(labels.py)으로 만든다. 다음 문항의 질문 문장(next.text)은 문항 세트의 문장이라 서비스가 보낸다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: ResponseAction
    """
    문장을 만들 절차(A 출력의 action, 시작이면 START)
    """
    next: ResponseNext
    """
    응답 뒤에 가는 자리(서비스가 정한다. 시작이면 순서표의 첫 문항)
    """
    note: OutOfSchemaNote | None = None
    """
    A 출력의 note 그대로(REDIRECT 의 OUT_OF_SCHEMA)
    """
    previous_question_id: QuestionItemId | None = None
    """
    대화에서 직전에 물은 문항(A 를 부를 때 보낸 값과 같다). 첫 문항이면 없다
    """
    question_id: QuestionItemId | None = None
    """
    A 를 부를 때 지금 묻고 있던 문항(START 에는 없다). 값이 없는 보류·거절에서 비우는 부분을 가리킬 때 쓴다
    """
    reason: ActionReason | None = None
    """
    그 절차의 사유(A 출력의 reason)
    """
    runtime_contract_version: RuntimeContractVersion
    """
    요청하는 쪽이 쓰는 문항 은행 버전(활성 문항 세트의 값). 적재한 모델 패키지가 학습한 값과 다르면 QUESTION_BANK_VERSION_MISMATCH 로 거절한다
    """
    slots: StoredSlots | None = None
    """
    이번 턴을 반영하기 전에 저장된 칸 값들(A 를 부를 때 보낸 목록과 같다). 이전 값(CONFIRM)과 되묻는 문장에 쓰는 이미 받은 값의 원재료다(START 에는 없다)
    """
    targets: SlotRefStrings | None = None
    """
    A 출력의 targets 그대로(REASK, CONFIRM, HOLD, SKIP)
    """
    user_utterance: UtteranceText | None = None
    """
    환자의 이번 말(START 에는 없다)
    """
    values: ExtractedValues | None = None
    """
    A 출력의 values 그대로(START 에는 없다). 이번 턴에 정해진 값과 충돌한 값의 원재료다
    """


class ResultAnswer(BaseModel):
    """
    결과에 저장된 답 하나(칸, 값, 정확도)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    key: SlotRefString
    """
    답이 담긴 칸
    """
    precision: ValuePrecision
    """
    값이 정확한지 대략인지
    """
    value: SlotAnswer
    """
    저장된 값
    """


class ResultPage(BaseModel):
    """
    결과 목록 한 쪽
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: Annotated[list[ResultSummary], Field(max_length=100)]
    """
    결과 요약들(최근 것이 먼저)
    """
    next_cursor: PageCursor | None = None
    """
    다음 쪽 커서
    """


class SessionResult(BaseModel):
    """
    한 세션의 문진 결과. 끝나지 않은 세션은 부분 결과로 상태와 함께 나온다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    acknowledged_at: Timestamp | None = None
    """
    의사가 확인한 때
    """
    acknowledged_by: UserId | None = None
    """
    결과를 확인한 의사(아직이면 없다)
    """
    answers: Annotated[list[ResultAnswer], Field(max_length=68)]
    """
    저장된 답들
    """
    blanks: Annotated[list[ResultBlank], Field(max_length=68)]
    """
    비어 있는 칸들과 원인
    """
    device_id: DeviceId | None = None
    """
    문진을 한 키오스크 기기
    """
    ended_at: Timestamp | None = None
    """
    세션이 끝난 때(진행 중이면 없다)
    """
    question_set_version_id: QuestionSetVersionId
    """
    답한 문진표의 버전
    """
    questionnaire_id: QuestionnaireId
    """
    문진표
    """
    questionnaire_title: QuestionnaireTitle | None = None
    """
    문진표 제목
    """
    session_id: SessionId
    """
    결과가 속한 세션
    """
    started_at: Timestamp
    """
    세션을 시작한 때
    """
    status: SessionStatus
    """
    세션 상태(끝나지 않았으면 부분 결과다)
    """
    subject_ref: SubjectRef
    """
    문진 대상자 참조값
    """


class ActionExtraction(BaseModel):
    """
    LoRA-A 의 출력(규칙 보증을 마친 값). 받는 쪽은 다시 검증하지 않는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: ExtractionAction
    """
    고른 절차
    """
    next_item: FlowTarget
    """
    다음 문항(없으면 END). 추론 서버가 순서표로 보증해 채운다
    """
    note: OutOfSchemaNote | None = None
    """
    OUT_OF_SCHEMA 일 때 환자가 말한 문진표 밖 건강 이야기
    """
    reason: ActionReason | None = None
    """
    절차의 사유(NEXT 와 CORRECT 에는 없다)
    """
    targets: SlotRefStrings | None = None
    """
    REASK, CONFIRM, HOLD, SKIP 이 겨냥하는 칸들
    """
    values: ExtractedValues
    """
    뽑은 칸 값들
    """


class CaseReview(BaseModel):
    """
    검토자가 사례에 게시하는 검토 결과
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    base_case_version: CaseVersion
    """
    검토자가 본 사례의 버전. 최신 버전과 다르면 409(CASE_VERSION_MISMATCH)로 거절해 동시 수정을 막는다
    """
    expected: ActionExtraction | None = None
    """
    확정한 기대 출력
    """
    review_status: ReviewStatus
    """
    확정한 상태
    """
    reviewed_input: ReviewedInput | None = None
    """
    고쳐 쓴 발화
    """


class DeidentifiedTrace(BaseModel):
    """
    비식별 처리를 마친 턴 기록(검토자가 읽는 것)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    case_id: CaseId
    """
    이 기록이 속한 사례
    """
    extract_output: ActionExtraction | None = None
    """
    LoRA-A 의 출력
    """
    failure_signal: TurnFailureReason | None = None
    """
    턴이 값을 만들지 못했다면 그 신호
    """
    occurred_at: Timestamp
    """
    턴이 끝난 때
    """
    response_text: ResponseSentence | None = None
    """
    LoRA-B 가 만든 문장
    """
    utterance: DeidentifiedUtterance | None = None
    """
    비식별을 마친 발화
    """


class ExtractionRequest(BaseModel):
    """
    추론 서버에 LoRA-A 추출을 요청하는 본문. 지금 묻는 문항, 상담원이 방금 한 말, 환자의 말, 저장된 칸 값, 순서표, 칸 규격의 구조화된 값만 싣는다. 모델 입력의 글자와 state 에 넣을 문항의 선택은 model-runtime 이 데이터셋 정본(labels.py, IO_SPEC.md 2.1)으로 만든다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    current_question: ResponseSentence
    """
    상담원이 방금 환자에게 한 말(화면에 보인 직전 질문, 모델 입력의 current_question). 서비스가 화면에 보인 글이라 서비스가 보낸다. 환자의 말은 이 질문에 대한 답으로 읽는다
    """
    fields: QuestionFieldSpecs
    """
    출력 값을 보증하는 칸 규격들
    """
    flow: QuestionFlowTable
    """
    출력의 다음 문항을 보증하는 순서표
    """
    previous_question_id: QuestionItemId | None = None
    """
    대화에서 직전에 물은 문항(건너뛰기를 반영한 것, IO_SPEC.md 2.1 의 state 규칙). 첫 문항이면 없다. 세션의 진행을 아는 쪽만 알 수 있어 서비스가 보낸다(ADR 0019 의 책임선)
    """
    question_id: QuestionItemId
    """
    지금 묻고 있는 문항(모델 입력의 question_id)
    """
    runtime_contract_version: RuntimeContractVersion
    """
    요청하는 쪽이 쓰는 문항 은행 버전(활성 문항 세트의 값). 적재한 모델 패키지가 학습한 값과 다르면 QUESTION_BANK_VERSION_MISMATCH 로 거절한다
    """
    slots: StoredSlots
    """
    이번 턴을 반영하기 전에 저장된 칸 값들. model-runtime 이 지금 문항·직전에 물은 문항·참조 원천 문항의 것만 골라 모델 입력 state 로 쓴다
    """
    user_utterance: UtteranceText
    """
    환자의 이번 말
    """


class ExtractionResult(BaseModel):
    """
    LoRA-A 추출 응답. 처리한 모델 패키지와 검증을 마친 출력
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    output: ActionExtraction
    """
    보증을 마친 LoRA-A 출력
    """
    package_digest: OciDigest
    """
    이 출력을 만든 모델 패키지(OCI 매니페스트 digest)
    """


class FailureCase(BaseModel):
    """
    실패 사례 하나. 비식별한 턴 기록에서 만들고 검토자가 확정한다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    case_id: CaseId
    """
    사례 식별자
    """
    case_version: CaseVersion
    """
    검토 버전
    """
    created_at: Timestamp
    """
    사례를 만든 때
    """
    expected: ActionExtraction | None = None
    """
    검토자가 확정한 기대 출력(CONFIRMED 일 때)
    """
    item_id: QuestionItemId
    """
    실패가 난 문항
    """
    kind: FailureKind
    """
    찾아낸 규칙
    """
    model_output: ActionExtraction | None = None
    """
    모델이 낸 출력
    """
    questionnaire_id: QuestionnaireId
    """
    문진표
    """
    review_status: ReviewStatus
    """
    검토 상태
    """
    reviewed_at: Timestamp | None = None
    """
    검토한 때
    """
    reviewed_by: UserId | None = None
    """
    검토한 사람
    """
    reviewed_input: ReviewedInput | None = None
    """
    검토자가 고쳐 쓴 발화
    """
    utterance: UtteranceText | None = None
    """
    검토용 환자 발화 원문(보존 180일)
    """


class FailureCaseExport(BaseModel):
    """
    model-lab 이 당겨 가는 실패 사례. 환자 발화 원문과 모델 출력을 빼고 검토자가 개인정보를 뺀 문장과 기대 출력만 담는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    case_id: CaseId
    """
    사례 식별자
    """
    case_version: CaseVersion
    """
    검토 버전
    """
    created_at: Timestamp
    """
    사례를 만든 때
    """
    expected: ActionExtraction | None = None
    """
    검토자가 확정한 기대 출력(CONFIRMED 일 때)
    """
    item_id: QuestionItemId
    """
    실패가 난 문항
    """
    kind: FailureKind
    """
    찾아낸 규칙
    """
    questionnaire_id: QuestionnaireId
    """
    문진표
    """
    review_status: ReviewStatus
    """
    검토 상태
    """
    reviewed_input: ReviewedInput | None = None
    """
    검토자가 개인정보를 빼고 고쳐 쓴 발화(검토를 마친 사례에만 있다)
    """


class FailureCaseExportPage(BaseModel):
    """
    학습·데이터 영역이 읽는 실패 사례 목록 한 쪽
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: Annotated[list[FailureCaseExport], Field(max_length=100)]
    """
    사례들
    """
    next_cursor: PageCursor | None = None
    """
    다음 쪽 커서
    """


class FailureCasePage(BaseModel):
    """
    실패 사례 목록 한 쪽
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    items: Annotated[list[FailureCase], Field(max_length=100)]
    """
    사례들
    """
    next_cursor: PageCursor | None = None
    """
    다음 쪽 커서
    """
