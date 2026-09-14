"""add human handoff ownership and lifecycle timestamps

Revision ID: b6e1c4f8a930
Revises: a4d9e7c3f210
"""

from alembic import op
import sqlalchemy as sa


revision = "b6e1c4f8a930"
down_revision = "a4d9e7c3f210"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_handoffs",
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_handoffs",
        sa.Column("taken_over_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_handoffs",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_handoffs",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_handoffs_assigned_user_id_users",
        "agent_handoffs",
        "users",
        ["assigned_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_agent_handoffs_assigned_user_id",
        "agent_handoffs",
        ["assigned_user_id"],
        unique=False,
    )
    op.execute(
        "UPDATE agent_handoffs SET updated_at = created_at WHERE updated_at IS NULL"
    )
    op.alter_column(
        "agent_handoffs",
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )


def downgrade():
    op.drop_index(
        "ix_agent_handoffs_assigned_user_id",
        table_name="agent_handoffs",
    )
    op.drop_constraint(
        "fk_agent_handoffs_assigned_user_id_users",
        "agent_handoffs",
        type_="foreignkey",
    )
    op.drop_column("agent_handoffs", "updated_at")
    op.drop_column("agent_handoffs", "completed_at")
    op.drop_column("agent_handoffs", "taken_over_at")
    op.drop_column("agent_handoffs", "assigned_user_id")
