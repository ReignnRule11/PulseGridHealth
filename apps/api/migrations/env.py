from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db import Base
from app import models  # noqa: F401


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def get_migration_url() -> str:
    """Require a distinct DDL identity in production; allow local/test fallback."""
    environment = settings.app_env.strip().lower()
    if environment in {"production", "prod"}:
        if not settings.migration_database_url:
            raise RuntimeError(
                "MIGRATION_DATABASE_URL is required in production; refusing to run "
                "Alembic with the restricted runtime DATABASE_URL."
            )

        runtime = make_url(settings.database_url)
        migration = make_url(settings.migration_database_url)
        if not runtime.drivername.startswith("postgresql") or not migration.drivername.startswith("postgresql"):
            raise RuntimeError("Production runtime and migration URLs must both target PostgreSQL.")
        if not runtime.username or not migration.username or runtime.username == migration.username:
            raise RuntimeError(
                "Production MIGRATION_DATABASE_URL must use a distinct database role "
                "from the runtime DATABASE_URL."
            )
        if runtime.database != migration.database:
            raise RuntimeError(
                "Production runtime and migration URLs must target the same database."
            )

    return settings.migration_database_url or settings.database_url


migration_url = get_migration_url()


def run_migrations_offline():
    context.configure(
        url=migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": migration_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
