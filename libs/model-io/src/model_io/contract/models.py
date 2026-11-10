# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


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


class CurrentItemScope(StrEnum):
    """
    저장하는 값의 칸이 있어도 되는 자리의 종류
    """

    CURRENT_ITEM = 'CURRENT_ITEM'
    ITEM_RANGE_TO_NEXT_ITEM = 'ITEM_RANGE_TO_NEXT_ITEM'
    ITEM_FAMILY = 'ITEM_FAMILY'


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


class InsertionOrder(RootModel[Literal['insertion']]):
    root: Literal['insertion']
    """
    키를 요청의 slots 배열이 정한 순서대로 쓴다는 뜻
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


class NextItemRuleKind(StrEnum):
    """
    행동마다 next_item 을 정하는 규칙의 종류. 행동과의 짝은 REASK·CONFIRM 이 TARGET_ITEM, REDIRECT 가 ASKED_ITEM, 그 밖(NEXT·CORRECT·HOLD·SKIP)이 SEQUENCE_AFTER_SAVED 다
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


class StateEntryKeyOrderEnum(StrEnum):
    value = 'value'
    status = 'status'


class StateEntryKeyOrder(RootModel[list[StateEntryKeyOrderEnum]]):
    """
    LoRA-A 입력 state 의 항목 하나({value, status}) 안의 키 순서(value 다음 status)
    """

    root: Annotated[list[StateEntryKeyOrderEnum], Field(max_length=2, min_length=2)]
    """
    LoRA-A 입력 state 의 항목 하나({value, status}) 안의 키 순서(value 다음 status)
    """


class StoredSlotStatus(StrEnum):
    """
    서비스가 저장하고 있는 칸 하나의 상태
    """

    ANSWERED = 'ANSWERED'
    MISSING = 'MISSING'
    UNCLEAR = 'UNCLEAR'


class Timestamp(RootModel[AwareDatetime]):
    root: Annotated[AwareDatetime, Field(examples=['2026-11-10T09:30:00+09:00'])]
    """
    일이 일어난 때. UTC 오프셋을 포함한 RFC 3339 날짜-시각
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


class ModelInputSerialization(BaseModel):
    """
    모델 입력 글자의 직렬화 규칙(데이터). model-runtime 이 데이터셋 정본(labels.py)으로 만든 입력 객체를 json.dumps(obj, ensure_ascii=False) 와 같은 글자로 쓴다(기본 구분자, 비 ASCII 는 그대로). JSON 객체에는 순서가 없으므로 정해야 한다. 최상위 키는 문자 순, state 의 칸 순서는 요청 slots 배열의 순서, state 항목 안의 키는 value 다음 status(labels.py a_state), B 는 모든 수준을 문자 순으로 쓴다. state 는 model-runtime 이 요청의 저장된 칸 값(slots, StoredSlots)에서 만든다. 어느 문항의 칸을 넣을지는 참조 원천 문항을 taxonomy.py 의 REF_SOURCE 로 고르고 칸 묶음의 순서는 prev_state.py 를 따른다(표와 규칙은 계약에 복사하지 않고 contracts/inputs 의 정본 파일을 가리킨다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    a_nested_key_order: InsertionOrder
    """
    LoRA-A 입력의 state 안의 칸 키 순서(요청 slots 배열의 순서)
    """
    a_state_entry_key_order: StateEntryKeyOrder
    """
    LoRA-A 입력의 state 항목 하나 안의 키 순서(value, status)
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


class ActionExtractionRules(BaseModel):
    """
    LoRA-A 출력의 합격 조건 명세(데이터). model-runtime 의 출력 검증이 한 번 검사하고 받는 쪽은 다시 검증하지 않는다(R7). 조건 하나가 위반 코드(ViolationCode) 하나다. 출력 형식 조건은 ActionExtraction 스키마(OUTPUT_SCHEMA), 이 명세는 저장 규칙(SAVE_RULE), targets(TARGET_NOT_IN_VALUES), next_item(NEXT_ITEM_MISMATCH. 기준 문항과 건너뛰기는 NextItemRuleKind 가 labels.py a_target·next_after 대로 정한다), 현재 문항(OUT_OF_CURRENT_ITEM)을 정한다. 문항·칸·자료형·선택지·범위의 조건(UNKNOWN_ITEM, UNKNOWN_SLOT, VALUE_TYPE_MISMATCH, VALUE_NOT_IN_OPTIONS, VALUE_OUT_OF_RANGE)은 요청의 순서표(QuestionFlowTable)와 칸 규격(QuestionFieldSpec)이 정한다. 재질문 단계(문진 끝에 한도로 비운 문항을 다시 묻는 단계)에서는 서비스가 정한 순서가 next_item 보증보다 우선한다. 조건 검사기는 libs/model-io 에 두고 model-lab 의 의미 위반율 평가도 같은 검사기를 쓴다(D97). 위반율은 값 고쳐 쓰기(D115) 전의 모델 출력으로 센다
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
    행동마다 next_item 을 정하는 규칙(NEXT_ITEM_MISMATCH). 종류별 뜻은 NextItemRuleKind 의 설명이고 기준 문항은 labels.py a_target 을 따른다
    """
    null_value_statuses: Annotated[list[ValueStatus], Field(max_length=7)]
    """
    value 가 null 인 상태들(MISSING, UNCLEAR, UNKNOWN, REJECTED)이고 나머지 상태는 value 가 있다(SAVE_RULE)
    """
    saved_statuses: Annotated[list[ValueStatus], Field(max_length=7)]
    """
    save 가 참인 상태들(ANSWERED, CORRECTION)이고 나머지 상태는 save 가 거짓이다(SAVE_RULE)
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
