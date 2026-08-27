DIALECTS = {
    "auto": "Automatic — match customer",
    "msa": "Modern Standard Arabic (Fusha)",
    "omani": "Omani Arabic",
    "gulf": "Gulf Arabic",
    "saudi": "Saudi Arabic",
    "emirati": "Emirati Arabic",
    "levantine": "Levantine / Shami Arabic",
    "egyptian": "Egyptian Arabic",
}


def normalize_dialect(value: str | None) -> str:
    value = str(value or "auto").strip().lower()
    if value not in DIALECTS:
        raise ValueError("Unsupported dialect")
    return value


def dialect_prompt(value: str | None) -> str:
    dialect = normalize_dialect(value)
    rules = {
        "auto": (
            "Detect the customer's natural language variety and conversational register from their messages. "
            "When the customer writes colloquial Arabic, answer naturally in the closest matching colloquial dialect. "
            "Do not default to Modern Standard Arabic merely because the message is Arabic. "
            "Use Modern Standard Arabic only when the customer uses it or the conversation clearly calls for formal Arabic. "
            "If the customer changes language or dialect, adapt naturally."
        ),
        "msa": "Use natural Modern Standard Arabic (فصحى) consistently for Arabic replies.",
        "omani": "Use natural Omani Arabic consistently for Arabic replies while remaining clear and professional.",
        "gulf": "Use natural Gulf Arabic consistently for Arabic replies while remaining clear and professional.",
        "saudi": "Use natural Saudi Arabic consistently for Arabic replies while remaining clear and professional.",
        "emirati": "Use natural Emirati Arabic consistently for Arabic replies while remaining clear and professional.",
        "levantine": "Use natural Levantine/Shami Arabic consistently for Arabic replies while remaining clear and professional.",
        "egyptian": "Use natural Egyptian Arabic consistently for Arabic replies while remaining clear and professional.",
    }
    return "AI EMPLOYEE DIALECT POLICY:\n" + rules[dialect]
