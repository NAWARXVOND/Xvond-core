"""add semantic knowledge embeddings

Revision ID: f5a7c2e9d410
Revises: c8f2a1d4e930
"""

from alembic import op
import sqlalchemy as sa


revision = "f5a7c2e9d410"
down_revision = "c8f2a1d4e930"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("embedding_provider", sa.String(length=50), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("embedding_model", sa.String(length=120), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("embedding_updated_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_knowledge_chunks_embedding_model",
        "knowledge_chunks",
        ["embedding_model"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_knowledge_chunks_embedding_model", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "embedding_updated_at")
    op.drop_column("knowledge_chunks", "embedding_model")
    op.drop_column("knowledge_chunks", "embedding_provider")
    op.drop_column("knowledge_chunks", "embedding")
