import re
from datetime import datetime


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
    """Put the conversation under explicit human control.

    Human takeover is intentionally open-ended. The AI resumes only when an
    authorized user explicitly returns the conversation to AI. ``minutes`` is
    retained for backwards-compatible call signatures but is no longer used to
    auto-resume conversations.
    """
    current = now or datetime.utcnow()

    session.automation_state = "human"
    session.handoff_reason = reason
    session.human_takeover_until = None
    session.updated_at = current

    if human_message:
        session.last_human_message_at = current

    return session


def human_handoff_active(
    session,
    now: datetime | None = None,
) -> bool:
    # Human mode is explicit and does not expire. Only resume_ai() may return
    # the conversation to automation.
    return session.automation_state == "human"


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
