"""Repair only provable WhatsApp sources and scope sessions to their phone.

Revision ID: c9e24a71d508
Revises: b6e1c4f8a930
"""
import json
import re

from alembic import op
import sqlalchemy as sa

revision = "c9e24a71d508"
down_revision = "b6e1c4f8a930"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "whatsapp_sessions",
        sa.Column("ai_resumed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "whatsapp_sessions",
        sa.Column("ai_resume_echo_id", sa.String(length=255), nullable=True),
    )
    op.drop_constraint("uq_whatsapp_agent_contact", "whatsapp_sessions", type_="unique")
    op.create_unique_constraint(
        "uq_whatsapp_channel_contact", "whatsapp_sessions",
        ["company_id", "agent_id", "phone_number_id", "wa_id"],
    )
    # The plaintext phone ID is routing metadata, never a credential. Do not
    # infer the channel from an employee alone or overwrite conflicting sources.
    op.execute("""
        UPDATE ai_conversations AS c
        SET channel_id = matched.channel_id,
            channel_type = 'whatsapp', external_contact_id = matched.wa_id
        FROM (
            SELECT s.conversation_id, s.company_id, s.agent_id, s.wa_id,
                   min(ch.id) AS channel_id
            FROM whatsapp_sessions s JOIN agent_channels ch
              ON ch.company_id = s.company_id AND ch.agent_id = s.agent_id
             AND ch.channel_type = 'whatsapp'
             AND ch.config->>'phone_number_id' = s.phone_number_id
            GROUP BY s.conversation_id, s.company_id, s.agent_id, s.wa_id
            HAVING count(*) = 1
        ) AS matched
        WHERE c.id = matched.conversation_id
          AND c.company_id = matched.company_id AND c.agent_id = matched.agent_id
          AND (c.channel_id IS NULL OR c.channel_id = matched.channel_id)
          AND (c.channel_type IS NULL OR c.channel_type = 'whatsapp')
          AND (c.external_contact_id IS NULL OR c.external_contact_id = matched.wa_id)
    """)
    # Recover saved structured services only from an unambiguous canonical
    # document. Never generate a catalog from business type, chat, or billing.
    db = op.get_bind()
    profiles = db.execute(sa.text("SELECT id, company_id, services FROM company_profiles")).mappings()
    for row in profiles:
        if row["services"]:
            continue
        docs = db.execute(sa.text("""
            SELECT content FROM knowledge_documents
            WHERE company_id = :company_id AND source_type = 'business_profile'
              AND title = 'Business Information' AND enabled = true
        """), {"company_id": row["company_id"]}).scalars().all()
        if len(docs) != 1:
            continue
        match = re.search(r"(?:^|\n\n)Services:\s*\n(\[)", docs[0] or "")
        if not match:
            continue
        try:
            services, _ = json.JSONDecoder().raw_decode(docs[0][match.start(1):])
        except (ValueError, TypeError):
            continue
        if not isinstance(services, list) or not services or len(services) > 500:
            continue
        if any(not isinstance(item, (str, dict)) or not item for item in services):
            continue
        db.execute(sa.text("UPDATE company_profiles SET services = CAST(:services AS json) WHERE id = :id"),
                   {"services": json.dumps(services, ensure_ascii=False), "id": row["id"]})


def downgrade():
    # Restoring the old constraint after multiple phones were used would either
    # lose data or fail unpredictably. Require an operator to resolve ambiguity.
    duplicates = op.get_bind().execute(sa.text("""
        SELECT 1 FROM whatsapp_sessions GROUP BY agent_id, wa_id HAVING count(*) > 1 LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError("Cannot downgrade: multiple phone sessions exist for a contact")
    op.drop_constraint("uq_whatsapp_channel_contact", "whatsapp_sessions", type_="unique")
    op.create_unique_constraint("uq_whatsapp_agent_contact", "whatsapp_sessions", ["agent_id", "wa_id"])
    op.drop_column("whatsapp_sessions", "ai_resume_echo_id")
    op.drop_column("whatsapp_sessions", "ai_resumed_at")
    # Proven source repairs and recovered business facts are retained.
