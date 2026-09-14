"""Add canonical multi-channel customer identities.

Revision ID: e2b74c91a6fd
Revises: f17a62c0d9e1
"""
from alembic import op
import sqlalchemy as sa

revision = "e2b74c91a6fd"
down_revision = "f17a62c0d9e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=300), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "channel",
            "external_id",
            name="uq_customer_identity_company_channel_external",
        ),
    )
    op.create_index(
        "ix_customer_identities_company_id",
        "customer_identities",
        ["company_id"],
    )
    op.create_index(
        "ix_customer_identities_customer_id",
        "customer_identities",
        ["customer_id"],
    )
    op.create_index(
        "ix_customer_identities_customer_channel",
        "customer_identities",
        ["customer_id", "channel"],
    )

    # Preserve only provable legacy identities. If duplicate customer rows claim
    # the same external identity, leave them unresolved rather than guessing a
    # canonical customer during deployment.
    op.execute("""
        INSERT INTO customer_identities
            (company_id, customer_id, channel, external_id, verified,
             first_seen_at, last_seen_at)
        SELECT c.company_id, c.id, lower(c.channel), c.external_contact_id,
               false, c.first_seen_at, c.last_seen_at
        FROM customer_records c
        JOIN (
            SELECT company_id, lower(channel) AS channel_key,
                   external_contact_id, count(*) AS claim_count
            FROM customer_records
            WHERE channel IS NOT NULL AND channel <> ''
              AND external_contact_id IS NOT NULL AND external_contact_id <> ''
            GROUP BY company_id, lower(channel), external_contact_id
            HAVING count(*) = 1
        ) unique_identity
          ON unique_identity.company_id = c.company_id
         AND unique_identity.channel_key = lower(c.channel)
         AND unique_identity.external_contact_id = c.external_contact_id
    """)


def downgrade():
    op.drop_table("customer_identities")
