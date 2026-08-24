"""add tool approval workflow

Revision ID: b18d4f7a2c90
Revises: 9e3f21b1c8a4
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b18d4f7a2c90"
down_revision: Union[str, Sequence[str], None] = "9e3f21b1c8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table("tool_approval_requests"):
        return

    op.create_table(
        "tool_approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=150), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"]),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_approval_requests_company_id",
        "tool_approval_requests",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_tool_approval_requests_agent_id",
        "tool_approval_requests",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_tool_approval_company_status",
        "tool_approval_requests",
        ["company_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("tool_approval_requests")
