"""add analytics records

Revision ID: b73e8f10c5d2
Revises: a62d7e91b4c8
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "b73e8f10c5d2"
down_revision = "a62d7e91b4c8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["analytics_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_records_company_id", "analytics_records", ["company_id"])
    op.create_index("ix_analytics_records_source_id", "analytics_records", ["source_id"])
    op.create_index("ix_analytics_records_occurred_at", "analytics_records", ["occurred_at"])
    op.create_index(
        "ix_analytics_records_company_source_created",
        "analytics_records",
        ["company_id", "source_id", "created_at"],
    )


def downgrade():
    op.drop_table("analytics_records")
