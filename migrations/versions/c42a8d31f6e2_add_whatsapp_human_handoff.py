"""add WhatsApp coexistence human handoff

Revision ID: c42a8d31f6e2
Revises: b18d4f7a2c90
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c42a8d31f6e2"
down_revision: Union[str, Sequence[str], None] = "b18d4f7a2c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        item["name"]
        for item in inspector.get_columns("whatsapp_sessions")
    }

    if "automation_state" not in columns:
        op.add_column(
            "whatsapp_sessions",
            sa.Column(
                "automation_state",
                sa.String(length=20),
                nullable=False,
                server_default="ai",
            ),
        )

    if "handoff_reason" not in columns:
        op.add_column(
            "whatsapp_sessions",
            sa.Column("handoff_reason", sa.String(length=100), nullable=True),
        )

    if "human_takeover_until" not in columns:
        op.add_column(
            "whatsapp_sessions",
            sa.Column("human_takeover_until", sa.DateTime(), nullable=True),
        )

    if "last_human_message_at" not in columns:
        op.add_column(
            "whatsapp_sessions",
            sa.Column("last_human_message_at", sa.DateTime(), nullable=True),
        )

    if "updated_at" not in columns:
        op.add_column(
            "whatsapp_sessions",
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        item["name"]
        for item in inspector.get_columns("whatsapp_sessions")
    }

    for name in (
        "updated_at",
        "last_human_message_at",
        "human_takeover_until",
        "handoff_reason",
        "automation_state",
    ):
        if name in columns:
            op.drop_column("whatsapp_sessions", name)
