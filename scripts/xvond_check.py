
from collections import Counter
from pathlib import Path
import compileall

from backend.app.main import app
from backend.app.core.config.settings import (
    settings,
)
from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.database.hardening import (
    database_integrity_report,
)
from backend.app.core.system_check import (
    run_system_check,
)


def main():

    print("XVOND SYSTEM CHECK")
    print("=" * 60)

    ok = compileall.compile_dir(
        "backend",
        quiet=1,
    )

    print(
        "PYTHON COMPILE:",
        "OK" if ok else "FAILED",
    )

    paths = app.openapi()[
        "paths"
    ]

    print(
        "API ROUTES:",
        len(paths),
    )

    operation_ids = []

    for item in paths.values():
        for method in item.values():

            if not isinstance(
                method,
                dict,
            ):
                continue

            op = method.get(
                "operationId"
            )

            if op:
                operation_ids.append(op)

    duplicates = [
        name
        for name, count
        in Counter(
            operation_ids
        ).items()
        if count > 1
    ]

    print(
        "DUPLICATE OPERATION IDS:",
        duplicates,
    )

    db = SessionLocal()

    try:
        print(
            "DATABASE:",
            database_integrity_report(
                db
            ),
        )

    finally:
        db.close()

    print(
        "SYSTEM:",
        run_system_check(),
    )

    print(
        "ENVIRONMENT:",
        settings.APP_ENV,
    )

    if settings.is_production:

        production_status = (
            "READY"
            if (
                len(
                    settings.JWT_SECRET
                ) >= 32

                and settings.SUPERADMIN_EMAIL

                and settings.SUPERADMIN_PASSWORD
            )
            else "INVALID"
        )

    else:

        production_status = (
            "NOT CHECKED "
            "(development environment)"
        )

    print(
        "PRODUCTION CONFIG:",
        production_status,
    )


if __name__ == "__main__":
    main()
