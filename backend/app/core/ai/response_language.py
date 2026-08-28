import re


_CURRENT_MESSAGE_MARKER = "CURRENT CUSTOMER MESSAGE (answer this intent directly):"
_REPLY_LANGUAGE_RE = re.compile(r"Reply language policy:\s*([^\n.]+)", re.IGNORECASE)


def _current_customer_message(user_message: str) -> str:
    text = str(user_message or "")
    if _CURRENT_MESSAGE_MARKER in text:
        return text.rsplit(_CURRENT_MESSAGE_MARKER, 1)[-1].strip()
    return text.strip()


def dominant_language(message: str) -> str:
    text = str(message or "")
    arabic = sum(1 for char in text if "\u0600" <= char <= "\u06ff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    if arabic > latin:
        return "ar"
    if latin > arabic:
        return "en"
    return "auto"


def configured_reply_language(system_prompt: str) -> str:
    match = _REPLY_LANGUAGE_RE.search(str(system_prompt or ""))
    value = str(match.group(1) if match else "auto").strip().lower()
    aliases = {
        "automatic": "auto",
        "english": "en",
        "en-us": "en",
        "en-gb": "en",
        "arabic": "ar",
        "ar": "ar",
        "en": "en",
    }
    return aliases.get(value, value or "auto")


def response_language_instruction(system_prompt: str, user_message: str) -> str:
    configured = configured_reply_language(system_prompt)
    current_message = _current_customer_message(user_message)
    selected = dominant_language(current_message) if configured == "auto" else configured

    if selected == "en":
        return (
            "RUNTIME RESPONSE LANGUAGE (highest priority for this turn): English. "
            "Reply entirely in natural English. Do not switch to Arabic because company "
            "knowledge, prior conversation messages, greetings, examples, or tools are Arabic."
        )
    if selected == "ar":
        return (
            "RUNTIME RESPONSE LANGUAGE (highest priority for this turn): Arabic. "
            "Reply in Arabic and follow the AI employee's configured Arabic dialect policy. "
            "Do not switch to English because company knowledge or prior messages are English."
        )
    if configured not in {"auto", ""}:
        return (
            "RUNTIME RESPONSE LANGUAGE (highest priority for this turn): "
            f"{configured}. Reply only in that configured language."
        )
    return (
        "RUNTIME RESPONSE LANGUAGE (highest priority for this turn): mirror the language of "
        "the CURRENT CUSTOMER MESSAGE. If the customer changes language, change the response "
        "language on the same turn. Do not let knowledge or conversation history override it."
    )


def apply_response_language(system_prompt: str, user_message: str) -> str:
    instruction = response_language_instruction(system_prompt, user_message)
    return (str(system_prompt or "").strip() + "\n\n" + instruction).strip()
