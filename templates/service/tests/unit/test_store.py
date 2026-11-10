import pytest

from __PKG__.store.engine import check_database, make_engine


@pytest.mark.anyio
async def test_check_database_false_when_unreachable() -> None:
    # 포트 1 은 아무도 듣지 않는다. 실패해도 예외가 아니라 False 여야 한다.
    engine = make_engine("postgresql+asyncpg://u:p@127.0.0.1:1/db")
    try:
        assert await check_database(engine) is False
    finally:
        await engine.dispose()
