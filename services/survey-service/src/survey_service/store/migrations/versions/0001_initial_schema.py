"""초기 스키마

Revision ID: 0001
Revises:
Create Date: 2026-11-10 21:50:46.768811
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("event", sa.String(length=48), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "detail", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "failure_case",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.String(length=12), nullable=False),
        sa.Column("questionnaire_id", sa.String(length=63), nullable=False),
        sa.Column(
            "model_output", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column("utterance", sa.String(length=300), nullable=True),
        sa.Column("failure_signal", sa.String(length=32), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=16), nullable=False),
        sa.Column(
            "expected", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column("reviewed_input", sa.String(length=300), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
        sa.UniqueConstraint("kind", "session_id", "turn_id"),
    )
    op.create_index("ix_case_created", "failure_case", ["created_at"], unique=False)
    op.create_table(
        "idempotency_key",
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("principal", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("operation", "principal", "key"),
    )
    op.create_table(
        "push_subscription",
        sa.Column("push_subscription_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=8000), nullable=False),
        sa.Column("p256dh", sa.String(length=87), nullable=False),
        sa.Column("auth", sa.String(length=22), nullable=False),
        sa.Column(
            "kinds", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("push_subscription_id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_table(
        "question_set_version",
        sa.Column("question_set_version_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.String(length=63), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("runtime_contract_version", sa.Integer(), nullable=False),
        sa.Column(
            "content", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("question_set_version_id"),
        sa.UniqueConstraint("questionnaire_id", "version_number"),
    )
    op.create_index("ix_qsv_created", "question_set_version", ["created_at"], unique=False)
    op.create_table(
        "start_code",
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("subject_ref", sa.String(length=64), nullable=False),
        sa.Column("questionnaire_id", sa.String(length=63), nullable=True),
        sa.Column("issued_by", sa.String(length=255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by_device", sa.String(length=64), nullable=True),
        sa.Column("used_session_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "start_failure",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_start_failure_device_at", "start_failure", ["device_id", "at"], unique=False)
    op.create_table(
        "active_question_set",
        sa.Column("questionnaire_id", sa.String(length=63), nullable=False),
        sa.Column("question_set_version_id", sa.Uuid(), nullable=False),
        sa.Column("activated_by", sa.String(length=255), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_set_version_id"],
            ["question_set_version.question_set_version_id"],
        ),
        sa.PrimaryKeyConstraint("questionnaire_id"),
    )
    op.create_table(
        "failure_case_version",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column(
            "review", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["failure_case.case_id"],
        ),
        sa.PrimaryKeyConstraint("case_id", "case_version"),
    )
    op.create_table(
        "survey_session",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("subject_ref", sa.String(length=64), nullable=False),
        sa.Column("questionnaire_id", sa.String(length=63), nullable=False),
        sa.Column("question_set_version_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_contract_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pause_reason", sa.String(length=16), nullable=True),
        sa.Column("current_item_id", sa.String(length=12), nullable=True),
        sa.Column("previous_item_id", sa.String(length=12), nullable=True),
        sa.Column("last_assistant_text", sa.Text(), nullable=False),
        sa.Column(
            "answers", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column(
            "blanks", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column(
            "asked_items", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("reask_count", sa.Integer(), nullable=False),
        sa.Column("resume_pending", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_io_version", sa.String(length=32), nullable=True),
        sa.Column("start_code", sa.String(length=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["question_set_version_id"],
            ["question_set_version.question_set_version_id"],
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_session_started", "survey_session", ["started_at"], unique=False)
    op.create_index("ix_session_subject", "survey_session", ["subject_ref"], unique=False)
    op.create_table(
        "result_access_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("reader_kind", sa.String(length=16), nullable=False),
        sa.Column("reader", sa.String(length=255), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["survey_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "result_acknowledgement",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=255), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["survey_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_table(
        "staff_alert",
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("questionnaire_title", sa.String(length=200), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["survey_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("alert_id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index("ix_alert_raised", "staff_alert", ["raised_at"], unique=False)
    op.create_index("ix_alert_session_kind", "staff_alert", ["session_id", "kind"], unique=False)
    op.create_table(
        "turn_record",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.String(length=63), nullable=False),
        sa.Column("item_id", sa.String(length=12), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("utterance", sa.String(length=300), nullable=True),
        sa.Column(
            "extract_output",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("failure_signal", sa.String(length=32), nullable=True),
        sa.Column("reask_limit_hit", sa.Boolean(), nullable=False),
        sa.Column(
            "response", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column("package_digest", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("case_checked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["survey_session.session_id"],
        ),
        sa.PrimaryKeyConstraint("session_id", "turn_id"),
    )
    op.create_index("ix_turn_finished", "turn_record", ["finished_at"], unique=False)
    op.create_table(
        "alert_event",
        sa.Column("seq", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("event", sa.String(length=16), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["staff_alert.alert_id"],
        ),
        sa.PrimaryKeyConstraint("seq"),
    )


def downgrade() -> None:
    op.drop_table("alert_event")
    op.drop_index("ix_turn_finished", table_name="turn_record")
    op.drop_table("turn_record")
    op.drop_index("ix_alert_session_kind", table_name="staff_alert")
    op.drop_index("ix_alert_raised", table_name="staff_alert")
    op.drop_table("staff_alert")
    op.drop_table("result_acknowledgement")
    op.drop_table("result_access_log")
    op.drop_index("ix_session_subject", table_name="survey_session")
    op.drop_index("ix_session_started", table_name="survey_session")
    op.drop_table("survey_session")
    op.drop_table("failure_case_version")
    op.drop_table("active_question_set")
    op.drop_index("ix_start_failure_device_at", table_name="start_failure")
    op.drop_table("start_failure")
    op.drop_table("start_code")
    op.drop_index("ix_qsv_created", table_name="question_set_version")
    op.drop_table("question_set_version")
    op.drop_table("push_subscription")
    op.drop_table("idempotency_key")
    op.drop_index("ix_case_created", table_name="failure_case")
    op.drop_table("failure_case")
    op.drop_table("business_log")
