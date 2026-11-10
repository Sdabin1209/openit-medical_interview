"""DB 접근(store 컴포넌트): 저장·조회 명령 → 레코드. 트랜잭션 하나가 Tx 하나다.

계약 값은 컬럼에 JSON 으로 두고 영역 안 값(types)으로 바꿔 주고받는다. SQL 은 여기서만 쓴다.
"""

import base64
import binascii
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from survey_service.contract.models import (
    ActionExtraction,
    ActiveQuestionSet,
    AlertKind,
    CaseReview,
    FailureKind,
    PauseReason,
    PushSubscription,
    ReviewStatus,
    SessionStatus,
    TurnFailureReason,
)
from survey_service.store import models as m
from survey_service.types import (
    AlertEventRecord,
    AlertRecord,
    AnswerRecord,
    BlankRecord,
    DuplicateError,
    FailureCaseData,
    InvalidCursorError,
    Page,
    SessionRecord,
    StartCodeRecord,
    StoredQuestionSet,
    TurnOutcome,
    TurnRecordData,
    Tx,
)

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _encode_cursor(at: datetime, ident: UUID | int) -> str:
    micros = (at.astimezone(UTC) - EPOCH) // timedelta(microseconds=1)
    key = ident.hex if isinstance(ident, UUID) else str(ident)
    return base64.urlsafe_b64encode(f"{micros}.{key}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        micros_text, key = base64.urlsafe_b64decode(padded.encode()).decode().split(".", 1)
        return EPOCH + timedelta(microseconds=int(micros_text)), key
    except (binascii.Error, ValueError, UnicodeDecodeError, OverflowError) as error:
        raise InvalidCursorError(cursor) from error


class SqlTx:
    """Tx 약속의 SQLAlchemy 구현."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ------------------------------------------------------------ 쪽 나누기
    async def _page[R, T](
        self,
        stmt: Select[R],
        time_col: Any,  # noqa: ANN401  (SQLAlchemy 컬럼 표현식)
        id_col: Any,  # noqa: ANN401
        id_is_uuid: bool,
        limit: int,
        cursor: str | None,
        convert: Callable[[R], T],
        ident_of: Callable[[R], UUID | int],
        time_of: Callable[[R], datetime],
    ) -> Page[T]:
        """(시각, 식별자) 내림차순 키셋 쪽 나누기. 왜 키셋: 쪽 사이에 새 항목이 들어와도 중복·누락이 없다."""
        if cursor is not None:
            at, raw = _decode_cursor(cursor)
            try:
                ident: UUID | int = UUID(hex=raw) if id_is_uuid else int(raw)
            except ValueError as error:
                raise InvalidCursorError(cursor) from error
            stmt = stmt.where(or_(time_col < at, and_(time_col == at, id_col < ident)))
        rows = list((await self._s.scalars(stmt.order_by(time_col.desc(), id_col.desc()).limit(limit + 1))).all())
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = _encode_cursor(time_of(rows[-1]), ident_of(rows[-1])) if more and rows else None
        return Page[T](items=tuple(convert(r) for r in rows), next_cursor=next_cursor)

    # ------------------------------------------------------------ 문항 세트
    @staticmethod
    def _qsv(row: m.QuestionSetVersionRow, active: frozenset[UUID] = frozenset()) -> StoredQuestionSet:
        return StoredQuestionSet(
            question_set_version_id=row.question_set_version_id,
            questionnaire_id=row.questionnaire_id,
            version_number=row.version_number,
            runtime_contract_version=row.runtime_contract_version,
            content=row.content,
            content_hash=row.content_hash,
            uploaded_by=row.uploaded_by,
            created_at=row.created_at,
            is_active=row.question_set_version_id in active,
        )

    async def _active_ids(self) -> frozenset[UUID]:
        """지금 활성인 버전 식별자들. 왜 한 번에: 활성 표는 문진표마다 한 줄이라 작고, 목록의 줄마다 묻지 않는다."""
        rows = await self._s.scalars(select(m.ActiveQuestionSetRow.question_set_version_id))
        return frozenset(rows.all())

    async def _idempotent(self, operation: str, principal: str, key: str | None) -> str | None:
        if key is None:
            return None
        row = await self._s.get(m.IdempotencyKey, (operation, principal, key))
        return None if row is None else row.resource_id

    def _remember(self, operation: str, principal: str, key: str | None, resource_id: str, at: datetime) -> None:
        if key is not None:
            self._s.add(
                m.IdempotencyKey(
                    operation=operation, principal=principal, key=key, resource_id=resource_id, created_at=at
                )
            )

    async def save_question_set(self, value: StoredQuestionSet, idempotency_key: str | None) -> StoredQuestionSet:
        known = await self._idempotent("question_set", value.uploaded_by, idempotency_key)
        if known is not None:
            existing = await self._s.get(m.QuestionSetVersionRow, UUID(known))
            if existing is not None:
                return self._qsv(existing, await self._active_ids())
        last = await self._s.scalar(
            select(func.max(m.QuestionSetVersionRow.version_number)).where(
                m.QuestionSetVersionRow.questionnaire_id == value.questionnaire_id
            )
        )
        stored = value.model_copy(update={"version_number": (last or 0) + 1})
        self._s.add(
            m.QuestionSetVersionRow(
                question_set_version_id=stored.question_set_version_id,
                questionnaire_id=stored.questionnaire_id,
                version_number=stored.version_number,
                runtime_contract_version=stored.runtime_contract_version,
                content=stored.content,
                content_hash=stored.content_hash,
                uploaded_by=stored.uploaded_by,
                created_at=stored.created_at,
            )
        )
        self._remember(
            "question_set", value.uploaded_by, idempotency_key, str(stored.question_set_version_id), value.created_at
        )
        await self._s.flush()
        return stored

    async def get_question_set(self, question_set_version_id: UUID) -> StoredQuestionSet | None:
        row = await self._s.get(m.QuestionSetVersionRow, question_set_version_id)
        return None if row is None else self._qsv(row, await self._active_ids())

    async def list_question_sets(
        self, questionnaire_id: str | None, limit: int, cursor: str | None
    ) -> Page[StoredQuestionSet]:
        stmt = select(m.QuestionSetVersionRow)
        if questionnaire_id is not None:
            stmt = stmt.where(m.QuestionSetVersionRow.questionnaire_id == questionnaire_id)
        active = await self._active_ids()
        return await self._page(
            stmt, m.QuestionSetVersionRow.created_at, m.QuestionSetVersionRow.question_set_version_id,
            True, limit, cursor,
            lambda r: self._qsv(r, active), lambda r: r.question_set_version_id,
            lambda r: r.created_at,
        )  # fmt: skip

    async def activate_question_set(self, value: StoredQuestionSet, by: str, at: datetime) -> ActiveQuestionSet:
        row = await self._s.get(m.ActiveQuestionSetRow, value.questionnaire_id)
        if row is None:
            row = m.ActiveQuestionSetRow(
                questionnaire_id=value.questionnaire_id,
                question_set_version_id=value.question_set_version_id,
                activated_by=by,
                activated_at=at,
            )
            self._s.add(row)
        elif row.question_set_version_id != value.question_set_version_id:
            row.question_set_version_id, row.activated_by, row.activated_at = value.question_set_version_id, by, at
        await self._s.flush()
        return ActiveQuestionSet.model_validate(
            {
                "questionnaire_id": row.questionnaire_id,
                "question_set_version_id": str(row.question_set_version_id),
                "runtime_contract_version": value.runtime_contract_version,
                "activated_by": row.activated_by,
                "activated_at": row.activated_at.isoformat(),
            }
        )

    async def active_question_set(self, questionnaire_id: str) -> StoredQuestionSet | None:
        stmt = (
            select(m.QuestionSetVersionRow)
            .join(
                m.ActiveQuestionSetRow,
                m.ActiveQuestionSetRow.question_set_version_id == m.QuestionSetVersionRow.question_set_version_id,
            )
            .where(m.ActiveQuestionSetRow.questionnaire_id == questionnaire_id)
        )
        row = await self._s.scalar(stmt)
        return None if row is None else self._qsv(row, frozenset({row.question_set_version_id}))

    async def list_active_questionnaires(self) -> tuple[StoredQuestionSet, ...]:
        stmt = (
            select(m.QuestionSetVersionRow)
            .join(
                m.ActiveQuestionSetRow,
                m.ActiveQuestionSetRow.question_set_version_id == m.QuestionSetVersionRow.question_set_version_id,
            )
            .order_by(m.QuestionSetVersionRow.questionnaire_id)
        )
        rows = (await self._s.scalars(stmt)).all()
        return tuple(self._qsv(r, frozenset({r.question_set_version_id})) for r in rows)

    # ------------------------------------------------------------ 시작 코드
    @staticmethod
    def _code(row: m.StartCodeRow) -> StartCodeRecord:
        return StartCodeRecord(
            code=row.code, subject_ref=row.subject_ref, questionnaire_id=row.questionnaire_id, issued_by=row.issued_by,
            issued_at=row.issued_at, expires_at=row.expires_at, used_by_device=row.used_by_device,
            used_session_id=row.used_session_id,
        )  # fmt: skip

    async def issue_start_code(self, value: StartCodeRecord, idempotency_key: str) -> StartCodeRecord:
        known = await self._idempotent("start_code", value.issued_by, idempotency_key)
        if known is not None:
            existing = await self._s.get(m.StartCodeRow, known)
            if existing is not None:
                return self._code(existing)
        if await self._s.get(m.StartCodeRow, value.code) is not None:
            raise DuplicateError(value.code)
        self._s.add(
            m.StartCodeRow(
                code=value.code, subject_ref=value.subject_ref, questionnaire_id=value.questionnaire_id,
                issued_by=value.issued_by, issued_at=value.issued_at, expires_at=value.expires_at,
            )
        )  # fmt: skip
        self._remember("start_code", value.issued_by, idempotency_key, value.code, value.issued_at)
        try:
            await self._s.flush()
        except IntegrityError as error:  # 왜: 동시에 같은 코드를 만든 다른 요청과 겹쳤다. 코드를 다시 만들면 된다
            raise DuplicateError(value.code) from error
        return value

    async def get_start_code(self, code: str, for_update: bool = False) -> StartCodeRecord | None:
        stmt = select(m.StartCodeRow).where(m.StartCodeRow.code == code)
        if for_update:
            stmt = stmt.with_for_update()
        row = await self._s.scalar(stmt)
        return None if row is None else self._code(row)

    async def mark_start_code_used(self, code: str, device_id: str, session_id: UUID) -> None:
        await self._s.execute(
            update(m.StartCodeRow)
            .where(m.StartCodeRow.code == code)
            .values(used_by_device=device_id, used_session_id=session_id)
        )

    async def record_start_failure(self, device_id: str, at: datetime) -> None:
        self._s.add(m.StartFailureRow(device_id=device_id, at=at))
        await self._s.flush()

    async def count_start_failures(self, device_id: str, since: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(m.StartFailureRow)
            .where(m.StartFailureRow.device_id == device_id, m.StartFailureRow.at >= since)
        )
        return int(await self._s.scalar(stmt) or 0)

    # ------------------------------------------------------------ 세션
    @staticmethod
    def _session(row: m.SessionRow) -> SessionRecord:
        return SessionRecord(
            session_id=row.session_id, device_id=row.device_id, subject_ref=row.subject_ref,
            questionnaire_id=row.questionnaire_id, question_set_version_id=row.question_set_version_id,
            runtime_contract_version=row.runtime_contract_version, status=SessionStatus(row.status),
            pause_reason=PauseReason(row.pause_reason) if row.pause_reason else None,
            current_item_id=row.current_item_id, previous_item_id=row.previous_item_id,
            last_assistant_text=row.last_assistant_text,
            answers={k: AnswerRecord.model_validate(v) for k, v in row.answers.items()},
            blanks=tuple(BlankRecord.model_validate(b) for b in row.blanks),
            asked_items=tuple(str(i) for i in row.asked_items), reask_count=row.reask_count,
            resume_pending=row.resume_pending, started_at=row.started_at, last_activity_at=row.last_activity_at,
            ended_at=row.ended_at, model_io_version=row.model_io_version,
        )  # fmt: skip

    @staticmethod
    def _fill(row: m.SessionRow, v: SessionRecord) -> None:
        row.device_id, row.subject_ref, row.questionnaire_id = v.device_id, v.subject_ref, v.questionnaire_id
        row.question_set_version_id, row.runtime_contract_version = (
            v.question_set_version_id,
            v.runtime_contract_version,
        )
        row.status, row.pause_reason = v.status.value, v.pause_reason.value if v.pause_reason else None
        row.current_item_id, row.previous_item_id = v.current_item_id, v.previous_item_id
        row.last_assistant_text = v.last_assistant_text
        row.answers = {k: a.model_dump(mode="json") for k, a in v.answers.items()}
        row.blanks = [b.model_dump(mode="json") for b in v.blanks]
        row.asked_items = list(v.asked_items)
        row.reask_count, row.resume_pending = v.reask_count, v.resume_pending
        row.started_at, row.last_activity_at, row.ended_at = v.started_at, v.last_activity_at, v.ended_at
        row.model_io_version = v.model_io_version

    async def create_session(self, value: SessionRecord) -> None:
        row = m.SessionRow(session_id=value.session_id)
        self._fill(row, value)
        self._s.add(row)
        await self._s.flush()

    async def get_session(self, session_id: UUID, for_update: bool = False) -> SessionRecord | None:
        stmt = select(m.SessionRow).where(m.SessionRow.session_id == session_id)
        if for_update:
            stmt = stmt.with_for_update()
        row = await self._s.scalar(stmt)
        return None if row is None else self._session(row)

    async def save_session(self, value: SessionRecord) -> None:
        row = await self._s.get(m.SessionRow, value.session_id)
        if row is None:
            raise LookupError(str(value.session_id))
        self._fill(row, value)
        await self._s.flush()

    # ------------------------------------------------------------ 턴 기록
    @staticmethod
    def _turn(row: m.TurnRow) -> TurnRecordData:
        return TurnRecordData(
            session_id=row.session_id, turn_id=row.turn_id, questionnaire_id=row.questionnaire_id, item_id=row.item_id,
            outcome=TurnOutcome(row.outcome), utterance=row.utterance or "",
            extract_output=ActionExtraction.model_validate(row.extract_output) if row.extract_output else None,
            response_text=row.response_text,
            failure_signal=TurnFailureReason(row.failure_signal) if row.failure_signal else None,
            reask_limit_hit=row.reask_limit_hit, response=row.response, package_digest=row.package_digest,
            started_at=row.started_at, finished_at=row.finished_at,
        )  # fmt: skip

    @staticmethod
    def _fill_turn(row: m.TurnRow, v: TurnRecordData) -> None:
        row.questionnaire_id, row.item_id, row.outcome = v.questionnaire_id, v.item_id, v.outcome.value
        row.utterance = v.utterance
        row.extract_output = v.extract_output.model_dump(mode="json", exclude_none=True) if v.extract_output else None
        row.response_text = v.response_text
        row.failure_signal = v.failure_signal.value if v.failure_signal else None
        row.reask_limit_hit, row.response, row.package_digest = v.reask_limit_hit, v.response, v.package_digest
        row.started_at, row.finished_at = v.started_at, v.finished_at

    async def begin_turn(self, value: TurnRecordData, stale_before: datetime) -> TurnRecordData | None:
        """처리를 시작한다. 이미 있으면 그 기록을 돌려준다. 실패했거나 오래 멈춘 처리 중 기록은 다시 시작할 수 있다."""
        stmt = select(m.TurnRow).where(m.TurnRow.session_id == value.session_id, m.TurnRow.turn_id == value.turn_id)
        row = await self._s.scalar(stmt.with_for_update())
        if row is None:
            row = m.TurnRow(session_id=value.session_id, turn_id=value.turn_id, case_checked=False)
            self._fill_turn(row, value)
            try:
                async with self._s.begin_nested():
                    self._s.add(row)
            except IntegrityError:
                # 왜: 같은 turn_id 의 동시 요청이 먼저 넣었다. 그 요청이 끝난 뒤의 기록을 읽어 처리 중·완료로 돌려준다
                self._s.expunge(row)
                existing = await self._s.scalar(stmt)
                return None if existing is None else self._turn(existing)
            return None
        restartable = row.outcome == TurnOutcome.FAILED.value or (
            row.outcome == TurnOutcome.PROCESSING.value and row.started_at < stale_before
        )
        if restartable:
            self._fill_turn(row, value)
            row.case_checked = False
            await self._s.flush()
            return None
        return self._turn(row)

    async def get_turn(self, session_id: UUID, turn_id: UUID) -> TurnRecordData | None:
        row = await self._s.get(m.TurnRow, (session_id, turn_id))
        return None if row is None else self._turn(row)

    async def finish_turn(self, value: TurnRecordData) -> None:
        row = await self._s.get(m.TurnRow, (value.session_id, value.turn_id))
        if row is None:
            raise LookupError(str(value.turn_id))
        self._fill_turn(row, value)
        await self._s.flush()

    async def log_event(self, event: str, session_id: UUID | None, at: datetime, detail: dict[str, object]) -> None:
        self._s.add(m.BusinessLogRow(event=event, session_id=session_id, at=at, detail=detail))
        await self._s.flush()

    # ------------------------------------------------------------ 알림
    @staticmethod
    def _alert(row: m.AlertRow) -> AlertRecord:
        return AlertRecord(
            alert_id=row.alert_id, kind=AlertKind(row.kind), session_id=row.session_id, device_id=row.device_id,
            questionnaire_title=row.questionnaire_title, dedupe_key=row.dedupe_key, raised_at=row.raised_at,
            resolved_at=row.resolved_at, resolved_by=row.resolved_by,
        )  # fmt: skip

    async def create_alert(self, value: AlertRecord) -> tuple[AlertRecord, bool]:
        if value.dedupe_key is not None:
            existing = await self._s.scalar(select(m.AlertRow).where(m.AlertRow.dedupe_key == value.dedupe_key))
            if existing is not None:
                return self._alert(existing), False
        self._s.add(
            m.AlertRow(
                alert_id=value.alert_id, kind=value.kind.value, session_id=value.session_id, device_id=value.device_id,
                questionnaire_title=value.questionnaire_title, dedupe_key=value.dedupe_key, raised_at=value.raised_at,
            )
        )  # fmt: skip
        await self._s.flush()
        self._s.add(m.AlertEventRow(event="alert", alert_id=value.alert_id, at=value.raised_at))
        await self._s.flush()
        return value, True

    async def get_alert(self, alert_id: UUID) -> AlertRecord | None:
        row = await self._s.get(m.AlertRow, alert_id)
        return None if row is None else self._alert(row)

    async def find_alert(self, dedupe_key: str) -> AlertRecord | None:
        row = await self._s.scalar(select(m.AlertRow).where(m.AlertRow.dedupe_key == dedupe_key))
        return None if row is None else self._alert(row)

    async def open_alert(self, session_id: UUID, kind: AlertKind) -> AlertRecord | None:
        stmt = select(m.AlertRow).where(
            m.AlertRow.session_id == session_id, m.AlertRow.kind == kind.value, m.AlertRow.resolved_at.is_(None)
        )
        row = await self._s.scalar(stmt.order_by(m.AlertRow.raised_at.desc()).limit(1))
        return None if row is None else self._alert(row)

    async def resolve_alerts(
        self, session_id: UUID, kinds: tuple[AlertKind, ...], by: str, at: datetime
    ) -> tuple[AlertRecord, ...]:
        stmt = select(m.AlertRow).where(
            m.AlertRow.session_id == session_id,
            m.AlertRow.kind.in_([k.value for k in kinds]),
            m.AlertRow.resolved_at.is_(None),
        )
        rows = list((await self._s.scalars(stmt)).all())
        for row in rows:
            row.resolved_at, row.resolved_by = at, by
        await self._s.flush()
        for row in rows:
            self._s.add(m.AlertEventRow(event="resolved", alert_id=row.alert_id, at=at))
        await self._s.flush()
        return tuple(self._alert(r) for r in rows)

    async def list_alerts(self, kinds: tuple[AlertKind, ...], limit: int, cursor: str | None) -> Page[AlertRecord]:
        stmt = select(m.AlertRow).where(m.AlertRow.kind.in_([k.value for k in kinds]))
        return await self._page(
            stmt, m.AlertRow.raised_at, m.AlertRow.alert_id, True, limit, cursor,
            self._alert, lambda r: r.alert_id, lambda r: r.raised_at,
        )  # fmt: skip

    async def alert_events_after(
        self, sequence: int, kinds: tuple[AlertKind, ...], limit: int
    ) -> tuple[AlertEventRecord, ...]:
        stmt = (
            select(m.AlertEventRow, m.AlertRow)
            .join(m.AlertRow, m.AlertRow.alert_id == m.AlertEventRow.alert_id)
            .where(m.AlertEventRow.seq > sequence, m.AlertRow.kind.in_([k.value for k in kinds]))
            .order_by(m.AlertEventRow.seq)
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).all()
        return tuple(
            AlertEventRecord(
                sequence=e.seq, event="resolved" if e.event == "resolved" else "alert", alert=self._alert(a)
            )
            for e, a in rows
        )

    async def latest_alert_sequence(self) -> int:
        return int(await self._s.scalar(select(func.coalesce(func.max(m.AlertEventRow.seq), 0))) or 0)

    # ------------------------------------------------------------ 푸시 구독
    async def save_push_subscription(
        self, user_id: str, kinds: tuple[AlertKind, ...], value: PushSubscription, at: datetime
    ) -> tuple[UUID, datetime]:
        endpoint = str(value.endpoint.root)
        row = await self._s.scalar(select(m.PushSubscriptionRow).where(m.PushSubscriptionRow.endpoint == endpoint))
        if row is None:
            row = m.PushSubscriptionRow(push_subscription_id=_new_uuid(), endpoint=endpoint, registered_at=at)
            self._s.add(row)
        row.user_id, row.p256dh, row.auth = user_id, value.keys.p256dh.root, value.keys.auth.root
        row.kinds = [k.value for k in kinds]
        row.registered_at = at
        await self._s.flush()
        return row.push_subscription_id, row.registered_at

    async def push_subscriptions_for(self, kind: AlertKind) -> tuple[PushSubscription, ...]:
        rows = (await self._s.scalars(select(m.PushSubscriptionRow))).all()
        return tuple(
            PushSubscription.model_validate({"endpoint": r.endpoint, "keys": {"p256dh": r.p256dh, "auth": r.auth}})
            for r in rows
            if kind.value in r.kinds
        )

    async def delete_push_subscription(self, endpoint: str) -> None:
        await self._s.execute(delete(m.PushSubscriptionRow).where(m.PushSubscriptionRow.endpoint == endpoint))

    # ------------------------------------------------------------ 결과
    async def list_results(
        self, subject_ref: str | None, status: SessionStatus | None, limit: int, cursor: str | None
    ) -> Page[SessionRecord]:
        stmt = select(m.SessionRow)
        if subject_ref is not None:
            stmt = stmt.where(m.SessionRow.subject_ref == subject_ref)
        if status is not None:
            stmt = stmt.where(m.SessionRow.status == status.value)
        return await self._page(
            stmt, m.SessionRow.started_at, m.SessionRow.session_id, True, limit, cursor,
            self._session, lambda r: r.session_id, lambda r: r.started_at,
        )  # fmt: skip

    async def acknowledge(self, session_id: UUID, by: str, at: datetime) -> tuple[str, datetime]:
        row = await self._s.get(m.AcknowledgementRow, session_id)
        if row is None:
            row = m.AcknowledgementRow(session_id=session_id, acknowledged_by=by, acknowledged_at=at)
            self._s.add(row)
            await self._s.flush()
        return row.acknowledged_by, row.acknowledged_at

    async def get_acknowledgement(self, session_id: UUID) -> tuple[str, datetime] | None:
        row = await self._s.get(m.AcknowledgementRow, session_id)
        return None if row is None else (row.acknowledged_by, row.acknowledged_at)

    async def log_result_access(self, session_id: UUID, reader_kind: str, reader: str, at: datetime) -> None:
        self._s.add(m.ResultAccessRow(session_id=session_id, reader_kind=reader_kind, reader=reader, at=at))
        await self._s.flush()

    # ------------------------------------------------------------ 실패 사례
    async def turns_without_cases(self, limit: int) -> tuple[TurnRecordData, ...]:
        stmt = (
            select(m.TurnRow)
            .where(m.TurnRow.case_checked.is_(False), m.TurnRow.outcome.in_(["DONE", "FAILED"]))
            .order_by(m.TurnRow.started_at, m.TurnRow.turn_id)
            .limit(limit)
        )
        return tuple(self._turn(r) for r in (await self._s.scalars(stmt)).all())

    async def mark_cases_checked(self, turns: tuple[tuple[UUID, UUID], ...]) -> None:
        for session_id, turn_id in turns:
            await self._s.execute(
                update(m.TurnRow)
                .where(m.TurnRow.session_id == session_id, m.TurnRow.turn_id == turn_id)
                .values(case_checked=True)
            )

    @staticmethod
    def _case(row: m.FailureCaseRow) -> FailureCaseData:
        return FailureCaseData(
            case_id=row.case_id, case_version=row.case_version, kind=FailureKind(row.kind), session_id=row.session_id,
            turn_id=row.turn_id, item_id=row.item_id, questionnaire_id=row.questionnaire_id,
            model_output=ActionExtraction.model_validate(row.model_output) if row.model_output else None,
            utterance=row.utterance, review_status=ReviewStatus(row.review_status),
            expected=ActionExtraction.model_validate(row.expected) if row.expected else None,
            reviewed_input=row.reviewed_input, reviewed_by=row.reviewed_by, reviewed_at=row.reviewed_at,
            failure_signal=TurnFailureReason(row.failure_signal) if row.failure_signal else None,
            response_text=row.response_text, created_at=row.created_at, occurred_at=row.occurred_at,
        )  # fmt: skip

    async def create_case(self, value: FailureCaseData) -> bool:
        taken = await self._s.scalar(
            select(m.FailureCaseRow.case_id).where(
                m.FailureCaseRow.kind == value.kind.value,
                m.FailureCaseRow.session_id == value.session_id,
                m.FailureCaseRow.turn_id == value.turn_id,
            )
        )
        if taken is not None:
            return False
        self._s.add(
            m.FailureCaseRow(
                case_id=value.case_id, case_version=value.case_version, kind=value.kind.value,
                session_id=value.session_id,
                turn_id=value.turn_id, item_id=value.item_id, questionnaire_id=value.questionnaire_id,
                model_output=(
                    value.model_output.model_dump(mode="json", exclude_none=True) if value.model_output else None
                ),
                utterance=value.utterance,
                failure_signal=value.failure_signal.value if value.failure_signal else None,
                response_text=value.response_text, review_status=value.review_status.value, expected=None,
                created_at=value.created_at, occurred_at=value.occurred_at,
            )
        )  # fmt: skip
        await self._s.flush()
        return True

    async def get_case(self, case_id: UUID) -> FailureCaseData | None:
        row = await self._s.get(m.FailureCaseRow, case_id)
        return None if row is None else self._case(row)

    async def save_case_version(self, value: FailureCaseData, review: CaseReview) -> None:
        row = await self._s.get(m.FailureCaseRow, value.case_id)
        if row is None or value.reviewed_by is None or value.reviewed_at is None:
            raise LookupError(str(value.case_id))
        row.case_version, row.review_status = value.case_version, value.review_status.value
        row.expected = value.expected.model_dump(mode="json", exclude_none=True) if value.expected else None
        row.reviewed_input, row.reviewed_by, row.reviewed_at = (
            value.reviewed_input,
            value.reviewed_by,
            value.reviewed_at,
        )
        self._s.add(
            m.FailureCaseVersionRow(
                case_id=value.case_id, case_version=value.case_version,
                review=review.model_dump(mode="json", exclude_none=True),
                reviewed_by=value.reviewed_by, reviewed_at=value.reviewed_at,
            )
        )  # fmt: skip
        await self._s.flush()

    async def list_cases(
        self, review_status: ReviewStatus | None, questionnaire_id: str | None, limit: int, cursor: str | None
    ) -> Page[FailureCaseData]:
        stmt = select(m.FailureCaseRow)
        if review_status is not None:
            stmt = stmt.where(m.FailureCaseRow.review_status == review_status.value)
        if questionnaire_id is not None:
            stmt = stmt.where(m.FailureCaseRow.questionnaire_id == questionnaire_id)
        return await self._page(
            stmt, m.FailureCaseRow.created_at, m.FailureCaseRow.case_id, True, limit, cursor,
            self._case, lambda r: r.case_id, lambda r: r.created_at,
        )  # fmt: skip

    # ------------------------------------------------------------ 잡
    async def purge_expired(self, now: datetime, utterance_cutoff: datetime) -> int:
        """보존 기간이 지난 것을 지운다: 발화 원문(180일), 만료된 시작 코드와 오래된 실패 시도."""
        count = 0
        for table in (m.TurnRow, m.FailureCaseRow):
            time_col = m.TurnRow.started_at if table is m.TurnRow else m.FailureCaseRow.created_at
            stmt = update(table).where(time_col < utterance_cutoff, table.utterance.is_not(None)).values(utterance=None)  # pyright: ignore[reportAttributeAccessIssue]
            count += cast("int", (await self._s.execute(stmt)).rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        # 왜 하루: 만료 직후에도 같은 기기의 재전송(REPLAY)과 직원의 확인이 닿도록 만료 뒤 하루는 남긴다(측정 아님)
        gone = delete(m.StartCodeRow).where(
            m.StartCodeRow.expires_at < now - timedelta(days=1), m.StartCodeRow.used_by_device.is_(None)
        )
        count += cast("int", (await self._s.execute(gone)).rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        old = delete(m.StartFailureRow).where(m.StartFailureRow.at < now - timedelta(days=1))
        count += cast("int", (await self._s.execute(old)).rowcount or 0)  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        return count

    async def mark_expired_sessions(self, idle_cutoff: datetime) -> tuple[SessionRecord, ...]:
        """유휴 시간을 넘긴 진행 중 세션을 EXPIRED 로 바꾸고 바뀐 세션들을 돌려준다(끝난 때는 마지막 활동 시각)."""
        stmt = select(m.SessionRow).where(
            m.SessionRow.status == SessionStatus.ACTIVE.value, m.SessionRow.last_activity_at <= idle_cutoff
        )
        rows = list((await self._s.scalars(stmt.with_for_update())).all())
        for row in rows:
            row.status, row.ended_at = SessionStatus.EXPIRED.value, row.last_activity_at
        await self._s.flush()
        return tuple(self._session(r) for r in rows)


def _new_uuid() -> UUID:
    return uuid4()


class SqlStore:
    """Store 약속의 구현. 트랜잭션마다 세션 하나를 열고, 예외가 나면 되돌린다."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transaction(self) -> AbstractAsyncContextManager[Tx]:
        return self._transaction()

    @asynccontextmanager
    async def _transaction(self) -> AsyncGenerator[Tx]:
        async with self._sessions() as session, session.begin():
            yield SqlTx(session)

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:  # 왜: 어떤 실패든 '준비 안 됨'이며 예외 내용은 비밀을 담을 수 있어 버린다
            return False
        return True


__all__ = ["SqlStore", "SqlTx"]
