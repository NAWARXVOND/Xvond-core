"""add customer operations layer

Revision ID: a4d9e7c3f210
Revises: f5a7c2e9d410
"""

from alembic import op
import sqlalchemy as sa


revision = "a4d9e7c3f210"
down_revision = "f5a7c2e9d410"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("identity_key", sa.String(length=300), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("external_contact_id", sa.String(length=200), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", "identity_key", name="uq_customer_records_company_identity"),
    )
    op.create_index("ix_customer_records_company_id", "customer_records", ["company_id"])
    op.create_index("ix_customer_records_phone", "customer_records", ["phone"])
    op.create_index("ix_customer_records_email", "customer_records", ["email"])
    op.create_index("ix_customer_records_external_contact_id", "customer_records", ["external_contact_id"])
    op.create_index("ix_customer_records_company_updated", "customer_records", ["company_id", "updated_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("event_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("destinations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("whatsapp", sa.String(length=100), nullable=True),
        sa.Column("webhook_url", sa.String(length=1000), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", name="uq_notification_preferences_company"),
    )
    op.create_index("ix_notification_preferences_company_id", "notification_preferences", ["company_id"])

    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", "event_key", name="uq_notification_events_company_key"),
    )
    op.create_index("ix_notification_events_company_id", "notification_events", ["company_id"])
    op.create_index("ix_notification_events_event_type", "notification_events", ["event_type"])
    op.create_index("ix_notification_events_read", "notification_events", ["read"])
    op.create_index("ix_notification_events_company_created", "notification_events", ["company_id", "created_at"])


def downgrade():
    op.drop_index("ix_notification_events_company_created", table_name="notification_events")
    op.drop_index("ix_notification_events_read", table_name="notification_events")
    op.drop_index("ix_notification_events_event_type", table_name="notification_events")
    op.drop_index("ix_notification_events_company_id", table_name="notification_events")
    op.drop_table("notification_events")
    op.drop_index("ix_notification_preferences_company_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("ix_customer_records_company_updated", table_name="customer_records")
    op.drop_index("ix_customer_records_external_contact_id", table_name="customer_records")
    op.drop_index("ix_customer_records_email", table_name="customer_records")
    op.drop_index("ix_customer_records_phone", table_name="customer_records")
    op.drop_index("ix_customer_records_company_id", table_name="customer_records")
    op.drop_table("customer_records")
