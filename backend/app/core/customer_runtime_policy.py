from fastapi import HTTPException

from backend.app.core.ai.response_language import configured_reply_language, dominant_language


def is_service_access_error(exc: Exception) -> bool:
    if not isinstance(exc, HTTPException):
        return False
    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message") or "").lower()
        return bool(detail.get("service")) and (
            "limit" in message or "capacity" in message
        )
    text = str(detail or "").lower()
    return (
        "service subscription" in text
        or "service plan" in text
        or "monthly service limit" in text
        or "service capacity limit" in text
    )


def response_language(system_prompt: str, customer_message: str) -> str:
    configured = configured_reply_language(system_prompt)
    if configured == "auto":
        return dominant_language(customer_message)
    if configured in {"en", "english"}:
        return "en"
    if configured in {"ar", "arabic"}:
        return "ar"
    return configured


def safe_service_unavailable_message(system_prompt: str, customer_message: str) -> str:
    language = response_language(system_prompt, customer_message)
    if language == "en":
        return (
            "Sorry, the service is temporarily unavailable. "
            "I've forwarded your conversation to the team for assistance."
        )
    if language == "ar":
        return "عذرًا، الخدمة غير متاحة مؤقتًا. تم تحويل محادثتك للفريق لمساعدتك."
    return (
        "The service is temporarily unavailable. Your conversation has been forwarded "
        "to the team for assistance."
    )


def human_handoff_acknowledgement(system_prompt: str, customer_message: str) -> str:
    language = response_language(system_prompt, customer_message)
    if language == "en":
        return "I've transferred the conversation to a team member. They'll reply here shortly."
    if language == "ar":
        return "تم تحويل المحادثة إلى أحد الموظفين، وسيتم الرد عليك هنا قريبًا."
    return "Your conversation has been transferred to a team member."
