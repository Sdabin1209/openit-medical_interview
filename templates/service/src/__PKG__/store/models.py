"""이 영역 DB 의 테이블 정의(SQLAlchemy 2 선언형). 스키마 변경은 마이그레이션(migrations/versions/)으로 한다."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 모델의 바탕. Alembic 이 metadata 를 비교 기준으로 쓴다."""


class Greeting(Base):
    """템플릿 예시 테이블. 지우고 자기 테이블로 바꾼다(지울 때 새 마이그레이션 리비전을 더한다)."""

    __tablename__ = "greeting"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), doc="인사받는 사람 이름(1~64자, 계약의 이름 제약과 같다)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
