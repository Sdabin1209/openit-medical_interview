import uuid
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tests.support.harness import Harness, build_harness, sqlite_url
from tests.support.postgres import PostgresContainer


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[PostgresContainer]:
    """`-m postgres` 로 고른 시험이 있을 때만 PostgreSQL 16 컨테이너를 하나 띄운다."""
    server = PostgresContainer()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)])
async def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncGenerator[str]:
    """시험마다 새 DB. SQLite 는 임시 파일, PostgreSQL 은 컨테이너 안의 새 데이터베이스."""
    if request.param == "sqlite":
        yield sqlite_url(tmp_path)
        return
    server: PostgresContainer = request.getfixturevalue("postgres_server")
    name = f"t_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(server.url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin.dispose()
    yield server.url(name)


@pytest.fixture
async def harness(database_url: str) -> AsyncGenerator[Harness]:
    built = await build_harness(database_url)
    try:
        yield built
    finally:
        await built.engine.dispose()
