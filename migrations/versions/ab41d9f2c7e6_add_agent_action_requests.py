"""add generic agent action requests

Revision ID: ab41d9f2c7e6
Revises: f31a6c9e4d20
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "ab41d9f2c7e6"
down_revision = "f31a6c9e4d20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_action_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_action_requests_company_id", "agent_action_requests", ["company_id"])
    op.create_index("ix_agent_action_requests_agent_id", "agent_action_requests", ["agent_id"])
    op.create_index("ix_agent_action_requests_conversation_id", "agent_action_requests", ["conversation_id"])
    op.create_index("ix_agent_action_requests_action_type", "agent_action_requests", ["action_type"])


def downgrade():
    op.drop_table("agent_action_requests")
