"""Alembic 실행 환경(비동기 엔진, ADR 0001: SQLAlchemy asyncio + asyncpg).

두 길이 있다. 앱이 시작할 때는 열려 있는 연결을 넘겨받아 쓴다(`config.attributes["connection"]`, store.engine.migrate).
명령줄(`alembic upgrade head`)로 부를 때는 환경 입력 OPENIT_DATABASE_URL 과 비밀번호 파일
OPENIT_DATABASE_PASSWORD_FILE 에서 만든다(D84).
"""

import asyncio
import os
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from survey_service.store.engine import database_url
from survey_service.store.models import Base

target_metadata = Base.metadata


def _url() -> str:
    base = os.environ.get("OPENIT_DATABASE_URL")
    password_file = os.environ.get("OPENIT_DATABASE_PASSWORD_FILE")
    if not base or not password_file:
        raise RuntimeError("OPENIT_DATABASE_URL 과 OPENIT_DATABASE_PASSWORD_FILE 이 필요하다")
    password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
    return database_url(base, password).render_as_string(hide_password=False)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


existing = context.config.attributes.get("connection")
if existing is not None:
    run_migrations(existing)
elif context.is_offline_mode():
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
