from logging.config import fileConfig
import importlib
import pkgutil

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.core.database.base import Base
from backend.app.core.config.settings import settings

import backend.app


# ============================================================
# Alembic config
# ============================================================

config = context.config

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )


# ============================================================
# Import all backend modules
# ============================================================

# Alembic autogenerate needs every SQLAlchemy model loaded
# into Base.metadata. We discover the backend package instead
# of maintaining a fragile manual model-import list.

failed_imports = []

for module_info in pkgutil.walk_packages(
    backend.app.__path__,
    prefix="backend.app.",
):
    name = module_info.name

    # Do not import runtime entrypoints or generated caches.
    if name == "backend.app.main":
        continue

    try:
        importlib.import_module(name)

    except Exception as exc:
        failed_imports.append(
            (
                name,
                type(exc).__name__,
                str(exc),
            )
        )


if failed_imports:

    details = "\n".join(
        f"{name}: {error_type}: {message}"
        for (
            name,
            error_type,
            message,
        ) in failed_imports
    )

    raise RuntimeError(
        "Alembic could not import all backend modules:\n"
        + details
    )


# ============================================================
# Database URL
# ============================================================

database_url = settings.DATABASE_URL

if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not configured"
    )

if database_url.startswith(
    "postgresql://"
):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )


config.set_main_option(
    "sqlalchemy.url",
    database_url.replace(
        "%",
        "%%",
    ),
)


target_metadata = Base.metadata


# ============================================================
# Offline migrations
# ============================================================

def run_migrations_offline():

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# Online migrations
# ============================================================

def run_migrations_online():

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
