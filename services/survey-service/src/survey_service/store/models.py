"""이 영역 DB 의 테이블 정의(SQLAlchemy 2 선언형). 스키마 변경은 마이그레이션(migrations/versions/)으로 한다.

왜 JSON 칸: 문항 세트 내용, 칸 값 표, 추출 출력은 계약 값의 JSON 이고 칸 하나하나로 조회하지 않는다.
PostgreSQL 에서는 JSONB 로 저장한다(색인과 연산자를 쓸 수 있다). 시험이 쓰는 SQLite 는 JSON 으로 대신한다.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

Json = JSON().with_variant(JSONB(), "postgresql")


class UtcDateTime(TypeDecorator[datetime]):
    """시간대가 있는 시각. PostgreSQL 은 timestamptz, 시간대를 못 담는 SQLite 에서는 UTC 로 읽어 되돌린다."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("시간대가 없는 시각은 저장하지 않는다")
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    """모든 모델의 바탕. Alembic 이 metadata 를 비교 기준으로 쓴다."""


class IdempotencyKey(Base):
    """쓰기 요청의 멱등 키. 같은 호출자가 같은 키로 다시 보내면 앞서 만든 것을 돌려준다(Idempotency-Key 초안)."""

    __tablename__ = "idempotency_key"

    operation: Mapped[str] = mapped_column(String(32), primary_key=True)
    principal: Mapped[str] = mapped_column(String(255), primary_key=True)
    key: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class QuestionSetVersionRow(Base):
    """올린 문항 세트의 한 버전. 한 번 저장하면 바뀌지 않는다."""

    __tablename__ = "question_set_version"
    __table_args__ = (UniqueConstraint("questionnaire_id", "version_number"), Index("ix_qsv_created", "created_at"))

    question_set_version_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    questionnaire_id: Mapped[str] = mapped_column(String(63))
    version_number: Mapped[int] = mapped_column(Integer())
    runtime_contract_version: Mapped[int] = mapped_column(Integer())
    content: Mapped[dict[str, object]] = mapped_column(Json)
    content_hash: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class ActiveQuestionSetRow(Base):
    """문진표마다 지금 활성인 버전 하나."""

    __tablename__ = "active_question_set"

    questionnaire_id: Mapped[str] = mapped_column(String(63), primary_key=True)
    question_set_version_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("question_set_version.question_set_version_id")
    )
    activated_by: Mapped[str] = mapped_column(String(255))
    activated_at: Mapped[datetime] = mapped_column(UtcDateTime())


class StartCodeRow(Base):
    """발급한 시작 코드. 한 번 쓰면 폐기(used_by_device)한다."""

    __tablename__ = "start_code"

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    subject_ref: Mapped[str] = mapped_column(String(64))
    questionnaire_id: Mapped[str | None] = mapped_column(String(63))
    issued_by: Mapped[str] = mapped_column(String(255))
    issued_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    used_by_device: Mapped[str | None] = mapped_column(String(64))
    used_session_id: Mapped[UUID | None] = mapped_column(Uuid())


class StartFailureRow(Base):
    """시작 코드 실패 시도(기기별 한도 집계용, NIST SP 800-63B 5.2.2)."""

    __tablename__ = "start_failure"
    __table_args__ = (Index("ix_start_failure_device_at", "device_id", "at"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    device_id: Mapped[str] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(UtcDateTime())


class StartAttemptRow(Base):
    """처리 중인 세션 시작 하나(같은 기기·같은 시작 코드의 재전송을 409 SESSION_START_IN_PROGRESS 로 거르는 표시)."""

    __tablename__ = "start_attempt"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())


class SessionRow(Base):
    """문진 세션."""

    __tablename__ = "survey_session"
    __table_args__ = (Index("ix_session_started", "started_at"), Index("ix_session_subject", "subject_ref"))

    session_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64))
    subject_ref: Mapped[str] = mapped_column(String(64))
    questionnaire_id: Mapped[str] = mapped_column(String(63))
    question_set_version_id: Mapped[UUID] = mapped_column(
        Uuid(), ForeignKey("question_set_version.question_set_version_id")
    )
    runtime_contract_version: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(16))
    pause_reason: Mapped[str | None] = mapped_column(String(16))
    current_item_id: Mapped[str | None] = mapped_column(String(12))
    previous_item_id: Mapped[str | None] = mapped_column(String(12))
    last_assistant_text: Mapped[str] = mapped_column(Text())
    answers: Mapped[dict[str, object]] = mapped_column(Json)
    blanks: Mapped[list[object]] = mapped_column(Json)
    asked_items: Mapped[list[object]] = mapped_column(Json)
    reask_count: Mapped[int] = mapped_column(Integer())
    resume_pending: Mapped[bool] = mapped_column()
    failed_turn_ids: Mapped[list[object]] = mapped_column(Json, default=list)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_activity_at: Mapped[datetime] = mapped_column(UtcDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    model_io_version: Mapped[str | None] = mapped_column(String(32))
    start_code: Mapped[str | None] = mapped_column(String(6))


class TurnRow(Base):
    """턴 기록(trace). (세션, turn_id) 가 한 건이다."""

    __tablename__ = "turn_record"
    __table_args__ = (Index("ix_turn_finished", "finished_at"),)

    session_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("survey_session.session_id"), primary_key=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    questionnaire_id: Mapped[str] = mapped_column(String(63))
    item_id: Mapped[str] = mapped_column(String(12))
    outcome: Mapped[str] = mapped_column(String(16))
    utterance: Mapped[str | None] = mapped_column(String(300))
    extract_output: Mapped[dict[str, object] | None] = mapped_column(Json)
    response_text: Mapped[str | None] = mapped_column(Text())
    failure_signal: Mapped[str | None] = mapped_column(String(32))
    reask_limit_hit: Mapped[bool] = mapped_column()
    response: Mapped[dict[str, object] | None] = mapped_column(Json)
    package_digest: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    case_checked: Mapped[bool] = mapped_column()


class BusinessLogRow(Base):
    """업무 로그. 환자 발화와 비밀은 담지 않는다."""

    __tablename__ = "business_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    event: Mapped[str] = mapped_column(String(48))
    session_id: Mapped[UUID | None] = mapped_column(Uuid())
    at: Mapped[datetime] = mapped_column(UtcDateTime())
    detail: Mapped[dict[str, object]] = mapped_column(Json)


class AlertRow(Base):
    """직원·의사 알림."""

    __tablename__ = "staff_alert"
    __table_args__ = (Index("ix_alert_raised", "raised_at"), Index("ix_alert_session_kind", "session_id", "kind"))

    alert_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    session_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("survey_session.session_id"))
    device_id: Mapped[str | None] = mapped_column(String(64))
    questionnaire_title: Mapped[str | None] = mapped_column(String(200))
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    raised_at: Mapped[datetime] = mapped_column(UtcDateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    resolved_by: Mapped[str | None] = mapped_column(String(255))


class AlertEventRow(Base):
    """알림 스트림 이벤트. 순번(seq)이 SSE 의 id 다."""

    __tablename__ = "alert_event"

    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    event: Mapped[str] = mapped_column(String(16))
    alert_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("staff_alert.alert_id"))
    at: Mapped[datetime] = mapped_column(UtcDateTime())


class PushSubscriptionRow(Base):
    """웹 푸시 구독. 구독한 사람의 계정에 묶는다."""

    __tablename__ = "push_subscription"

    push_subscription_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(8000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(87))
    auth: Mapped[str] = mapped_column(String(22))
    kinds: Mapped[list[object]] = mapped_column(Json)
    registered_at: Mapped[datetime] = mapped_column(UtcDateTime())


class AcknowledgementRow(Base):
    """의사의 결과 확인 표시. 처음 기록을 남긴다."""

    __tablename__ = "result_acknowledgement"

    session_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("survey_session.session_id"), primary_key=True)
    acknowledged_by: Mapped[str] = mapped_column(String(255))
    acknowledged_at: Mapped[datetime] = mapped_column(UtcDateTime())


class ResultAccessRow(Base):
    """결과를 읽은 호출자와 때(접근 기록, U35)."""

    __tablename__ = "result_access_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    session_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("survey_session.session_id"))
    reader_kind: Mapped[str] = mapped_column(String(16))
    reader: Mapped[str] = mapped_column(String(255))
    at: Mapped[datetime] = mapped_column(UtcDateTime())


class FailureCaseRow(Base):
    """실패 사례의 최신 검토 버전. 지난 버전은 failure_case_version 에 남는다."""

    __tablename__ = "failure_case"
    __table_args__ = (UniqueConstraint("kind", "session_id", "turn_id"), Index("ix_case_created", "created_at"))

    case_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    case_version: Mapped[int] = mapped_column(Integer())
    kind: Mapped[str] = mapped_column(String(16))
    session_id: Mapped[UUID] = mapped_column(Uuid())
    turn_id: Mapped[UUID] = mapped_column(Uuid())
    item_id: Mapped[str] = mapped_column(String(12))
    questionnaire_id: Mapped[str] = mapped_column(String(63))
    model_output: Mapped[dict[str, object] | None] = mapped_column(Json)
    utterance: Mapped[str | None] = mapped_column(String(300))
    failure_signal: Mapped[str | None] = mapped_column(String(32))
    response_text: Mapped[str | None] = mapped_column(Text())
    review_status: Mapped[str] = mapped_column(String(16))
    expected: Mapped[dict[str, object] | None] = mapped_column(Json)
    reviewed_input: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime())


class FailureCaseVersionRow(Base):
    """검토가 바뀔 때마다 남기는 지난 검토 버전(되돌아볼 수 있게)."""

    __tablename__ = "failure_case_version"

    case_id: Mapped[UUID] = mapped_column(Uuid(), ForeignKey("failure_case.case_id"), primary_key=True)
    case_version: Mapped[int] = mapped_column(Integer(), primary_key=True)
    review: Mapped[dict[str, object]] = mapped_column(Json)
    reviewed_by: Mapped[str] = mapped_column(String(255))
    reviewed_at: Mapped[datetime] = mapped_column(UtcDateTime())
