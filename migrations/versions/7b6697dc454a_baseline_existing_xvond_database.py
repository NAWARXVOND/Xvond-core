"""baseline existing xvond database

Revision ID: 7b6697dc454a
Revises: 
Create Date: 2026-08-23 05:54:52.455426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.app.core.database.base import Base


# revision identifiers, used by Alembic.
revision: str = '7b6697dc454a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the complete Xvond schema on a fresh database."""
    Base.metadata.create_all(
        bind=op.get_bind(),
        checkfirst=True,
    )


def downgrade() -> None:
    """Remove the complete baseline schema."""
    Base.metadata.drop_all(
        bind=op.get_bind(),
        checkfirst=True,
    )
