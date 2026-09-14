"""Add durable WhatsApp transport and resumable inbound processing.

Revision ID: f17a62c0d9e1
Revises: c9e24a71d508
"""
from alembic import op
import sqlalchemy as sa

revision = "f17a62c0d9e1"
down_revision = "c9e24a71d508"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_messages", sa.Column("source_key", sa.String(length=320), nullable=True))
    op.create_index("ix_ai_messages_source_key", "ai_messages", ["source_key"], unique=True)

    op.add_column(
        "whatsapp_inbound_messages",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="processing"),
    )
    op.add_column(
        "whatsapp_inbound_messages",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "whatsapp_inbound_messages",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "ix_whatsapp_inbound_messages_status",
        "whatsapp_inbound_messages",
        ["status"],
    )

    op.create_table(
        "whatsapp_outbound_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("agent_channels.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("ai_messages.id"), nullable=False),
        sa.Column("inbound_external_message_id", sa.String(length=255), nullable=True),
        sa.Column("wa_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(length=160), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_whatsapp_outbound_idempotency"),
        sa.UniqueConstraint("provider_message_id", name="uq_whatsapp_outbound_provider_message"),
    )
    for column in (
        "idempotency_key",
        "company_id",
        "agent_id",
        "conversation_id",
        "channel_id",
        "message_id",
        "inbound_external_message_id",
        "wa_id",
        "status",
        "provider_message_id",
    ):
        op.create_index(
            f"ix_whatsapp_outbound_deliveries_{column}",
            "whatsapp_outbound_deliveries",
            [column],
        )


def downgrade():
    op.drop_table("whatsapp_outbound_deliveries")
    op.drop_index("ix_whatsapp_inbound_messages_status", table_name="whatsapp_inbound_messages")
    op.drop_column("whatsapp_inbound_messages", "updated_at")
    op.drop_column("whatsapp_inbound_messages", "attempts")
    op.drop_column("whatsapp_inbound_messages", "status")
    op.drop_index("ix_ai_messages_source_key", table_name="ai_messages")
    op.drop_column("ai_messages", "source_key")
