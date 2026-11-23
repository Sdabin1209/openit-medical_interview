"""마이그레이션이 빈 DB 에서 head 까지 올라가고 내려오며 모델과 어긋나지 않는지 본다(임시 SQLite 파일,
PostgreSQL 은 -m postgres)."""

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from survey_service.store.engine import _alembic_config, make_engine, migrate  # pyright: ignore[reportPrivateUsage]
from survey_service.store.models import Base
from survey_service.store.repository import SqlStore

pytestmark = pytest.mark.anyio

EXPECTED = {
    "survey_session", "turn_record", "staff_alert", "failure_case", "question_set_version", "start_code", "start_attempt",
}  # fmt: skip


def tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


async def test_migrate_creates_tables_and_is_idempotent(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'm.db'}")
    try:
        await migrate(engine)
        await migrate(engine)  # 이미 head 면 아무것도 하지 않는다
    finally:
        await engine.dispose()
    assert EXPECTED | {"alembic_version"} <= tables(tmp_path / "m.db")


def test_models_match_migrations_and_downgrade_removes(tmp_path: Path) -> None:
    """모델을 바꾸고 마이그레이션을 빠뜨리면 여기서 걸린다."""
    engine = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    with engine.begin() as connection:
        config: Config = _alembic_config(connection)
        command.upgrade(config, "head")
        diff = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": False}), Base.metadata)
        assert diff == []
        command.downgrade(config, "base")
    engine.dispose()
    assert not (EXPECTED & tables(tmp_path / "c.db"))


# ---------------------------------------------------------------- 0003 survey_session.failed_turn_ids

ROW = (
    "INSERT INTO survey_session (session_id, device_id, subject_ref, questionnaire_id, question_set_version_id,"
    " runtime_contract_version, status, last_assistant_text, answers, blanks, asked_items, reask_count,"
    " resume_pending, started_at, last_activity_at) VALUES (:sid, 'k', 's', 'q', :qsv, 1, 'ACTIVE', 't',"
    " '{}', '[]', '[]', 0, :no, '2026-11-11T00:00:00+00:00', '2026-11-11T00:00:00+00:00')"
)
QSV = (
    "INSERT INTO question_set_version (question_set_version_id, questionnaire_id, version_number,"
    " runtime_contract_version, content, content_hash, uploaded_by, created_at)"
    " VALUES (:qsv, 'q', 1, 1, '{}', 'h', 'u', '2026-11-11T00:00:00+00:00')"
)


async def _step_roundtrip(engine: AsyncEngine) -> None:
    """0002 에서 세션 행을 넣고 0003 으로 올리면 기존 행은 빈 목록이 되고, 내리면 칸이 사라진다."""
    qsv, sid = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "0002"))
        await connection.execute(text(QSV).bindparams(qsv=qsv))
        await connection.execute(text(ROW).bindparams(sid=sid, qsv=qsv, no=False))
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "0003"))
        stored = (await connection.execute(text("SELECT failed_turn_ids FROM survey_session"))).scalar_one()
        assert (json.loads(stored) if isinstance(stored, str) else stored) == []
        columns = await connection.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns("survey_session")])
        assert "failed_turn_ids" in columns
        await connection.run_sync(lambda c: command.downgrade(_alembic_config(c), "0002"))
        columns = await connection.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns("survey_session")])
        assert "failed_turn_ids" not in columns
        remaining = (await connection.execute(text("SELECT count(*) FROM survey_session"))).scalar_one()
        assert remaining == 1  # 내려도 세션 행은 남는다
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "head"))


async def test_0003_adds_and_removes_failed_turn_ids_sqlite(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 's.db'}")
    try:
        await _step_roundtrip(engine)
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_0003_adds_and_removes_failed_turn_ids_postgres(database_url: str) -> None:
    engine = make_engine(database_url)
    try:
        await _step_roundtrip(engine)
    finally:
        await engine.dispose()


# ---------------------------------------------------------------- 0004 survey_session 의 모델 입출력 v3 상태

V3_COLUMNS = {"screen_action", "explain_streak", "ask_back_source"}


async def _step_0004(engine: AsyncEngine) -> None:
    """0003 에서 세션 행을 넣고 0004 로 올리면 기존 행은 화면 절차·원본 없음과 연속 수 0 이 되고(읽으면 v2 규칙),
    새 값을 쓰고 읽을 수 있으며, 내리면 칸이 사라지고 행은 남는다."""
    qsv, sid = uuid.uuid4(), uuid.uuid4()
    source = {"action": "REASK", "reason": "MISSING", "question_id": "Q1", "user_utterance": "글쎄요", "slots": [],
              "values": [], "targets": ["Q1.diagnosed"], "next": {"type": "SAME", "question_id": "Q1", "text": "질문"}}  # fmt: skip
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "0003"))
        await connection.execute(text(QSV).bindparams(qsv=qsv))
        await connection.execute(text(ROW.replace("resume_pending,", "resume_pending, failed_turn_ids,").replace(
            ":no,", ":no, '[]',")).bindparams(sid=sid, qsv=qsv, no=False))  # fmt: skip
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "0004"))
        row = (
            await connection.execute(text("SELECT screen_action, explain_streak, ask_back_source FROM survey_session"))
        ).one()
        assert (row[0], row[1], row[2]) == (None, 0, None)
        # 왜 형 변환: PostgreSQL 의 JSONB 칸은 문자열 매개변수를 그대로 받지 않는다(SQLite 는 JSON 을 글로 둔다)
        placeholder = "CAST(:src AS JSONB)" if connection.dialect.name == "postgresql" else ":src"
        # 자리표시자만 고르는 고정 글이고 값은 매개변수로 묶는다
        update = (
            f"UPDATE survey_session SET screen_action = 'CONFIRM', explain_streak = 2, ask_back_source = {placeholder}"  # noqa: S608
        )
        await connection.execute(text(update).bindparams(src=json.dumps(source, ensure_ascii=False)))
    # 저장소로 읽으면 계약 값으로 돌아온다(JSON 칸이 AskBackSource 로)
    store = SqlStore(engine)
    async with store.transaction() as tx:
        found = await tx.get_session(sid)
    assert found is not None and found.screen_action is not None and found.screen_action.value == "CONFIRM"
    assert found.explain_streak == 2 and found.ask_back_source is not None
    assert found.ask_back_source.model_dump(mode="json", exclude_none=True) == source
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: command.downgrade(_alembic_config(c), "0003"))
        columns = await connection.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("survey_session")})
        assert not (V3_COLUMNS & columns)
        assert (await connection.execute(text("SELECT count(*) FROM survey_session"))).scalar_one() == 1
        await connection.run_sync(lambda c: command.upgrade(_alembic_config(c), "head"))


async def test_0004_adds_and_removes_v3_session_state_sqlite(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 's4.db'}")
    try:
        await _step_0004(engine)
    finally:
        await engine.dispose()


@pytest.mark.postgres
async def test_0004_adds_and_removes_v3_session_state_postgres(database_url: str) -> None:
    engine = make_engine(database_url)
    try:
        await _step_0004(engine)
    finally:
        await engine.dispose()
