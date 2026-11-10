import os

import pytest

from conftest import pytest_sessionstart, validate_test_database_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://user:pass@localhost:5432/pulsegrid_test",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/pulsegrid-e2e",
        "postgresql+psycopg://user:pass@[::1]:5432/pulsegrid_test",
    ],
)
def test_local_postgres_test_databases_are_allowed(url):
    validate_test_database_url(url, "test")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://user:pass@db.example.com:5432/pulsegrid_test",
        "postgresql+psycopg://user:pass@10.0.0.5:5432/pulsegrid_test",
        "postgresql+psycopg://user:pass@localhost:5432/pulsegrid",
    ],
)
def test_unsafe_postgres_targets_are_rejected(url):
    with pytest.raises(pytest.UsageError):
        validate_test_database_url(url, "test")


def test_postgres_requires_test_environment():
    with pytest.raises(pytest.UsageError, match="APP_ENV=test"):
        validate_test_database_url(
            "postgresql+psycopg://user:pass@localhost:5432/pulsegrid_test",
            "development",
        )


def test_missing_database_url_forces_sqlite_and_test_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    pytest_sessionstart(None)

    assert os.environ["DATABASE_URL"] == "sqlite://"
    assert os.environ["APP_ENV"] == "test"
