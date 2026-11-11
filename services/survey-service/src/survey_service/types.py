"""영역 안 컴포넌트 사이를 오가는 값과 컴포넌트가 기대는 저장소 약속(ADR 0003, 구조 규칙 5).

계약 값(contract/models.py)은 영역 사이 값이고, 여기 값은 이 영역 안에서만 돈다. 칸마다 뜻을 적는다.
컴포넌트는 서로를 모르므로 둘 이상이 쓰는 값은 모두 여기에 한 번만 정의한다(D117).
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel

from survey_service.contract.models import (
    ActionExtraction,
    ActiveQuestionSet,
    AlertKind,
    BlankReason,
    CaseReview,
    ExtractionRequest,
    ExtractionResult,
    FailureKind,
    PauseReason,
    PushSubscription,
    ResponseGenerationRequest,
    ResponseResult,
    ReviewStatus,
    SessionStatus,
    TurnFailureReason,
)

# 값은 JSON 으로 저장·교환하는 칸 값 하나(예 아니오, 수, 선택지 코드, 자유 글, 값 없음)다
SlotValue = bool | int | float | str | None

_SLOT_REF = re.compile(r"^(?P<item>[A-Za-z0-9_.]+)(?:\[(?P<repeat>[a-z]+)\])?\.(?P<field>[a-z][a-z0-9_]*)$")


def unwrap(value: object) -> SlotValue:
    """계약의 RootModel 껍질(SlotAnswer, ConditionValue 등)을 벗겨 값 자체를 낸다."""
    while isinstance(value, RootModel):
        value = cast("RootModel[object]", value).root
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise TypeError(f"칸 값이 아니다: {type(value).__name__}")


def split_slot(ref: str) -> tuple[str, str | None, str] | None:
    """칸 가리킴(SlotRefString)을 (문항, 반복 키, 칸 이름)으로 나눈다. 모양이 틀리면 None. 컴포넌트 둘 이상이 쓴다."""
    match = _SLOT_REF.match(ref)
    if match is None:
        return None
    return match["item"], match["repeat"], match["field"]


class _Value(BaseModel):
    """영역 안 값의 바탕. 모르는 칸을 받지 않고 바꿀 수 없다(frozen)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------- 신원


class PrincipalKind(StrEnum):
    """호출자의 종류. 신원은 platform 이 넘긴 것만 쓴다(사람 OIDC, 기기 mTLS, 기계 토큰)."""

    HUMAN = "HUMAN"
    DEVICE = "DEVICE"
    MACHINE = "MACHINE"


class Principal(_Value):
    """인증을 마친 호출자. 본문의 신원은 쓰지 않는다."""

    kind: PrincipalKind = Field(description="호출자의 종류")
    subject: str = Field(
        min_length=1, max_length=255, description="사람은 OIDC sub, 기기는 기기 ID, 기계는 호출자 이름"
    )
    roles: frozenset[str] = Field(description="사람의 UserRole 또는 기계의 MachineRole 값들(기기는 비어 있다)")


# ---------------------------------------------------------------- 문항 세트


class StoredQuestionSet(_Value):
    """저장한 문항 세트 버전 하나(한 번 저장하면 바뀌지 않는다). 내용은 계약의 QuestionSetContent 의 JSON 이다."""

    question_set_version_id: UUID = Field(description="버전 식별자")
    questionnaire_id: str = Field(description="문진표 식별자")
    version_number: int = Field(ge=1, description="같은 문진표 안의 순번")
    runtime_contract_version: int = Field(ge=1, description="문항 은행과 칸 키의 정수 버전")
    content: dict[str, object] = Field(description="QuestionSetContent 의 JSON")
    content_hash: str = Field(description="내용의 SHA-256(소문자 16진수 64자)")
    uploaded_by: str = Field(description="올린 사람(OIDC sub)")
    created_at: datetime = Field(description="저장한 때")
    is_active: bool = Field(
        default=False, description="그 문진표의 지금 활성 버전인지(저장한 내용이 아니라 활성화에 따라 바뀐다)"
    )


# ---------------------------------------------------------------- 시작 코드


class StartCodeRecord(_Value):
    """발급한 시작 코드 하나."""

    code: str = Field(pattern=r"^[0-9]{6}$", description="6자리 숫자")
    subject_ref: str = Field(description="코드에 묶인 대상자 참조값")
    questionnaire_id: str | None = Field(description="코드에 묶인 문진표(없으면 없다)")
    issued_by: str = Field(description="발급한 직원(OIDC sub)")
    issued_at: datetime = Field(description="발급한 때")
    expires_at: datetime = Field(description="이때가 지나면 쓸 수 없다")
    used_by_device: str | None = Field(default=None, description="처음 쓴 기기(쓰지 않았으면 없다)")
    used_session_id: UUID | None = Field(default=None, description="그 코드로 시작한 세션")


class StartCodeVerdict(StrEnum):
    """시작 코드를 이 기기가 쓸 수 있는지에 대한 판정."""

    OK = "OK"
    REPLAY = "REPLAY"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    USED = "USED"


# ---------------------------------------------------------------- 세션


class AnswerRecord(_Value):
    """세션에 모인 칸 하나의 값. status 는 모델 입력 state 의 상태(ANSWERED, MISSING, UNCLEAR)다."""

    key: str = Field(description="칸(SlotRefString)")
    value: SlotValue = Field(description="저장한 값(다시 물을 칸이면 null)")
    precision: Literal["exact", "approximate", "unspecified"] = Field(description="값의 정확도")
    status: Literal["ANSWERED", "MISSING", "UNCLEAR"] = Field(description="칸의 상태")


class BlankRecord(_Value):
    """결과에서 비어 있는 칸 하나와 그 원인."""

    item_id: str = Field(description="비어 있는 문항")
    key: str | None = Field(default=None, description="비어 있는 칸(문항 전체가 비었으면 없다)")
    reason: BlankReason = Field(description="비어 있는 원인")


class SessionRecord(_Value):
    """문진 세션 하나의 상태. 바꿀 때는 model_copy 로 새 값을 만든다."""

    session_id: UUID = Field(description="세션 식별자")
    device_id: str = Field(description="시작한 기기. 이 기기만 세션에 닿는다(D88 U8)")
    subject_ref: str = Field(description="대상자 참조값(키오스크에는 주지 않는다)")
    questionnaire_id: str = Field(description="문진표")
    question_set_version_id: UUID = Field(description="시작할 때의 문항 세트 버전(진행 중 바뀌지 않는다)")
    runtime_contract_version: int = Field(ge=1, description="그 버전의 문항 은행 버전")
    status: SessionStatus = Field(description="세션 상태")
    pause_reason: PauseReason | None = Field(default=None, description="멈춘 까닭")
    current_item_id: str | None = Field(description="지금 묻는 문항(끝났으면 없다)")
    previous_item_id: str | None = Field(default=None, description="바로 앞에 물은 문항(모델 입력 state 에 쓴다)")
    last_assistant_text: str = Field(description="화면에 보인 직전 말(모델 입력의 current_question)")
    answers: dict[str, AnswerRecord] = Field(
        default_factory=dict, description="칸 키에서 값으로 가는 표(넣은 순서가 의미를 가진다)"
    )
    blanks: tuple[BlankRecord, ...] = Field(default=(), description="비어 있는 칸들과 원인")
    asked_items: tuple[str, ...] = Field(
        default=(), description="지금까지 물은 문항들(묻지 못한 문항을 결과에서 가린다)"
    )
    reask_count: int = Field(default=0, ge=0, description="지금 문항에서 이어진 REASK·CONFIRM 횟수")
    resume_pending: bool = Field(default=False, description="정지가 풀린 뒤 다음 발화 턴 전이라 resume_text 를 줄 때")
    failed_turn_ids: tuple[UUID, ...] = Field(
        default=(),
        description="턴이 기록되거나 정지가 풀린 뒤로 실패한 서로 다른 turn_id 들(연속 실패 수는 이 길이)",
    )
    started_at: datetime = Field(description="시작한 때")
    last_activity_at: datetime = Field(description="환자가 마지막으로 움직인 때(유휴 만료의 기준)")
    ended_at: datetime | None = Field(default=None, description="끝난 때")
    model_io_version: str | None = Field(
        default=None, description="시작할 때 활성이던 모델 입출력 버전(알 수 없으면 없다)"
    )


class SessionTransition(_Value):
    """추출 결과를 세션에 반영한 결과."""

    session: SessionRecord = Field(description="반영한 뒤의 세션")
    next_item_id: str = Field(description="다음 자리(문항 식별자 또는 END)")
    limit_skip: bool = Field(
        description="되묻기 한도에 닿아 서비스가 문항을 건너뛰었는지(이때 모델 응답을 쓰지 않는다)"
    )


class TurnOutcome(StrEnum):
    """턴 기록의 처리 상태. PROCESSING 은 처리 중, DONE 은 끝, FAILED 는 값을 만들지 못했다."""

    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class TurnRecordData(_Value):
    """턴 하나의 기록(trace 가 저장). 같은 (session_id, turn_id) 는 한 건이다."""

    session_id: UUID = Field(description="세션")
    turn_id: UUID = Field(description="턴 식별자(클라이언트가 만든다)")
    questionnaire_id: str = Field(description="문진표")
    item_id: str = Field(description="이 턴에 묻던 문항")
    outcome: TurnOutcome = Field(description="처리 상태")
    utterance: str = Field(max_length=300, description="환자 발화 원문(보존 180일, 검토자 역할에만 나간다)")
    extract_output: ActionExtraction | None = Field(default=None, description="추출 출력")
    response_text: str | None = Field(default=None, description="화면에 보인 문장")
    failure_signal: TurnFailureReason | None = Field(default=None, description="값을 만들지 못했을 때의 신호")
    reask_limit_hit: bool = Field(default=False, description="서비스가 되묻기 한도로 문항을 건너뛴 턴")
    response: dict[str, object] | None = Field(
        default=None, description="돌려준 TurnResponse 의 JSON(같은 turn_id 의 재전송에 그대로 준다)"
    )
    package_digest: str | None = Field(default=None, description="추출을 처리한 모델 패키지")
    started_at: datetime = Field(description="처리를 시작한 때")
    finished_at: datetime | None = Field(default=None, description="처리를 마친 때")


# ---------------------------------------------------------------- 알림


class AlertRecord(_Value):
    """직원·의사 알림 하나."""

    alert_id: UUID = Field(description="알림 식별자")
    kind: AlertKind = Field(description="알림 종류")
    session_id: UUID = Field(description="알림이 가리키는 세션")
    device_id: str | None = Field(description="찾아갈 기기(결과 알림에는 없다)")
    questionnaire_title: str | None = Field(default=None, description="문진표 제목")
    dedupe_key: str | None = Field(
        default=None, description="같은 사건을 한 번만 처리하는 키(위험 신호는 세션·분류·감지 시각)"
    )
    raised_at: datetime = Field(description="생긴 때")
    resolved_at: datetime | None = Field(default=None, description="풀리거나 확인된 때")
    resolved_by: str | None = Field(default=None, description="푼 사람(OIDC sub)")


class AlertEventRecord(_Value):
    """알림 스트림(SSE)의 이벤트 하나. sequence 가 이벤트 id 다."""

    sequence: int = Field(ge=0, description="순번")
    event: Literal["alert", "resolved"] = Field(description="이벤트 이름")
    alert: AlertRecord = Field(description="이벤트가 가리키는 알림")


# ---------------------------------------------------------------- 실패 사례


class FailureCaseData(_Value):
    """실패 사례의 최신 검토 버전. 불변 값이고 검토가 바뀌면 case_version 이 오른다."""

    case_id: UUID = Field(description="사례 식별자")
    case_version: int = Field(ge=1, description="검토 버전")
    kind: FailureKind = Field(description="찾아낸 규칙")
    session_id: UUID = Field(description="사례가 난 세션")
    turn_id: UUID = Field(description="사례가 난 턴")
    item_id: str = Field(description="실패가 난 문항")
    questionnaire_id: str = Field(description="문진표")
    model_output: ActionExtraction | None = Field(description="모델이 낸 출력")
    utterance: str | None = Field(description="검토용 원문(보존 기간이 지나면 지워진다)")
    review_status: ReviewStatus = Field(description="검토 상태")
    expected: ActionExtraction | None = Field(default=None, description="확정한 기대 출력")
    reviewed_input: str | None = Field(default=None, description="고쳐 쓴 발화")
    reviewed_by: str | None = Field(default=None, description="검토한 사람(OIDC sub)")
    reviewed_at: datetime | None = Field(default=None, description="검토한 때")
    failure_signal: TurnFailureReason | None = Field(default=None, description="턴의 실패 신호")
    response_text: str | None = Field(default=None, description="그 턴에 화면에 보인 문장")
    created_at: datetime = Field(description="사례를 만든 때")
    occurred_at: datetime = Field(description="턴이 끝난 때")


class ReviewVerdict(StrEnum):
    """검토 게시의 판정."""

    UNCHANGED = "UNCHANGED"
    NEW_VERSION = "NEW_VERSION"
    VERSION_MISMATCH = "VERSION_MISMATCH"


class ReviewDecision(_Value):
    """검토 게시를 가른 결과. NEW_VERSION 이면 next 가 저장할 새 버전이다."""

    verdict: ReviewVerdict = Field(description="판정")
    next: FailureCaseData | None = Field(default=None, description="저장할 새 버전(NEW_VERSION 일 때만)")


# ---------------------------------------------------------------- 모델 호출 결과


class ModelCallFailure(StrEnum):
    """이웃 model-runtime 호출이 값을 내지 못한 까닭. 어느 것이든 턴은 실패 신호로 끝난다(D75)."""

    UNAVAILABLE = "UNAVAILABLE"
    DEADLINE = "DEADLINE"


class ModelCallError(Exception):
    """모델 호출 실패. 링크 컴포넌트가 던지고 턴 처리가 신호로 바꾼다."""

    def __init__(self, failure: ModelCallFailure) -> None:
        super().__init__(failure.value)
        self.failure = failure


class StaffHelpText(StrEnum):
    """서비스의 고정 문장(모델이 쓰지 않는다, v7-flow-resolutions). 값은 환자에게 그대로 보인다."""

    # 왜 연속 실패 한도로 건너뛸 때도 이 문장: 계약 TurnFailureLimit 이 되묻기 한도와 같다고 정했다
    REASK_LIMIT_SKIP = "정확히 알아듣지 못해서 이 질문은 건너뛸게요."
    FINISHED = "문진이 모두 끝났어요. 답해 주셔서 감사합니다."
    RESUMED = "문진을 이어서 할게요."


# ---------------------------------------------------------------- 저장소 약속(store 가 구현, link 가 쓴다)


class Page[T](_Value):
    """커서 쪽 하나."""

    items: tuple[T, ...] = Field(description="항목들")
    next_cursor: str | None = Field(default=None, description="다음 쪽 커서(마지막이면 없다)")


class InvalidCursorError(Exception):
    """쪽 나누기 커서가 서버가 만든 값이 아니다(400)."""


class DuplicateError(Exception):
    """유일해야 하는 값이 겹쳤다(시작 코드 6자리 충돌처럼 다시 만들면 되는 경우)."""


class Tx(Protocol):
    """한 트랜잭션 안의 저장·조회(store 가 구현). 링크 컴포넌트는 이 약속만 안다."""

    # 문항 세트
    async def save_question_set(self, value: StoredQuestionSet, idempotency_key: str | None) -> StoredQuestionSet: ...
    async def get_question_set(self, question_set_version_id: UUID) -> StoredQuestionSet | None: ...
    async def list_question_sets(
        self, questionnaire_id: str | None, limit: int, cursor: str | None
    ) -> Page[StoredQuestionSet]: ...
    async def activate_question_set(self, value: StoredQuestionSet, by: str, at: datetime) -> ActiveQuestionSet: ...
    async def active_question_set(self, questionnaire_id: str) -> StoredQuestionSet | None: ...
    async def list_active_questionnaires(self) -> tuple[StoredQuestionSet, ...]: ...
    # 시작 코드
    async def issue_start_code(self, value: StartCodeRecord, idempotency_key: str) -> StartCodeRecord: ...
    async def get_start_code(self, code: str, for_update: bool = False) -> StartCodeRecord | None: ...
    async def mark_start_code_used(self, code: str, device_id: str, session_id: UUID) -> None: ...
    async def record_start_failure(self, device_id: str, at: datetime) -> None: ...
    async def count_start_failures(self, device_id: str, since: datetime) -> int: ...
    async def begin_start_attempt(self, device_id: str, code: str, at: datetime, stale_before: datetime) -> bool: ...
    async def end_start_attempt(self, device_id: str, code: str) -> None: ...
    # 세션
    async def create_session(self, value: SessionRecord) -> None: ...
    async def get_session(self, session_id: UUID, for_update: bool = False) -> SessionRecord | None: ...
    async def save_session(self, value: SessionRecord) -> None: ...
    # 턴 기록(trace)
    async def begin_turn(self, value: TurnRecordData, stale_before: datetime) -> TurnRecordData | None: ...
    async def get_turn(self, session_id: UUID, turn_id: UUID) -> TurnRecordData | None: ...
    async def finish_turn(self, value: TurnRecordData) -> None: ...
    async def log_event(self, event: str, session_id: UUID | None, at: datetime, detail: dict[str, object]) -> None: ...
    # 알림
    async def create_alert(self, value: AlertRecord) -> tuple[AlertRecord, bool]: ...
    async def get_alert(self, alert_id: UUID) -> AlertRecord | None: ...
    async def find_alert(self, dedupe_key: str) -> AlertRecord | None: ...
    async def open_alert(self, session_id: UUID, kind: AlertKind) -> AlertRecord | None: ...
    async def resolve_alerts(
        self, session_id: UUID, kinds: tuple[AlertKind, ...], by: str, at: datetime
    ) -> tuple[AlertRecord, ...]: ...
    async def list_alerts(self, kinds: tuple[AlertKind, ...], limit: int, cursor: str | None) -> Page[AlertRecord]: ...
    async def alert_events_after(
        self, sequence: int, kinds: tuple[AlertKind, ...], limit: int
    ) -> tuple[AlertEventRecord, ...]: ...
    async def latest_alert_sequence(self) -> int: ...
    # 푸시 구독
    async def save_push_subscription(
        self, user_id: str, kinds: tuple[AlertKind, ...], value: PushSubscription, at: datetime
    ) -> tuple[UUID, datetime]: ...
    async def push_subscriptions_for(self, kind: AlertKind) -> tuple[PushSubscription, ...]: ...
    async def delete_push_subscription(self, endpoint: str) -> None: ...
    # 결과
    async def list_results(
        self, subject_ref: str | None, status: SessionStatus | None, limit: int, cursor: str | None
    ) -> Page[SessionRecord]: ...
    async def acknowledge(self, session_id: UUID, by: str, at: datetime) -> tuple[str, datetime]: ...
    async def get_acknowledgement(self, session_id: UUID) -> tuple[str, datetime] | None: ...
    async def log_result_access(self, session_id: UUID, reader_kind: str, reader: str, at: datetime) -> None: ...
    # 실패 사례
    async def turns_without_cases(self, limit: int) -> tuple[TurnRecordData, ...]: ...
    async def mark_cases_checked(self, turns: tuple[tuple[UUID, UUID], ...]) -> None: ...
    async def create_case(self, value: FailureCaseData) -> bool: ...
    async def get_case(self, case_id: UUID) -> FailureCaseData | None: ...
    async def save_case_version(self, value: FailureCaseData, review: CaseReview) -> None: ...
    async def list_cases(
        self, review_status: ReviewStatus | None, questionnaire_id: str | None, limit: int, cursor: str | None
    ) -> Page[FailureCaseData]: ...
    # 잡
    async def purge_expired(self, now: datetime, utterance_cutoff: datetime) -> int: ...
    async def mark_expired_sessions(self, idle_cutoff: datetime) -> tuple[SessionRecord, ...]: ...


class Store(Protocol):
    """DB 접근 약속. 트랜잭션 하나를 열고 닫는다. 오류가 나면 되돌린다."""

    def transaction(self) -> AbstractAsyncContextManager[Tx]: ...
    async def ping(self) -> bool: ...


class ModelPort(Protocol):
    """이웃 model-runtime 호출 약속(link_model_client 가 구현). 값을 못 내면 ModelCallError 를 던진다."""

    async def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
    async def respond(self, request: ResponseGenerationRequest) -> ResponseResult: ...
    async def respond_stream(
        self, request: ResponseGenerationRequest, on_delta: Callable[[str], Awaitable[None]]
    ) -> ResponseResult:
        """응답 문장을 스트림으로 받는다. 조각마다 on_delta 를 부르고, 끝내 못 받으면 ModelCallError 를 던진다."""
        ...

    async def model_io_version(self) -> str | None: ...


class Notifier(Protocol):
    """직원 알림을 웹 푸시로 보내는 약속(link_push 가 구현). 푸시 서비스가 더는 쓰지 않는다고 답한 구독
    주소들을 돌려준다."""

    async def push(self, record: AlertRecord, subscriptions: tuple[PushSubscription, ...]) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class Limits:
    """영역이 쓰는 한도와 시간 상한. 값의 근거는 칸마다 적는다."""

    reask_limit: int  # 계약 ReaskLimit(처음 질문 1회에 되묻기 2회, 사용자 결정 2026-11-10)
    start_code_ttl_seconds: int  # 계약 StartCodeTtlSeconds(기본 300, 최대 600, UD-04)
    idle_seconds: int  # 계약 KioskIdleResetSeconds(60, UD-17)
    turn_seconds: int  # 계약 SurveyTurnLimitSeconds(환자 턴 하나의 총 마감)
    extract_seconds: int  # 계약 ExtractClientLimitSeconds
    respond_seconds: int  # 계약 RespondClientLimitSeconds
    heartbeat_seconds: int  # 계약 AlertStreamHeartbeatSeconds
    retention_days: int  # 계약 RawUtteranceRetentionDays(180일, L12)
    start_failure_limit: int  # 시작 코드 실패 시도 한도(ADR 0002)
    start_failure_window_seconds: int  # 위 한도를 세는 창(ADR 0002)
    retry_after_seconds: int  # Retry-After 로 알리는 초. 계약 RetryAfterSeconds 의 예시 값이고 측정이 아니다


@dataclass(frozen=True)
class Runtime:
    """링크 컴포넌트가 함께 쓰는 의존. main 이 만들어 넣는다(의존 주입)."""

    store: Store
    model: ModelPort
    notifier: Notifier
    now: Callable[[], datetime]
    new_id: Callable[[], UUID]
    limits: Limits
    fhir_canonical_base_url: str
    risk_detection_enabled: bool
    device_placements: Mapping[str, str]  # 기기 ID → 기본 문진표(DevicePlacementTable)
    vapid_public_key: str
