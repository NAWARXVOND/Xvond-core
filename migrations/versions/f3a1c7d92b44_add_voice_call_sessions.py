"""add voice call sessions

Revision ID: f3a1c7d92b44
Revises: e84b5c9d2a10
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a1c7d92b44"
down_revision = "e84b5c9d2a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "voice_call_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_call_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["agent_channels.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_voice_call_sessions_agent_id",
        "voice_call_sessions",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_call_sessions_channel_id",
        "voice_call_sessions",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_call_sessions_company_id",
        "voice_call_sessions",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_call_sessions_conversation_id",
        "voice_call_sessions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_voice_call_sessions_company_agent",
        "voice_call_sessions",
        ["company_id", "agent_id"],
        unique=False,
    )
    op.create_index(
        "uq_voice_call_sessions_channel_external",
        "voice_call_sessions",
        ["channel_id", "external_call_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "uq_voice_call_sessions_channel_external",
        table_name="voice_call_sessions",
    )
    op.drop_index(
        "ix_voice_call_sessions_company_agent",
        table_name="voice_call_sessions",
    )
    op.drop_index(
        "ix_voice_call_sessions_conversation_id",
        table_name="voice_call_sessions",
    )
    op.drop_index(
        "ix_voice_call_sessions_company_id",
        table_name="voice_call_sessions",
    )
    op.drop_index(
        "ix_voice_call_sessions_channel_id",
        table_name="voice_call_sessions",
    )
    op.drop_index(
        "ix_voice_call_sessions_agent_id",
        table_name="voice_call_sessions",
    )
    op.drop_table("voice_call_sessions")
