# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal
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


class AdapterRole(StrEnum):
    """
    어댑터의 역할
    """

    LORA_A = 'LORA_A'
    LORA_B = 'LORA_B'


class ArgvElement(RootModel[str]):
    root: Annotated[str, Field(examples=['/usr/local/bin/openit-run'], max_length=4096)]
    """
    시작 프로세스 명령줄의 요소 하나
    """


class AuthenticateChallenge(RootModel[str]):
    root: Annotated[str, Field(examples=['Bearer realm="openit"'], max_length=8000)]
    """
    WWW-Authenticate 헤더 값(예를 들어 Bearer realm 과 error 를 담은 도전)
    """


class BaseModelName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['Qwen/Qwen3-8B'],
            max_length=96,
            pattern='^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)?$',
        ),
    ]
    """
    기반 모델의 이름(모델 허브 식별자 형태, 예를 들어 Qwen/Qwen3-8B)
    """


class ByteSize(RootModel[int]):
    root: Annotated[int, Field(examples=[174655536], ge=0, le=9007199254740991)]
    """
    파일의 크기(바이트)
    """


class CapabilityName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['CAP_NET_BIND_SERVICE'], max_length=40, pattern='^CAP_[A-Z_]+$'
        ),
    ]
    """
    컨테이너에 더하는 Linux capability 의 이름(추가 권한). 기본은 모두 뺀 상태에서 더한다
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


class ConstrainedDecoding(RootModel[bool]):
    root: bool
    """
    출력을 스키마에 맞게 제약하며 만드는지(참이면 제약 디코딩)
    """


class ContainerPath(RootModel[str]):
    root: Annotated[
        str, Field(examples=['/var/lib/openit/cache'], max_length=4096, pattern='^/')
    ]
    """
    컨테이너 안의 절대 경로
    """


class DatasetVersionId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    게시된 데이터셋 한 버전의 식별자
    """


class EgressProxyUrl(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['http://127.0.0.1:3128'])]
    """
    영역 게이트웨이의 나가는 CONNECT 터널 주소. Exposure.egress 에 선언한 상대에게만 닿는다
    """


class EnvKind(StrEnum):
    """
    환경 입력의 종류
    """

    VALUE = 'VALUE'
    SECRET_FILE = 'SECRET_FILE'
    FILE_PATH = 'FILE_PATH'


class EnvVarName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['OPENIT_LISTEN_PORT'], max_length=63, pattern='^[A-Z_][A-Z0-9_]*$'
        ),
    ]
    """
    환경 변수의 이름
    """


class ExtraMetricName(RootModel[str]):
    root: Annotated[str, Field(examples=['turn_count'], max_length=63)]
    """
    필수 지표 밖의 지표 이름(영문 소문자와 밑줄)
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


class IsRequired(RootModel[bool]):
    root: bool
    """
    환경 입력이 없으면 서비스가 시작하지 않는지(참이면 필수 입력)
    """


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


class MetricGroupName(RootModel[str]):
    root: Annotated[str, Field(examples=['ACCURACY'], max_length=63)]
    """
    평가 지표의 묶음 이름(예를 들어 ACCURACY)
    """


class MetricSlice(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['violation_code=OUT_OF_CURRENT_ITEM'],
            max_length=84,
            pattern='^(action|violation_code|constrained_decoding|question_type|unit|value_range)=[A-Za-z0-9_.-]{1,63}$',
        ),
    ]
    """
    지표를 쪼갠 조각. 기준 이름(MetricSliceDimension)과 값을 등호로 이은 글(예를 들어 action=REASK, violation_code=OUT_OF_CURRENT_ITEM, constrained_decoding=on). 전체이면 없다
    """


class MetricUnit(StrEnum):
    """
    평가 지표 값의 단위
    """

    ratio = 'ratio'
    seconds = 'seconds'
    count_ = 'count'


class MetricValue(RootModel[float]):
    root: Annotated[float, Field(examples=[0.93], ge=0.0, le=9007199254740991.0)]
    """
    지표 값(단위는 같은 지표의 unit 이 정한다)
    """


class ModelChangeReason(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['평가 보고서의 의미 위반율이 활성 패키지보다 낮다'],
            max_length=4000,
            min_length=1,
        ),
    ]
    """
    모델 패키지 활성화나 롤백을 결정한 사람이 적는 까닭
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


class ModelPackageArtifactType(
    RootModel[Literal['application/vnd.openit.model.package.v1']]
):
    root: Literal['application/vnd.openit.model.package.v1']
    """
    모델 패키지 OCI 아티팩트의 artifactType. model-runtime 은 이 값이 아닌 아티팩트를 모델 패키지로 받지 않는다
    """


class ModelPackageBlobMediaType(StrEnum):
    """
    모델 패키지 OCI 아티팩트 안의 파일 하나(config 와 layer)의 미디어 유형
    """

    application_vnd_openit_model_package_config_v1_json = (
        'application/vnd.openit.model.package.config.v1+json'
    )
    application_vnd_openit_model_adapter_weights_v1 = (
        'application/vnd.openit.model.adapter.weights.v1'
    )
    application_vnd_openit_model_adapter_system_prompt_v1 = (
        'application/vnd.openit.model.adapter.system-prompt.v1'
    )


class ModelProfileName(RootModel[str]):
    root: Annotated[str, Field(examples=['rtx4090-24g'], max_length=63)]
    """
    추론 서버의 GPU 크기별 프로파일 이름(기반 모델과 서빙 크기를 고른다)
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


class OciImageManifestMediaType(
    RootModel[Literal['application/vnd.oci.image.manifest.v1+json']]
):
    root: Literal['application/vnd.oci.image.manifest.v1+json']
    """
    OCI 이미지 매니페스트의 미디어 유형(모델 패키지도 이 매니페스트 형식을 쓴다)
    """


class OciRepositoryName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['openit/model-package'],
            max_length=255,
            pattern='^[a-z0-9]+((\\.|_|__|-+)[a-z0-9]+)*(/[a-z0-9]+((\\.|_|__|-+)[a-z0-9]+)*)*$',
        ),
    ]
    """
    OCI 레지스트리의 저장소 이름(모델 패키지를 올리고 받는 곳)
    """


class OciSchemaVersion(RootModel[Literal[2]]):
    root: Annotated[Literal[2], Field(ge=2, le=2)]
    """
    OCI 이미지 매니페스트의 schemaVersion(항상 2)
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


class PathPersistent(RootModel[bool]):
    root: bool
    """
    쓰는 경로의 내용이 컨테이너를 다시 만들어도 남아야 하는지(참이면 유지되는 볼륨, 거짓이면 임시 저장소)
    """


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


class ProcessDeclaration(BaseModel):
    """
    시작 프로세스 하나의 실행 규칙. 서비스의 진입점이면 job 이 없고 잡이면 그 잡의 이름이 있다. 첫 요소는 절대 경로다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    argv: list[Any] | None = None
    job: JobName | None = None
    """
    이 규칙이 실행하는 잡(서비스의 진입점이면 없다)
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


class RequiredMetricName(StrEnum):
    """
    평가 보고서가 반드시 담는 지표의 이름과 뜻(계산식, 단위, 분모, slice). 이 밖의 지표 이름도 MetricName 으로 낼 수 있다
    """

    value_precision = 'value_precision'
    value_recall = 'value_recall'
    precision_match_rate = 'precision_match_rate'
    next_item_accuracy = 'next_item_accuracy'
    schema_valid_raw = 'schema_valid_raw'
    semantic_violation_rate = 'semantic_violation_rate'
    ungrounded_number_rate = 'ungrounded_number_rate'
    forbidden_expression_rate = 'forbidden_expression_rate'
    length_p95_seconds = 'length_p95_seconds'


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


class RollbackCommand(BaseModel):
    """
    활성 모델 패키지를 이전에 활성이었던 패키지로 되돌리는 본문. 하는 사람은 OIDC 접근 토큰의 sub 클레임에서 얻는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    reason: ModelChangeReason
    """
    되돌리는 까닭
    """
    target_package_digest: OciDigest
    """
    되돌아갈 모델 패키지. 이전에 활성이었던 패키지여야 한다
    """


class RunAsUid(RootModel[int]):
    root: Annotated[int, Field(examples=[10001], ge=1, le=4294967294)]
    """
    이미지가 실행되는 숫자 사용자 ID(root 가 아니다)
    """


class RuntimeContractVersion(RootModel[int]):
    root: Annotated[int, Field(examples=[1], ge=1, le=2147483647)]
    """
    문항 은행과 칸 키의 정수 버전. 모델 패키지가 학습한 값과 다르면 적재와 승인을 거부한다
    """


class SampleCount(RootModel[int]):
    root: Annotated[int, Field(examples=[400], ge=0, le=2147483647)]
    """
    지표를 계산한 표본의 수
    """


class SamplingTemperature(RootModel[float]):
    root: Annotated[float, Field(examples=[0], ge=0.0, le=2.0)]
    """
    응답을 만들 때 다음 글자를 고르는 무작위성의 크기. 0 이면 가장 확률 높은 것만 고르고 클수록 다양하다
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


class SemanticVersion(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['0.11.10'],
            max_length=64,
            pattern='^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-((?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\\.(?:0|[1-9]\\d*|\\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\\+([0-9a-zA-Z-]+(?:\\.[0-9a-zA-Z-]+)*))?$',
        ),
    ]
    """
    의미 있는 버전 문자열(MAJOR.MINOR.PATCH)
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


class StoredSlotStatus(StrEnum):
    """
    서비스가 저장하고 있는 칸 하나의 상태
    """

    ANSWERED = 'ANSWERED'
    MISSING = 'MISSING'
    UNCLEAR = 'UNCLEAR'


class SysctlName(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['net.ipv4.ip_unprivileged_port_start'],
            max_length=255,
            pattern='^[a-z0-9_]+(\\.[a-z0-9_]+)+$',
        ),
    ]
    """
    컨테이너에 주입하는 sysctl 의 이름(점으로 이은 소문자 키)
    """


class SysctlValue(RootModel[str]):
    root: Annotated[str, Field(examples=['0'], max_length=255)]
    """
    sysctl 에 주는 값(글자로 쓴다)
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


class TokenLimit(RootModel[int]):
    root: Annotated[int, Field(examples=[512], ge=1, le=32768)]
    """
    한 번에 만들 수 있는 최대 토큰 수
    """


class TrainingRunId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    학습 실행 하나의 식별자
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


class WritablePath(BaseModel):
    """
    컨테이너가 쓰는 경로 하나(경로, 유지 여부, 쓰는 사용자). 루트 파일시스템은 읽기 전용이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    owner_uid: RunAsUid
    """
    그 경로에 쓰는 사용자
    """
    path: ContainerPath
    """
    쓰는 경로
    """
    persistent: PathPersistent
    """
    유지 여부
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


class ActivationRequest(BaseModel):
    """
    승인자가 모델 패키지를 활성화하는 본문. 승인자는 본문이 아니라 OIDC 접근 토큰의 sub 클레임에서 얻는다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    package_digest: OciDigest
    """
    활성으로 만들 모델 패키지(OCI 매니페스트 digest)
    """
    reason: ModelChangeReason
    """
    활성화하는 까닭
    """


class ConditionValue(RootModel[YesNoAnswer | SlotNumber | OptionCode]):
    root: YesNoAnswer | SlotNumber | OptionCode
    """
    건너뛰기 조건이 비교하는 값(예 또는 아니오, 수, 선택지 코드 중 하나)
    """


class EnvDeclaration(BaseModel):
    """
    이미지가 받는 환경 입력 하나의 선언
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    kind: EnvKind
    """
    입력의 종류
    """
    name: EnvVarName
    """
    환경 변수 이름
    """
    required: IsRequired
    """
    없으면 시작하지 않는 입력인지
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


class MetricName(RootModel[RequiredMetricName | ExtraMetricName]):
    root: RequiredMetricName | ExtraMetricName
    """
    평가 지표의 이름. 필수 지표(RequiredMetricName) 또는 자유 이름
    """


class ModelPackageBlobDescriptor(BaseModel):
    """
    모델 패키지 OCI 아티팩트 안의 파일 하나를 가리키는 OCI descriptor(미디어 유형, digest, 크기). 받는 쪽은 내려받아 digest 를 확인한다. 칸 이름은 OCI 표준 그대로다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    digest: OciDigest
    """
    파일 내용의 digest
    """
    mediaType: ModelPackageBlobMediaType
    """
    파일의 미디어 유형
    """
    size: ByteSize
    """
    파일 크기(바이트)
    """


class ModelPackageOciManifest(BaseModel):
    """
    레지스트리에 게시되는 모델 패키지의 OCI 이미지 매니페스트(OCI 아티팩트). artifactType 이 모델 패키지임을 가리키고, config 는 목록표(ModelPackageManifest), layers 는 어댑터 가중치 둘과 시스템 프롬프트 둘이다. 이 매니페스트의 digest 가 모델 패키지의 식별자다. 칸 이름은 OCI 표준 그대로다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    artifactType: ModelPackageArtifactType
    """
    이 아티팩트가 모델 패키지임을 가리키는 유형
    """
    config: ModelPackageBlobDescriptor
    """
    목록표(ModelPackageManifest) 파일. 미디어 유형은 config 유형이다
    """
    layers: Annotated[
        list[ModelPackageBlobDescriptor], Field(max_length=4, min_length=4)
    ]
    """
    어댑터 가중치와 시스템 프롬프트 파일들
    """
    mediaType: OciImageManifestMediaType
    """
    OCI 이미지 매니페스트의 미디어 유형
    """
    schemaVersion: OciSchemaVersion
    """
    OCI 매니페스트 버전
    """


class ModelRuntimeEnv(BaseModel):
    """
    deploy 가 model-runtime 에 주는 환경 입력(추론 서버가 다른 서버에 있어도 같다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    OPENIT_EGRESS_PROXY: EgressProxyUrl | None = None
    """
    나가는 호출이 지나는 게이트웨이 터널(같은 서버에 있을 때). 필요한 컴포넌트: link_registry
    """
    OPENIT_HOSTS_TABLE_FILE: ConfigFilePath | None = None
    """
    다른 서버에서 survey-service 와 레지스트리를 찾는 이름 표 파일(다른 서버일 때만). 필요한 컴포넌트: link_registry
    """
    OPENIT_LISTEN_PORT: ListenPort
    """
    요청을 받을 포트. 필요한 컴포넌트: link_api
    """
    OPENIT_LOG_LEVEL: LogLevel | None = None
    """
    로그 수준. 필요한 컴포넌트: 모든 컴포넌트
    """
    OPENIT_MACHINE_TOKENS_FILE: ConfigFilePath
    """
    이 서비스를 부르는 기계 호출자 표 파일(MachineTokenTable 모양). 필요한 컴포넌트: link_api
    """
    OPENIT_MODEL_CACHE_DIR: ConfigFilePath
    """
    기반 모델 가중치를 받아 두는 유지되는 폴더(모델 허브에서 처음 시작할 때 받는다). 필요한 컴포넌트: inference
    """
    OPENIT_MODEL_PROFILE: ModelProfileName
    """
    GPU 크기별 프로파일 이름. 필요한 컴포넌트: inference
    """
    OPENIT_OIDC_AUDIENCE: ServiceName
    """
    이 서비스의 이름. 접근 토큰의 aud 에 이 이름이 있어야 받는다. 필요한 컴포넌트: link_api
    """
    OPENIT_OIDC_ISSUER_URL: OidcIssuerUrl
    """
    활성화 승인과 롤백을 호출하는 사람 접근 토큰의 허용 발급자(iss). 다른 발급자의 토큰은 거절한다. 필요한 컴포넌트: link_api
    """
    OPENIT_OIDC_JWKS_URL: OidcJwksUrl | None = None
    """
    발급자의 서명 공개 키 집합 주소(없으면 발급자의 디스커버리 문서에서 얻는다). 필요한 컴포넌트: link_api
    """
    OPENIT_REGISTRY_CREDENTIALS_FILE: SecretFilePath
    """
    레지스트리에서 받을 때 보일 자격 파일(읽기 권한). 필요한 컴포넌트: link_registry
    """
    OPENIT_REGISTRY_REPOSITORY: OciRepositoryName
    """
    모델 패키지가 올라 있는 레지스트리 저장소 이름. 필요한 컴포넌트: link_registry
    """
    OPENIT_REGISTRY_URL: PeerBaseUrl
    """
    모델 패키지를 digest 로 받을 레지스트리 주소(OCI Distribution). 필요한 컴포넌트: link_registry
    """
    OPENIT_ROOT_CERTIFICATE_FILE: ConfigFilePath
    """
    신뢰할 사설 CA(또는 조직 CA)의 루트 인증서 파일. 영역 사이 TLS 의 신뢰 앵커다. 필요한 컴포넌트: link_api, link_registry
    """
    OPENIT_TLS_CERTIFICATE_FILE: ConfigFilePath
    """
    이 서비스의 인증서 파일(영역 사이 mTLS 의 서버·클라이언트 인증서, 사설 CA 가 발급). 필요한 컴포넌트: link_api, link_registry
    """
    OPENIT_TLS_PRIVATE_KEY_FILE: SecretFilePath
    """
    이 서비스의 TLS 개인키 파일. 필요한 컴포넌트: link_api
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


class ServingConfig(BaseModel):
    """
    어댑터 하나를 서빙할 때의 설정(어댑터와 함께 패키지에 들어간다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    constrained_decoding: ConstrainedDecoding
    """
    제약 디코딩 사용 여부
    """
    max_new_tokens: TokenLimit
    """
    만들 수 있는 최대 토큰 수
    """
    temperature: SamplingTemperature
    """
    무작위성
    """


class SlotAnswer(RootModel[YesNoAnswer | SlotNumber | OptionCode | SlotText | NoValue]):
    root: YesNoAnswer | SlotNumber | OptionCode | SlotText | NoValue
    """
    칸 하나에 담긴 값(예 또는 아니오, 수, 선택지 코드, 자유 글, 값 없음 중 하나)
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


class Sysctl(BaseModel):
    """
    컨테이너에 주입하는 sysctl 하나(이름과 값)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    name: SysctlName
    """
    sysctl 이름
    """
    value: SysctlValue
    """
    sysctl 값
    """


class TrainingLineage(BaseModel):
    """
    모델 패키지의 계보(어느 데이터로 어느 기반 모델에서 학습했는가)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    base_model: BaseModelName
    """
    기반 모델
    """
    dataset_version_id: DatasetVersionId
    """
    학습에 쓴 데이터셋 버전
    """
    training_run_ids: Annotated[list[TrainingRunId], Field(max_length=2)]
    """
    어댑터를 만든 학습 실행들
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


class AdapterEntry(BaseModel):
    """
    패키지 안의 어댑터 하나(가중치, 짝이 되는 시스템 프롬프트, 서빙 설정)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    role: AdapterRole
    """
    어댑터의 역할
    """
    serving_config: ServingConfig
    """
    서빙 설정
    """
    system_prompt: ModelPackageBlobDescriptor
    """
    이 어댑터와 짝이 되는 시스템 프롬프트 파일
    """
    weights: ModelPackageBlobDescriptor
    """
    어댑터 가중치 파일
    """


class ContainerInputs(BaseModel):
    """
    영역 밖에서 컨테이너에 주입하는 것 전체의 선언(실행 사용자, 환경 입력, 쓰는 경로, 추가 권한, sysctls, 시작 프로세스 명령줄)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    capabilities: Annotated[list[CapabilityName], Field(max_length=41)]
    """
    더하는 추가 권한들(기본은 없다)
    """
    env: Annotated[list[EnvDeclaration], Field(max_length=23)]
    """
    받는 환경 입력들
    """
    processes: Annotated[list[ProcessDeclaration], Field(max_length=12, min_length=1)]
    """
    시작 프로세스들(서비스의 진입점 하나와 잡마다 하나)
    """
    run_as_uid: RunAsUid
    """
    실행 사용자
    """
    sysctls: Annotated[list[Sysctl], Field(max_length=16)]
    """
    주입하는 sysctl 들
    """
    writable_paths: Annotated[list[WritablePath], Field(max_length=16)]
    """
    쓰는 경로들(루트 파일시스템은 읽기 전용이다)
    """


class EvaluationMetric(BaseModel):
    """
    평가 지표 하나의 값(임계치 없이 보고한다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    group: MetricGroupName | None = None
    """
    지표 묶음
    """
    name: MetricName
    """
    지표 이름
    """
    sample_count: SampleCount
    """
    표본 수
    """
    slice: MetricSlice | None = None
    """
    지표를 쪼갠 조각(전체이면 없다)
    """
    unit: MetricUnit
    """
    지표 값의 단위
    """
    value: MetricValue
    """
    지표 값
    """


class EvaluationReport(BaseModel):
    """
    모델 패키지 하나의 평가 보고서. model-lab 이 만들어 패키지와 함께 낸다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    created_at: Timestamp
    """
    보고서를 만든 때
    """
    dataset_version_id: DatasetVersionId
    """
    평가에 쓴 데이터셋 버전
    """
    metrics: Annotated[list[EvaluationMetric], Field(max_length=1000)]
    """
    지표들
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


class ModelPackageManifest(BaseModel):
    """
    모델 패키지의 목록표(OCI 아티팩트의 config 파일). 어댑터, 짝이 되는 시스템 프롬프트, 계보, 평가 보고서를 묶는다. 패키지의 식별자는 OCI 매니페스트의 digest 다(OciDigest)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    adapters: Annotated[list[AdapterEntry], Field(max_length=2, min_length=2)]
    """
    역할마다 하나씩의 어댑터
    """
    base_model: BaseModelName
    """
    기반 모델
    """
    created_at: Timestamp
    """
    패키지를 만든 때
    """
    evaluation: EvaluationReport
    """
    평가 보고서
    """
    lineage: TrainingLineage
    """
    계보
    """
    model_io_version: ModelIoVersion
    """
    어댑터가 학습한 모델 입출력 형식의 버전
    """
    model_runtime_version: SemanticVersion
    """
    학습과 평가에 쓴 model-runtime 라이브러리 버전. 서빙 설치본과 MAJOR.MINOR 가 같아야 적재한다
    """
    runtime_contract_version: RuntimeContractVersion
    """
    학습한 문항 은행과 칸 키의 정수 버전
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
