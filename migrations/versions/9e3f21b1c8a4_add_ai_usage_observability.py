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


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        column["name"]
        for column in inspector.get_columns("ai_usage")
    }


def upgrade() -> None:
    columns = _column_names()

    if "status" not in columns:
        op.add_column(
            "ai_usage",
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="success",
            ),
        )

    if "error_message" not in columns:
        op.add_column(
            "ai_usage",
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
            ),
        )

    if "latency_ms" not in columns:
        op.add_column(
            "ai_usage",
            sa.Column(
                "latency_ms",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("ai_usage")
    }

    if "ix_ai_usage_status" not in indexes:
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
