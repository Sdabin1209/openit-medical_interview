"""PostgreSQL 연결(SQLAlchemy asyncio + asyncpg, ADR 0001)과 준비 점검."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def make_engine(url: str) -> AsyncEngine:
    """연결 문자열(비밀)로 엔진을 만든다. 문자열은 로그에 남기지 않는다."""
    return create_async_engine(url, pool_pre_ping=True)


async def check_database(engine: AsyncEngine) -> bool:
    """`SELECT 1` 이 되면 준비됨."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # 왜: 어떤 실패든 '준비 안 됨'이며, 예외 내용은 비밀을 담을 수 있어 버린다
        return False
    return True
