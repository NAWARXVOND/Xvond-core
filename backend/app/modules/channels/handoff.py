import re
from datetime import datetime, timedelta

from backend.app.core.config.settings import settings


_ARABIC_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670]")
_HUMAN_REQUEST_PATTERNS = (
    "موظف",
    "موظفة",
    "انسان",
    "بشري",
    "خدمة العملاء",
    "مسؤول",
    "مدير",
    "human",
    "agent",
    "representative",
    "customer service",
    "real person",
    "live person",
)


def normalize_message(value: str) -> str:
    text = _ARABIC_DIACRITICS.sub("", str(value or "").lower())
    return " ".join(text.split())


def requests_human(message: str) -> bool:
    text = normalize_message(message)
    return any(pattern in text for pattern in _HUMAN_REQUEST_PATTERNS)


def echo_recipient(message_echo: dict) -> str | None:
    for key in ("to", "recipient_id"):
        value = str(message_echo.get(key) or "").strip()
        if value:
            return value
    return None


def activate_human_handoff(
    session,
    reason: str,
    now: datetime | None = None,
    minutes: int | None = None,
    human_message: bool = False,
):
    current = now or datetime.utcnow()
    duration = minutes or settings.WHATSAPP_HUMAN_HANDOFF_MINUTES

    session.automation_state = "human"
    session.handoff_reason = reason
    session.human_takeover_until = current + timedelta(minutes=duration)
    session.updated_at = current

    if human_message:
        session.last_human_message_at = current

    return session


def human_handoff_active(
    session,
    now: datetime | None = None,
) -> bool:
    if session.automation_state != "human":
        return False

    current = now or datetime.utcnow()
    deadline = session.human_takeover_until

    if deadline is not None and deadline > current:
        return True

    resume_ai(session, now=current)
    return False


def extend_human_handoff(
    session,
    now: datetime | None = None,
):
    return activate_human_handoff(
        session,
        reason=session.handoff_reason or "human_active",
        now=now,
    )


def resume_ai(
    session,
    now: datetime | None = None,
):
    session.automation_state = "ai"
    session.handoff_reason = None
    session.human_takeover_until = None
    session.updated_at = now or datetime.utcnow()
    return session
