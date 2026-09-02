from datetime import datetime

from backend.app.modules.ai_agent.models import AIConversation, AIMessage
from backend.app.modules.customer_ops.models import CustomerRecord


CUSTOMER_MEMORY_MAX_MESSAGES = 32
CUSTOMER_MEMORY_MAX_CHARS = 6000


def _clean(value):
    text = str(value or "").strip()
    return text or None


def _identity_for_external(external_contact_id: str) -> str:
    return "external:" + external_contact_id.strip().lower()


def get_or_touch_customer(db, conversation: AIConversation) -> CustomerRecord | None:
    external = _clean(conversation.external_contact_id)
    if not external:
        return None

    row = (
        db.query(CustomerRecord)
        .filter(
            CustomerRecord.company_id == conversation.company_id,
            CustomerRecord.external_contact_id == external,
        )
        .first()
    )
    if row is None:
        identity_key = _identity_for_external(external)
        row = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.company_id == conversation.company_id,
                CustomerRecord.identity_key == identity_key,
            )
            .first()
        )

    now = datetime.utcnow()
    if row is None:
        row = CustomerRecord(
            company_id=conversation.company_id,
            identity_key=_identity_for_external(external),
            external_contact_id=external,
            channel=_clean(conversation.channel_type),
            phone=external if str(conversation.channel_type or "").lower() == "whatsapp" else None,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
        db.flush()
    else:
        row.external_contact_id = external
        if _clean(conversation.channel_type):
            row.channel = _clean(conversation.channel_type)
        if str(conversation.channel_type or "").lower() == "whatsapp" and not row.phone:
            row.phone = external
        row.last_seen_at = now

    return row


def _older_customer_messages(db, conversation: AIConversation) -> list[AIMessage]:
    external = _clean(conversation.external_contact_id)
    if not external:
        return []

    # The normal conversation history already supplies the newest 32 messages.
    # Pull the next older block across every conversation for this same customer
    # so continuity survives long chats and future conversation/session rotation.
    rows = (
        db.query(AIMessage)
        .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
        .filter(
            AIConversation.company_id == conversation.company_id,
            AIConversation.external_contact_id == external,
            AIMessage.role.in_(["user", "assistant", "human"]),
        )
        .order_by(AIMessage.id.desc())
        .offset(32)
        .limit(CUSTOMER_MEMORY_MAX_MESSAGES)
        .all()
    )
    rows.reverse()
    return rows


def build_customer_memory(db, conversation: AIConversation) -> str:
    customer = get_or_touch_customer(db, conversation)
    if customer is None:
        return ""

    parts = []
    profile = []
    if _clean(customer.name):
        profile.append(f"Name: {customer.name.strip()}")
    if _clean(customer.phone):
        profile.append(f"Phone: {customer.phone.strip()}")
    if _clean(customer.email):
        profile.append(f"Email: {customer.email.strip()}")
    if customer.tags:
        profile.append("Tags: " + ", ".join(str(x) for x in customer.tags if str(x).strip()))
    if _clean(customer.notes):
        profile.append("Business notes about this customer: " + customer.notes.strip())
    if profile:
        parts.append("CUSTOMER PROFILE (persistent, company-managed):\n" + "\n".join(profile))

    older = _older_customer_messages(db, conversation)
    if older:
        lines = []
        used = 0
        for item in older:
            role = str(item.role or "").strip().lower()
            content = str(item.content or "").strip()
            if not content:
                continue
            line = f"{role}: {content}"
            size = len(line) + (1 if lines else 0)
            if lines and used + size > CUSTOMER_MEMORY_MAX_CHARS:
                break
            if not lines and size > CUSTOMER_MEMORY_MAX_CHARS:
                line = line[:CUSTOMER_MEMORY_MAX_CHARS]
                size = len(line)
            lines.append(line)
            used += size
        if lines:
            parts.append(
                "OLDER CUSTOMER INTERACTIONS (persistent continuity; newer conversation history wins on conflicts):\n"
                + "\n".join(lines)
            )

    return "\n\n".join(parts)
