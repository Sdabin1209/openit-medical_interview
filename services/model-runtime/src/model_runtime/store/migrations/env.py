"""Alembic 실행 환경(비동기 엔진, ADR 0001: SQLAlchemy asyncio + asyncpg).

왜 DATABASE_URL_FILE: 연결 문자열에 비밀(암호)이 들어 있어 파일로만 받는다(ADR 0005, D84).
"""

import asyncio
import os
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from model_runtime.store.models import Base

target_metadata = Base.metadata


def database_url() -> str:
    path = os.environ.get("DATABASE_URL_FILE")
    if not path:
        raise RuntimeError("DATABASE_URL_FILE 이 설정되지 않았다(연결 문자열을 담은 파일 경로)")
    return Path(path).read_text(encoding="utf-8").strip()


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


def run_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
