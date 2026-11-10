from app.core.config import Settings


def test_render_postgres_url_uses_installed_psycopg_driver():
    settings = Settings(database_url="postgresql://user:pass@host:5432/pulsegrid")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/pulsegrid"


def test_legacy_postgres_url_uses_installed_psycopg_driver():
    settings = Settings(database_url="postgres://user:pass@host:5432/pulsegrid")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/pulsegrid"


def test_explicit_sqlalchemy_driver_is_preserved():
    url = "postgresql+psycopg://user:pass@host:5432/pulsegrid"
    settings = Settings(database_url=url)
    assert settings.database_url == url



def test_production_migrations_require_separate_credentials():
    from app.core.config import resolve_migration_database_url
    import pytest

    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL is required"):
        resolve_migration_database_url(
            "postgresql+psycopg://runtime:secret@host:5432/pulsegrid",
            None,
            "production",
        )


def test_production_migrations_reject_the_runtime_role():
    from app.core.config import resolve_migration_database_url
    import pytest

    url = "postgresql+psycopg://pulsegrid:secret@host:5432/pulsegrid"
    with pytest.raises(RuntimeError, match="distinct database role"):
        resolve_migration_database_url(url, url, "production")


def test_production_migrations_require_postgres_and_same_database():
    from app.core.config import resolve_migration_database_url
    import pytest

    runtime = "postgresql+psycopg://runtime:secret@host:5432/pulsegrid"
    wrong_database = "postgresql+psycopg://owner:secret@host:5432/other"
    with pytest.raises(RuntimeError, match="same database"):
        resolve_migration_database_url(runtime, wrong_database, "production")

    with pytest.raises(RuntimeError, match="both target PostgreSQL"):
        resolve_migration_database_url(
            "sqlite:///runtime.db",
            "sqlite:///migration.db",
            "production",
        )


def test_nonproduction_migrations_keep_local_fallback():
    from app.core.config import resolve_migration_database_url

    runtime = "sqlite:///pulsegrid.db"
    assert resolve_migration_database_url(runtime, None, "test") == runtime
    migration = "sqlite:///migration.db"
    assert resolve_migration_database_url(runtime, migration, "development") == migration


def test_production_migrations_accept_distinct_roles_for_same_database():
    from app.core.config import resolve_migration_database_url

    runtime = "postgresql+psycopg://runtime:secret@host-pooler:5432/pulsegrid"
    migration = "postgresql+psycopg://owner:secret@host:5432/pulsegrid"
    assert resolve_migration_database_url(runtime, migration, "production") == migration
