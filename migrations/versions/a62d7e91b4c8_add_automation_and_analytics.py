"""add automation and analytics tables

Revision ID: a62d7e91b4c8
Revises: f31a6c9e4d20
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "a62d7e91b4c8"
down_revision = "f31a6c9e4d20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "automation_workflows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("trigger_type", sa.String(length=100), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_workflows_company_id", "automation_workflows", ["company_id"])
    op.create_index("ix_automation_workflows_company_enabled", "automation_workflows", ["company_id", "enabled"])

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["automation_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_runs_company_id", "automation_runs", ["company_id"])
    op.create_index("ix_automation_runs_workflow_id", "automation_runs", ["workflow_id"])
    op.create_index("ix_automation_runs_company_created", "automation_runs", ["company_id", "created_at"])

    op.create_table(
        "analytics_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["company_integrations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_sources_company_id", "analytics_sources", ["company_id"])
    op.create_index("ix_analytics_sources_company_enabled", "analytics_sources", ["company_id", "enabled"])

    op.create_table(
        "analytics_dashboards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_dashboards_company_id", "analytics_dashboards", ["company_id"])


def downgrade():
    op.drop_table("analytics_dashboards")
    op.drop_table("analytics_sources")
    op.drop_table("automation_runs")
    op.drop_table("automation_workflows")
