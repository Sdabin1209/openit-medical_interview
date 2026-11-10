"""PostgreSQL 연결(SQLAlchemy asyncio + asyncpg, ADR 0001)과 마이그레이션 실행."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ASYNC_DRIVER = "postgresql+asyncpg"
# 왜 이 번호: 같은 DB 에 여러 복제본이 동시에 마이그레이션하지 않게 하는 PostgreSQL 권고 잠금의 키다(임의의
# 영역 고유 값)
MIGRATION_LOCK_KEY = 7_201_510


def database_url(base: str, password: str) -> URL:
    """환경 입력의 접속 주소(비밀번호 없음)와 비밀번호 파일의 값으로 접속 URL 을 만든다. 문자열은 로그에
    남기지 않는다."""
    url = make_url(base)
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername=ASYNC_DRIVER)
    return url.set(password=password)


def make_engine(url: str | URL) -> AsyncEngine:
    """엔진을 만든다. pool_pre_ping: 끊긴 연결을 쓰기 전에 걸러 낸다."""
    return create_async_engine(url, pool_pre_ping=True)


def _alembic_config(connection: Connection) -> Config:
    # 왜 ini 파일 없이: 설치된 패키지(이미지)에는 alembic.ini 가 없다. 마이그레이션 폴더는 패키지 안에 있다
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    config.attributes["connection"] = connection
    return config


def _upgrade(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
    command.upgrade(_alembic_config(connection), "head")


async def migrate(engine: AsyncEngine) -> None:
    """head 까지 마이그레이션한다(이미 head 면 아무것도 하지 않는다)."""
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)


async def check_database(engine: AsyncEngine) -> bool:
    """`SELECT 1` 이 되면 준비됨."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # 왜: 어떤 실패든 '준비 안 됨'이며, 예외 내용은 비밀을 담을 수 있어 버린다
        return False
    return True
