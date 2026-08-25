"""add company profile and business information storage

Revision ID: f4b8d2c1a930
Revises: e3c8a1f4b720
"""

from alembic import op
import sqlalchemy as sa

revision = "f4b8d2c1a930"
down_revision = "e3c8a1f4b720"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("business_type", sa.String(length=150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("currency", sa.String(length=20), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=True),
        sa.Column("primary_language", sa.String(length=50), nullable=True),
        sa.Column("additional_languages", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("phone", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=250), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("working_hours", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("locations", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("services", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("service_areas", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("policies", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("business_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("company_id", name="uq_company_profiles_company_id"),
    )
    op.create_index("ix_company_profiles_company_id", "company_profiles", ["company_id"], unique=True)


def downgrade():
    op.drop_index("ix_company_profiles_company_id", table_name="company_profiles")
    op.drop_table("company_profiles")
