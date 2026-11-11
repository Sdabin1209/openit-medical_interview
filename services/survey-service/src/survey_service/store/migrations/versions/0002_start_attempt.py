"""세션 시작 처리 중 표시(start_attempt)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "start_attempt",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("device_id", "code"),
    )


def downgrade() -> None:
    op.drop_table("start_attempt")
