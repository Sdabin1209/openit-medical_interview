# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
)


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


class AskText(RootModel[str]):
    root: Annotated[str, Field(examples=['일주일에 며칠 하는지'], max_length=92)]
    """
    되묻거나 확인할 내용을 사람 말로 쓴 문장 틀
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


class ConstrainedDecoding(RootModel[bool]):
    root: bool
    """
    출력을 스키마에 맞게 제약하며 만드는지(참이면 제약 디코딩)
    """


class CurrentQuestionText(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                '안녕하세요. 먼저 질환부터 여쭤볼게요. 뇌졸중으로 진단받으셨거나 현재 약물 치료 중이신가요?'
            ],
            max_length=344,
        ),
    ]
    """
    상담원이 방금 환자에게 한 말(화면에 보인 직전 질문). 환자의 말은 이 질문에 대한 답으로 읽는다
    """


class CurrentValueText(RootModel[str]):
    root: Annotated[str, Field(examples=['일주일에 5일'], max_length=30)]
    """
    CONFIRM 에서 이번에 말한 값을 사람 말로 쓴 글
    """


class DatasetVersionId(RootModel[UUID]):
    root: Annotated[UUID, Field(examples=['3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90'])]
    """
    게시된 데이터셋 한 버전의 식별자
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


class HoldText(RootModel[str]):
    root: Annotated[str, Field(examples=['일반담배 중 피운 기간'], max_length=36)]
    """
    HOLD 나 SKIP 으로 비워 두는 부분의 이름
    """


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


class JsonPointer(RootModel[str]):
    root: Annotated[str, Field(examples=['/input/user_utterance'], max_length=8000)]
    """
    요청 본문 안에서 잘못된 값의 위치(JSON 포인터)
    """


class KnownText(RootModel[str]):
    root: Annotated[str, Field(examples=['진단 받음, 지금 약 먹음'], max_length=124)]
    """
    이번 턴에 정해진 값을 사람 말로 되짚은 문장들(쉼표로 이은 글)
    """


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


class NoValue(RootModel[None]):
    root: None
    """
    값이 없음을 뜻하는 null(모름·거절·빠짐 등 저장할 값이 없는 칸)
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


class PreviousValueText(RootModel[str]):
    root: Annotated[str, Field(examples=['일주일에 3일'], max_length=30)]
    """
    CONFIRM 에서 이전에 저장된 값을 사람 말로 쓴 글
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
        str, Field(examples=['makgeolli'], max_length=18, pattern='^[a-z]+$')
    ]
    """
    같은 칸이 여러 번 쓰일 때 구분하는 반복 키(술 종류: soju, beer, spirits, makgeolli, wine)
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


class StateKeyOrder(RootModel[list[SlotRefString]]):
    """
    state 의 칸 키를 모델 입력 글자에서 놓을 순서. JSON 객체에는 순서가 없으므로(RFC 8259 4) 순서를 따로 전한다
    """

    root: Annotated[list[SlotRefString], Field(max_length=18)]
    """
    state 의 칸 키를 모델 입력 글자에서 놓을 순서. JSON 객체에는 순서가 없으므로(RFC 8259 4) 순서를 따로 전한다
    """


class StateStatus(StrEnum):
    """
    LoRA-A 입력 state 안의 칸 하나의 상태
    """

    ANSWERED = 'ANSWERED'
    MISSING = 'MISSING'
    UNCLEAR = 'UNCLEAR'


class Timestamp(RootModel[AwareDatetime]):
    root: Annotated[AwareDatetime, Field(examples=['2026-11-10T09:30:00+09:00'])]
    """
    일이 일어난 때. UTC 오프셋을 포함한 RFC 3339 날짜-시각
    """


class TokenLimit(RootModel[int]):
    root: Annotated[int, Field(examples=[512], ge=1, le=32768)]
    """
    한 번에 만들 수 있는 최대 토큰 수
    """


class TopicText(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지'], max_length=88
        ),
    ]
    """
    지금 다루는 문항을 사람 말로 풀어 쓴 설명(예를 들어 뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지)
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


class YesNoAnswer(RootModel[bool]):
    root: bool
    """
    예 또는 아니오 칸의 값(예이면 참)
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
    반복 키가 있는 칸이면 그 키들(없으면 빈 키 하나만 쓴다)
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


class ResponseNext(BaseModel):
    """
    응답 뒤에 가는 자리(종류, 문항, 그 질문 문장)
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
    그 문항의 질문 문장(END 에는 없다)
    """
    type: ResponseNextType
    """
    자리의 종류
    """


class ResponseRequest(BaseModel):
    """
    LoRA-B 의 입력(모델 입출력 v2). 어떤 절차로 어떤 문장을 만들지와 다음에 갈 자리를 알려 주는 모든 것
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: ResponseAction
    """
    문장을 만들 절차
    """
    ask: AskText | None = None
    """
    REASK 와 CONFIRM 에서 되묻는 내용
    """
    current: CurrentValueText | None = None
    """
    CONFIRM 에서 이번에 말한 값
    """
    hold: HoldText | None = None
    """
    HOLD 와 SKIP 에서 비워 두는 부분
    """
    known: KnownText | None = None
    """
    이번 턴에 정해진 값의 설명(START 에는 없다)
    """
    next: ResponseNext
    """
    응답 뒤에 가는 자리
    """
    note: OutOfSchemaNote | None = None
    """
    REDIRECT 의 OUT_OF_SCHEMA 에서 환자가 말한 문진표 밖 건강 이야기
    """
    previous: PreviousValueText | None = None
    """
    CONFIRM 에서 이전에 저장된 값
    """
    reason: ActionReason | None = None
    """
    그 절차의 사유
    """
    topic: TopicText
    """
    지금 다루는 문항의 설명
    """
    user_utterance: UtteranceText | None = None
    """
    환자의 이번 말(START 에는 없다)
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


class StateEntry(BaseModel):
    """
    state 안의 칸 하나(저장된 값과 상태)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    status: StateStatus
    """
    칸의 상태
    """
    value: SlotAnswer
    """
    저장된 값(다시 물은 칸이면 null)
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


class CollectedState(
    RootModel[
        dict[
            Annotated[
                str,
                StringConstraints(
                    pattern=r'^[A-Za-z0-9_.]+(\[[a-z]+\])?\.[a-z][a-z0-9_]*$'
                ),
            ],
            StateEntry,
        ]
    ]
):
    root: dict[
        Annotated[
            str,
            StringConstraints(
                pattern=r'^[A-Za-z0-9_.]+(\[[a-z]+\])?\.[a-z][a-z0-9_]*$'
            ),
        ],
        StateEntry,
    ]
    """
    칸을 가리키는 키(문항.칸, 술은 문항[술코드].칸)에서 그 칸의 값과 상태로 가는 표. 항목의 순서가 의미를 가진다(모델 입력 글자는 학습 데이터와 같게 만든다)
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
    추론 서버에 LoRA-B 응답 문장 생성을 요청하는 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    input: ResponseRequest
    """
    모델에 들어가는 입력
    """
    runtime_contract_version: RuntimeContractVersion
    """
    요청하는 쪽이 쓰는 문항 은행 버전(활성 문항 세트의 값). 적재한 모델 패키지가 학습한 값과 다르면 QUESTION_BANK_VERSION_MISMATCH 로 거절한다
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


class ActionExtractionInput(BaseModel):
    """
    LoRA-A 의 입력. 지금 묻는 문항과 상담원이 한 말과 환자의 말과 저장된 값들
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    current_question: CurrentQuestionText
    """
    상담원이 방금 한 말
    """
    question_id: QuestionItemId
    """
    지금 묻고 있는 문항
    """
    state: CollectedState
    """
    지금 문항과 직전 문항과 참조 문항의 저장 값들
    """
    user_utterance: UtteranceText
    """
    환자의 이번 말
    """


class ExtractionRequest(BaseModel):
    """
    추론 서버에 LoRA-A 추출을 요청하는 본문
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    fields: QuestionFieldSpecs
    """
    출력 값을 보증하는 칸 규격들
    """
    flow: QuestionFlowTable
    """
    출력의 다음 문항을 보증하는 순서표
    """
    input: ActionExtractionInput
    """
    모델에 들어가는 입력
    """
    runtime_contract_version: RuntimeContractVersion
    """
    요청하는 쪽이 쓰는 문항 은행 버전(활성 문항 세트의 값). 적재한 모델 패키지가 학습한 값과 다르면 QUESTION_BANK_VERSION_MISMATCH 로 거절한다
    """
    state_key_order: StateKeyOrder
    """
    input.state 의 칸 키를 모델 입력 글자에서 놓을 순서
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
