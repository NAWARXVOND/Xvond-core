
import smtplib
from email.message import EmailMessage

from backend.app.core.config.settings import settings


def send_password_reset_code(
    email: str,
    code: str,
):
    if not settings.SMTP_HOST:
        raise RuntimeError(
            "Email service is not configured"
        )

    message = EmailMessage()

    message["Subject"] = (
        "Xvond password verification code"
    )

    message["From"] = settings.SMTP_FROM
    message["To"] = email

    message.set_content(
        f"""Your Xvond verification code is:

{code}

This code expires in 10 minutes.

If you did not request a password reset,
you can ignore this email.
"""
    )

    with smtplib.SMTP_SSL(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=30,
    ) as smtp:

        smtp.login(
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD,
        )

        smtp.send_message(
            message
        )
