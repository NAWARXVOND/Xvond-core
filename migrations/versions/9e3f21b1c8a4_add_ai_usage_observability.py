"""add ai usage observability

Revision ID: 9e3f21b1c8a4
Revises: 7b6697dc454a
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9e3f21b1c8a4"
down_revision: Union[str, Sequence[str], None] = "7b6697dc454a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_usage",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="success",
        ),
    )
    op.add_column(
        "ai_usage",
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_usage",
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_ai_usage_status",
        "ai_usage",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_usage_status",
        table_name="ai_usage",
    )
    op.drop_column("ai_usage", "latency_ms")
    op.drop_column("ai_usage", "error_message")
    op.drop_column("ai_usage", "status")
