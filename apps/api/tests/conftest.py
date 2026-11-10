"""Global safety checks for destructive integration-test database fixtures."""

import os

import pytest
from sqlalchemy.engine import make_url


def pytest_sessionstart(session):
    """Refuse PostgreSQL test runs unless they target an explicitly named test DB."""
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_database_url:
        return

    try:
        database_url = make_url(raw_database_url)
    except Exception as exc:
        raise pytest.UsageError("DATABASE_URL is not a valid SQLAlchemy URL; refusing to start tests.") from exc

    if database_url.drivername.startswith("postgresql"):
        app_env = os.getenv("APP_ENV", "").strip().lower()
        database_name = (database_url.database or "").lower()
        if app_env != "test":
            raise pytest.UsageError(
                "PostgreSQL test runs require APP_ENV=test. Refusing to run destructive fixtures."
            )
        if not database_name.endswith(("_test", "-test", "_e2e", "-e2e")):
            raise pytest.UsageError(
                "PostgreSQL test database name must end in _test, -test, _e2e, or -e2e. "
                "Refusing to run destructive fixtures."
            )
