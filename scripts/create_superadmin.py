from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.core.security import hash_password

import backend.app.models

from backend.app.models.user import User


def main():
    db = SessionLocal()

    try:
        existing = (
            db.query(User)
            .filter(
                User.email == settings.SUPERADMIN_EMAIL
            )
            .first()
        )

        if existing is not None:
            print(
                "Super admin already exists:",
                existing.email,
            )
            return

        user = User(
            company_id=None,
            email=settings.SUPERADMIN_EMAIL,
            full_name=settings.SUPERADMIN_FULL_NAME,
            password_hash=hash_password(
                settings.SUPERADMIN_PASSWORD
            ),
            role="super_admin",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(
            "Super admin created:",
            user.email,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
