"""add company commercial lifecycle

Revision ID: e9c14b72a630
Revises: e2b74c91a6fd
"""

from alembic import op
import sqlalchemy as sa


revision = "e9c14b72a630"
down_revision = "e2b74c91a6fd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "companies",
        sa.Column("lifecycle_status", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("lifecycle_updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        UPDATE companies
        SET lifecycle_status = CASE WHEN active THEN 'live' ELSE 'onboarding' END,
            lifecycle_updated_at = COALESCE(created_at, NOW())
        """
    )
    op.alter_column("companies", "lifecycle_status", nullable=False)
    op.alter_column("companies", "lifecycle_updated_at", nullable=False)
    op.create_index(
        "ix_companies_lifecycle_status",
        "companies",
        ["lifecycle_status"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_companies_lifecycle_status", table_name="companies")
    op.drop_column("companies", "lifecycle_updated_at")
    op.drop_column("companies", "lifecycle_status")
