"""add company solutions

Revision ID: e84b5c9d2a10
Revises: d71a9f4e2b63
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "e84b5c9d2a10"
down_revision = "d71a9f4e2b63"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_solutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("package_tier", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("linked_agent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["linked_agent_id"], ["ai_agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_solutions_company_id",
        "company_solutions",
        ["company_id"],
    )
    op.create_index(
        "ix_company_solutions_company_status",
        "company_solutions",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_company_solutions_service",
        "company_solutions",
        ["service_code"],
    )
    op.create_index(
        "ix_company_solutions_linked_agent_id",
        "company_solutions",
        ["linked_agent_id"],
    )


def downgrade():
    op.drop_index(
        "ix_company_solutions_linked_agent_id",
        table_name="company_solutions",
    )
    op.drop_index(
        "ix_company_solutions_service",
        table_name="company_solutions",
    )
    op.drop_index(
        "ix_company_solutions_company_status",
        table_name="company_solutions",
    )
    op.drop_index(
        "ix_company_solutions_company_id",
        table_name="company_solutions",
    )
    op.drop_table("company_solutions")
