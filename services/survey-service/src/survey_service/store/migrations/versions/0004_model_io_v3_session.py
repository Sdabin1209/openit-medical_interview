"""세션의 모델 입출력 v3 상태(계약 9.4.0): 화면의 절차, 설명 요청 연속 수, 설명 요청이 이어 받을 원본

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 왜 screen_action·ask_back_source 는 비워 두나: 이미 있는 세션의 화면 절차와 원본은 알 수 없다. 비어 있으면
    # previous_screen_action 을 싣지 않아 model-runtime 이 v2 규칙으로 고르고, 설명 요청은 원본 없이 간다.
    # 왜 explain_streak 의 server_default: 이미 있는 행은 이어진 설명 요청이 없다(0). 모델은 기본값을 코드에서 주므로
    # 서버 기본값은 이 올림에만 쓴다(0003 과 같은 방식)
    with op.batch_alter_table("survey_session") as batch:
        batch.add_column(sa.Column("screen_action", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("explain_streak", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch.add_column(
            sa.Column(
                "ask_back_source",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )
    with op.batch_alter_table("survey_session") as batch:
        batch.alter_column("explain_streak", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("survey_session") as batch:
        batch.drop_column("ask_back_source")
        batch.drop_column("explain_streak")
        batch.drop_column("screen_action")
