
SENSITIVE_WORDS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "client_secret",
    "auth_key",
)


def is_sensitive_key(key: str) -> bool:

    normalized = str(key).lower()

    return any(
        word in normalized
        for word in SENSITIVE_WORDS
    )


def public_config(value):

    if isinstance(value, dict):

        result = {}

        for key, item in value.items():

            if is_sensitive_key(key):
                continue

            result[key] = public_config(
                item
            )

        return result

    if isinstance(value, list):
        return [
            public_config(item)
            for item in value
        ]

    return value


def configured_secret_fields(
    config: dict | None,
    prefix: str = "",
) -> list[str]:

    result = []

    for key, value in (
        config or {}
    ).items():

        path = (
            f"{prefix}.{key}"
            if prefix
            else str(key)
        )

        if is_sensitive_key(key):

            if value not in (
                None,
                "",
                False,
            ):
                result.append(path)

            continue

        if isinstance(value, dict):
            result.extend(
                configured_secret_fields(
                    value,
                    path,
                )
            )

    return sorted(result)


def merge_config(
    existing: dict | None,
    incoming: dict | None,
) -> dict:

    result = dict(
        existing or {}
    )

    if incoming is None:
        return result

    for key, value in incoming.items():

        if (
            is_sensitive_key(key)
            and value in (
                None,
                "",
            )
        ):
            continue

        if (
            isinstance(value, dict)
            and isinstance(
                result.get(key),
                dict,
            )
        ):
            result[key] = merge_config(
                result[key],
                value,
            )

        else:
            result[key] = value

    return result
