"""add channel-independent AI employee profiles

Revision ID: e3c8a1f4b720
Revises: d9f4c2a1b760
"""

from alembic import op
import sqlalchemy as sa

revision = "e3c8a1f4b720"
down_revision = "d9f4c2a1b760"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_agent_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("business_type", sa.String(length=150), nullable=True),
        sa.Column("reply_language", sa.String(length=50), nullable=False, server_default="auto"),
        sa.Column("conversation_style", sa.String(length=80), nullable=False, server_default="professional_friendly"),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("agent_id", name="uq_ai_agent_profiles_agent_id"),
    )
    op.create_index("ix_ai_agent_profiles_company_id", "ai_agent_profiles", ["company_id"])
    op.create_index("ix_ai_agent_profiles_agent_id", "ai_agent_profiles", ["agent_id"])


def downgrade():
    op.drop_index("ix_ai_agent_profiles_agent_id", table_name="ai_agent_profiles")
    op.drop_index("ix_ai_agent_profiles_company_id", table_name="ai_agent_profiles")
    op.drop_table("ai_agent_profiles")
