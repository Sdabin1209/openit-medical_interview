"""마이그레이션이 빈 DB 에서 head 까지 올라가고 내려오며 모델과 어긋나지 않는지 본다(임시 SQLite 파일)."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from __PKG__.store.models import Base

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    url_file = tmp_path / "database_url"
    url_file.write_text(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(url_file))
    return Config(str(ROOT / "alembic.ini"))


def tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def test_upgrade_head_creates_tables_and_downgrade_removes(config: Config, tmp_path: Path) -> None:
    command.upgrade(config, "head")
    assert {"greeting", "alembic_version"} <= tables(tmp_path / "test.db")
    command.downgrade(config, "base")
    assert "greeting" not in tables(tmp_path / "test.db")


def test_upgrade_is_idempotent(config: Config, tmp_path: Path) -> None:
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # 이미 head 면 아무것도 하지 않는다
    assert "greeting" in tables(tmp_path / "test.db")


def test_models_match_migrations(config: Config, tmp_path: Path) -> None:
    """모델을 바꾸고 마이그레이션을 빠뜨리면 여기서 걸린다."""
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []
