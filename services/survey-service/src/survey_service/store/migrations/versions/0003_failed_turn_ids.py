"""세션의 연속 실패 턴(survey_session.failed_turn_ids, 계약 TurnFailureLimit)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 왜 server_default: 이미 있는 세션 행은 연속 실패가 없다(빈 목록).
    # 모델은 기본값을 코드에서 주므로 서버 기본값은 이 올림에만 쓴다
    with op.batch_alter_table("survey_session") as batch:
        batch.add_column(
            sa.Column(
                "failed_turn_ids",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
    with op.batch_alter_table("survey_session") as batch:
        batch.alter_column("failed_turn_ids", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("survey_session") as batch:
        batch.drop_column("failed_turn_ids")
