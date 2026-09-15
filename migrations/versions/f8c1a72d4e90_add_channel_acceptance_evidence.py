"""add system-owned channel acceptance evidence

Revision ID: f8c1a72d4e90
Revises: f17a62c0d9e1
"""

from alembic import op
import sqlalchemy as sa


revision = "f8c1a72d4e90"
down_revision = "f17a62c0d9e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_channels",
        sa.Column("customer_roundtrip_verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "agent_channels",
        sa.Column("customer_roundtrip_source", sa.String(length=100), nullable=True),
    )


def downgrade():
    op.drop_column("agent_channels", "customer_roundtrip_source")
    op.drop_column("agent_channels", "customer_roundtrip_verified_at")
