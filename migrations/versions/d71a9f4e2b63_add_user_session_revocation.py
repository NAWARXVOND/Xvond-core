"""add user session revocation state

Revision ID: d71a9f4e2b63
Revises: c42a8d31f6e2
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "d71a9f4e2b63"
down_revision = "c42a8d31f6e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column(
        "users",
        "active",
        server_default=None,
    )
    op.alter_column(
        "users",
        "token_version",
        server_default=None,
    )


def downgrade():
    op.drop_column("users", "token_version")
    op.drop_column("users", "active")
