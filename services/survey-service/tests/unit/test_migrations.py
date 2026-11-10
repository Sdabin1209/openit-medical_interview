"""마이그레이션이 빈 DB 에서 head 까지 올라가고 내려오며 모델과 어긋나지 않는지 본다(임시 SQLite 파일,
PostgreSQL 은 -m postgres)."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from survey_service.store.engine import _alembic_config, make_engine, migrate  # pyright: ignore[reportPrivateUsage]
from survey_service.store.models import Base

pytestmark = pytest.mark.anyio

EXPECTED = {"survey_session", "turn_record", "staff_alert", "failure_case", "question_set_version", "start_code"}


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
