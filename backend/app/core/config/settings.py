
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:

    APP_NAME = os.getenv(
        "APP_NAME",
        "Xvond Core",
    )

    APP_VERSION = os.getenv(
        "APP_VERSION",
        "1.0.0",
    )

    APP_ENV = os.getenv(
        "APP_ENV",
        "development",
    ).strip().lower()

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "",
    )

    JWT_SECRET = os.getenv(
        "JWT_SECRET",
        "",
    )

    JWT_ALGORITHM = os.getenv(
        "JWT_ALGORITHM",
        "HS256",
    )

    JWT_ISSUER = os.getenv(
        "JWT_ISSUER",
        "xvond-core",
    )

    JWT_AUDIENCE = os.getenv(
        "JWT_AUDIENCE",
        "xvond-users",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "60",
        )
    )

    SUPERADMIN_EMAIL = os.getenv(
        "SUPERADMIN_EMAIL",
        "",
    )

    SUPERADMIN_PASSWORD = os.getenv(
        "SUPERADMIN_PASSWORD",
        "",
    )

    SUPERADMIN_FULL_NAME = os.getenv(
        "SUPERADMIN_FULL_NAME",
        "Xvond Super Admin",
    )

    OPENAI_API_KEY = os.getenv(
        "OPENAI_API_KEY",
        "",
    )

    ANTHROPIC_API_KEY = os.getenv(
        "ANTHROPIC_API_KEY",
        "",
    )

    GOOGLE_API_KEY = os.getenv(
        "GOOGLE_API_KEY",
        "",
    )

    XAI_API_KEY = os.getenv(
        "XAI_API_KEY",
        "",
    )

    GROQ_API_KEY = os.getenv(
        "GROQ_API_KEY",
        "",
    )

    CONFIG_ENCRYPTION_KEY = os.getenv(
        "CONFIG_ENCRYPTION_KEY",
        "",
    )

    SMTP_HOST = os.getenv(
        "SMTP_HOST",
        "",
    )

    SMTP_PORT = int(
        os.getenv(
            "SMTP_PORT",
            "465",
        )
    )

    SMTP_USERNAME = os.getenv(
        "SMTP_USERNAME",
        "",
    )

    SMTP_PASSWORD = os.getenv(
        "SMTP_PASSWORD",
        "",
    )

    SMTP_FROM = os.getenv(
        "SMTP_FROM",
        SMTP_USERNAME,
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV in {
            "production",
            "prod",
        }

    def validate(self):

        errors = []

        if not self.DATABASE_URL:
            errors.append(
                "DATABASE_URL is required"
            )

        if not self.JWT_SECRET:
            errors.append(
                "JWT_SECRET is required"
            )

        if self.is_production:

            if len(self.JWT_SECRET) < 32:
                errors.append(
                    "JWT_SECRET must contain at least 32 characters in production"
                )

            weak_secrets = {
                "change-this-before-production",
                "xvond-development-secret-change-before-production",
                "secret",
                "password",
            }

            if self.JWT_SECRET in weak_secrets:
                errors.append(
                    "JWT_SECRET is using a development value"
                )

            if len(self.CONFIG_ENCRYPTION_KEY) < 32:
                errors.append(
                    "CONFIG_ENCRYPTION_KEY must contain at least 32 characters in production"
                )

            if not self.SUPERADMIN_EMAIL:
                errors.append(
                    "SUPERADMIN_EMAIL is required in production"
                )

            if not self.SUPERADMIN_PASSWORD:
                errors.append(
                    "SUPERADMIN_PASSWORD is required in production"
                )

            if (
                self.SUPERADMIN_PASSWORD
                and len(self.SUPERADMIN_PASSWORD) < 12
            ):
                errors.append(
                    "SUPERADMIN_PASSWORD must contain at least 12 characters"
                )

        if errors:
            raise RuntimeError(
                "Invalid Xvond configuration: "
                + "; ".join(errors)
            )


settings = Settings()
settings.validate()
