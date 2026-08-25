"""add monthly service subscriptions and usage

Revision ID: f31a6c9e4d20
Revises: e84b5c9d2a10
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "f31a6c9e4d20"
down_revision = "e84b5c9d2a10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=False),
        sa.Column("tier", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("monthly_price", sa.Numeric(12, 3), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_code", "tier", name="uq_service_plans_service_tier"),
    )
    op.create_index("ix_service_plans_service_enabled", "service_plans", ["service_code", "enabled"])

    op.create_table(
        "service_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_period_start", sa.DateTime(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["service_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "service_code", name="uq_service_subscription_company_service"),
    )
    op.create_index("ix_service_subscriptions_company_id", "service_subscriptions", ["company_id"])
    op.create_index("ix_service_subscriptions_service_code", "service_subscriptions", ["service_code"])
    op.create_index("ix_service_subscriptions_company_status", "service_subscriptions", ["company_id", "status"])

    op.create_table(
        "service_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_usage_events_company_id", "service_usage_events", ["company_id"])
    op.create_index("ix_service_usage_events_service_code", "service_usage_events", ["service_code"])
    op.create_index(
        "ix_service_usage_company_service_metric_created",
        "service_usage_events",
        ["company_id", "service_code", "metric", "created_at"],
    )


def downgrade():
    op.drop_table("service_usage_events")
    op.drop_table("service_subscriptions")
    op.drop_table("service_plans")
