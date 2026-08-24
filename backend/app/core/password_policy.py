def validate_password(
    password: str,
) -> None:

    if not isinstance(
        password,
        str,
    ):
        raise ValueError(
            "Password must be a string"
        )

    if len(password) < 10:
        raise ValueError(
            "Password must be at least 10 characters"
        )

    if not any(
        c.isalpha()
        for c in password
    ):
        raise ValueError(
            "Password must contain a letter"
        )

    if not any(
        c.isdigit()
        for c in password
    ):
        raise ValueError(
            "Password must contain a number"
        )
