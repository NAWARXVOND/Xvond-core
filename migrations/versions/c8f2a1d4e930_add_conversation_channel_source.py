"""add conversation channel source metadata

Revision ID: c8f2a1d4e930
Revises: f4b8d2c1a930
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "c8f2a1d4e930"
down_revision = "f4b8d2c1a930"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_conversations",
        sa.Column("channel_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_conversations",
        sa.Column("channel_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ai_conversations",
        sa.Column("external_contact_id", sa.String(length=200), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_conversations_channel_id_agent_channels",
        "ai_conversations",
        "agent_channels",
        ["channel_id"],
        ["id"],
    )
    op.create_index(
        "ix_ai_conversations_channel_id",
        "ai_conversations",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_external_contact_id",
        "ai_conversations",
        ["external_contact_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_company_channel",
        "ai_conversations",
        ["company_id", "channel_type"],
        unique=False,
    )

    # Existing WhatsApp sessions already provide an exact conversation/contact
    # mapping, so preserve that history in the new generic conversation source.
    op.execute(
        """
        UPDATE ai_conversations AS c
        SET channel_type = 'whatsapp',
            external_contact_id = s.wa_id
        FROM whatsapp_sessions AS s
        WHERE s.conversation_id = c.id
          AND c.channel_type IS NULL
        """
    )


def downgrade():
    op.drop_index(
        "ix_ai_conversations_company_channel",
        table_name="ai_conversations",
    )
    op.drop_index(
        "ix_ai_conversations_external_contact_id",
        table_name="ai_conversations",
    )
    op.drop_index(
        "ix_ai_conversations_channel_id",
        table_name="ai_conversations",
    )
    op.drop_constraint(
        "fk_ai_conversations_channel_id_agent_channels",
        "ai_conversations",
        type_="foreignkey",
    )
    op.drop_column("ai_conversations", "external_contact_id")
    op.drop_column("ai_conversations", "channel_type")
    op.drop_column("ai_conversations", "channel_id")
