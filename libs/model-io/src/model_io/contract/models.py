# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
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


class AlphabeticalOrder(RootModel[Literal['alphabetical']]):
    root: Literal['alphabetical']
    """
    키를 문자 순(유니코드 코드 포인트 순)으로 정렬해 쓴다는 뜻
    """


class AskText(RootModel[str]):
    root: Annotated[str, Field(examples=['일주일에 며칠 하는지'], max_length=92)]
    """
    되묻거나 확인할 내용을 사람 말로 쓴 문장 틀
    """


class CurrentItemScope(StrEnum):
    """
    저장하는 값의 칸이 있어도 되는 자리의 종류
    """

    CURRENT_ITEM = 'CURRENT_ITEM'
    ITEM_RANGE_TO_NEXT_ITEM = 'ITEM_RANGE_TO_NEXT_ITEM'
    ITEM_FAMILY = 'ITEM_FAMILY'


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


class EnsureAscii(RootModel[Literal[False]]):
    root: Literal[False]
    """
    모델 입력 글자에서 비 ASCII 글자를 이스케이프하지 않는다는 뜻(항상 거짓)
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


class HoldText(RootModel[str]):
    root: Annotated[str, Field(examples=['일반담배 중 피운 기간'], max_length=36)]
    """
    HOLD 나 SKIP 으로 비워 두는 부분의 이름
    """


class InsertionOrder(RootModel[Literal['insertion']]):
    root: Literal['insertion']
    """
    키를 요청이 정한 순서대로 쓴다는 뜻(state_key_order)
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


class ModelInputSerialization(BaseModel):
    """
    모델 입력 글자의 직렬화 규칙(데이터). 입력 객체를 json.dumps(obj, ensure_ascii=False) 와 같은 글자로 쓴다(기본 구분자, 비 ASCII 는 그대로). JSON 객체에는 순서가 없으므로 state 의 칸 순서는 요청의 state_key_order 가 정한다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    a_nested_key_order: InsertionOrder
    """
    LoRA-A 입력의 state 안의 키 순서(요청이 정한 순서)
    """
    a_top_level_key_order: AlphabeticalOrder
    """
    LoRA-A 입력의 최상위 키 순서
    """
    b_key_order: AlphabeticalOrder
    """
    LoRA-B 입력의 모든 수준의 키 순서
    """
    ensure_ascii: EnsureAscii
    """
    비 ASCII 글자를 이스케이프할지(항상 거짓)
    """


class NextItemRuleKind(StrEnum):
    """
    행동마다 next_item 을 정하는 규칙의 종류
    """

    TARGET_ITEM = 'TARGET_ITEM'
    ASKED_ITEM = 'ASKED_ITEM'
    SEQUENCE_AFTER_SAVED = 'SEQUENCE_AFTER_SAVED'


class NoValue(RootModel[None]):
    root: None
    """
    값이 없음을 뜻하는 null(모름·거절·빠짐 등 저장할 값이 없는 칸)
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


class SampleCount(RootModel[int]):
    root: Annotated[int, Field(examples=[400], ge=0, le=2147483647)]
    """
    지표를 계산한 표본의 수
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


class ViolationCode(StrEnum):
    """
    model-runtime 의 출력 검증이 낸 위반의 코드이고 semantic_violation_rate 가 센다. 코드는 ActionExtractionRules 와 ActionExtraction 스키마의 합격 조건에서만 나오고 조건 하나가 코드 하나다. 코드를 내는 검사는 model-runtime 의 출력 검증 한 곳이다(R7). 위반율은 값 고쳐 쓰기(D115) 전의 모델 출력으로 센다
    """

    OUTPUT_SCHEMA = 'OUTPUT_SCHEMA'
    SAVE_RULE = 'SAVE_RULE'
    TARGET_NOT_IN_VALUES = 'TARGET_NOT_IN_VALUES'
    NEXT_ITEM_MISMATCH = 'NEXT_ITEM_MISMATCH'
    UNKNOWN_ITEM = 'UNKNOWN_ITEM'
    UNKNOWN_SLOT = 'UNKNOWN_SLOT'
    VALUE_TYPE_MISMATCH = 'VALUE_TYPE_MISMATCH'
    VALUE_NOT_IN_OPTIONS = 'VALUE_NOT_IN_OPTIONS'
    VALUE_OUT_OF_RANGE = 'VALUE_OUT_OF_RANGE'
    OUT_OF_CURRENT_ITEM = 'OUT_OF_CURRENT_ITEM'


class YesNoAnswer(RootModel[bool]):
    root: bool
    """
    예 또는 아니오 칸의 값(예이면 참)
    """


class ConditionValue(RootModel[YesNoAnswer | SlotNumber | OptionCode]):
    root: YesNoAnswer | SlotNumber | OptionCode
    """
    건너뛰기 조건이 비교하는 값(예 또는 아니오, 수, 선택지 코드 중 하나)
    """


class CurrentItemRule(BaseModel):
    """
    현재 문항 규칙(데이터). 저장하는 값(save 가 참)의 칸은 allowed_scopes 가 허용한 자리 안에 있어야 한다. exempt_actions 의 action 이거나 exempt_statuses 의 status 인 값은 이 검사에서 뺀다(정정). 어기면 OUT_OF_CURRENT_ITEM 이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    allowed_scopes: Annotated[list[CurrentItemScope], Field(max_length=3, min_length=1)]
    """
    저장하는 칸이 있어도 되는 자리들(현재 문항, 현재 문항부터 next_item 까지 순서 구간, 같은 문항 계열)
    """
    exempt_actions: Annotated[list[ExtractionAction], Field(max_length=7)]
    """
    이 검사를 면제하는 action 들(CORRECT)
    """
    exempt_statuses: Annotated[list[ValueStatus], Field(max_length=7)]
    """
    이 검사를 면제하는 값의 status 들(CORRECTION)
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


class MetricName(RootModel[RequiredMetricName | ExtraMetricName]):
    root: RequiredMetricName | ExtraMetricName
    """
    평가 지표의 이름. 필수 지표(RequiredMetricName) 또는 자유 이름
    """


class NextItemRule(BaseModel):
    """
    행동 하나의 next_item 규칙
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: ExtractionAction
    """
    규칙이 적용되는 행동
    """
    rule: NextItemRuleKind
    """
    next_item 을 정하는 규칙
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


class ActionExtractionRules(BaseModel):
    """
    LoRA-A 출력의 합격 조건 명세(데이터). model-runtime 의 출력 검증이 한 번 검사하고 받는 쪽은 다시 검증하지 않는다(R7). 조건 하나가 위반 코드(ViolationCode) 하나다. 출력 형식 조건은 ActionExtraction 스키마(OUTPUT_SCHEMA), 이 명세는 저장 규칙(SAVE_RULE), targets(TARGET_NOT_IN_VALUES), next_item(NEXT_ITEM_MISMATCH), 현재 문항(OUT_OF_CURRENT_ITEM)을 정한다. 문항·칸·자료형·선택지·범위의 조건(UNKNOWN_ITEM, UNKNOWN_SLOT, VALUE_TYPE_MISMATCH, VALUE_NOT_IN_OPTIONS, VALUE_OUT_OF_RANGE)은 요청의 순서표(QuestionFlowTable)와 칸 규격(QuestionFieldSpec)이 정한다. 재질문 단계(문진 끝에 한도로 비운 문항을 다시 묻는 단계)에서는 서비스가 정한 순서가 next_item 보증보다 우선한다. 조건 검사기는 libs/model-io 에 두고 model-lab 의 의미 위반율 평가도 같은 검사기를 쓴다(D97). 위반율은 값 고쳐 쓰기(D115) 전의 모델 출력으로 센다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    actions_with_targets: Annotated[list[ExtractionAction], Field(max_length=7)]
    """
    targets 가 values 의 키의 부분집합이어야 하는 행동들(REASK, CONFIRM, HOLD, SKIP)(TARGET_NOT_IN_VALUES)
    """
    current_item_rule: CurrentItemRule
    """
    저장하는 값의 칸이 있어도 되는 자리와 정정 예외(OUT_OF_CURRENT_ITEM)
    """
    next_item_rules: Annotated[list[NextItemRule], Field(max_length=7)]
    """
    행동마다 next_item 을 정하는 규칙(NEXT_ITEM_MISMATCH)
    """
    null_value_statuses: Annotated[list[ValueStatus], Field(max_length=7)]
    """
    value 가 null 인 상태들(MISSING, UNCLEAR, UNKNOWN, REJECTED)이고 나머지 상태는 value 가 있다(SAVE_RULE)
    """
    saved_statuses: Annotated[list[ValueStatus], Field(max_length=7)]
    """
    save 가 참인 상태들(ANSWERED, CORRECTION)이고 나머지 상태는 save 가 거짓이다(SAVE_RULE)
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
