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
