"""Global safety checks for destructive integration-test database fixtures."""

import os

import pytest
from sqlalchemy.engine import make_url


LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}
TEST_DATABASE_SUFFIXES = ("_test", "-test", "_e2e", "-e2e")


def validate_test_database_url(raw_database_url: str, app_env: str) -> None:
    """Reject PostgreSQL targets that are not explicitly local test databases."""
    try:
        database_url = make_url(raw_database_url)
    except Exception as exc:
        raise pytest.UsageError(
            "DATABASE_URL is not a valid SQLAlchemy URL; refusing to start tests."
        ) from exc

    if not database_url.drivername.startswith("postgresql"):
        return

    hostname = (database_url.host or "").lower()
    if hostname not in LOCAL_DATABASE_HOSTS:
        raise pytest.UsageError(
            "PostgreSQL test runs must use a loopback database host "
            "(localhost, 127.0.0.1, or ::1). Refusing to run destructive fixtures."
        )

    if app_env.strip().lower() != "test":
        raise pytest.UsageError(
            "PostgreSQL test runs require APP_ENV=test. Refusing to run destructive fixtures."
        )

    database_name = (database_url.database or "").lower()
    if not database_name.endswith(TEST_DATABASE_SUFFIXES):
        raise pytest.UsageError(
            "PostgreSQL test database name must end in _test, -test, _e2e, or -e2e. "
            "Refusing to run destructive fixtures."
        )


def pytest_sessionstart(session):
    """Use isolated SQLite by default; guard any explicitly configured PostgreSQL target."""
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_database_url:
        # Environment variables override .env values in Pydantic Settings. This prevents
        # a developer's local .env database URL from becoming the implicit test target.
        os.environ["DATABASE_URL"] = "sqlite://"
        os.environ.setdefault("APP_ENV", "test")
        return

    validate_test_database_url(raw_database_url, os.getenv("APP_ENV", ""))
