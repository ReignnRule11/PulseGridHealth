from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    database_url: str
    migration_database_url: str | None = None
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 5
    min_baseline_points: int = 6
    anomaly_z_threshold: float = 3.5
    min_workforce_cohort_size: int = 20
    bootstrap_token: str = ""
    session_ttl_hours: int = 12
    invitation_ttl_hours: int = 72
    ai_enabled: bool = False
    ai_provider_name: str = "openai_compatible"
    ai_api_base: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4.1-mini"
    ai_timeout_seconds: int = 20

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: str | None) -> str | None:
        """Normalize provider PostgreSQL URLs for the installed Psycopg 3 driver."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value


settings = Settings()



def resolve_migration_database_url(
    database_url: str,
    migration_database_url: str | None,
    app_env: str,
) -> str:
    """Resolve Alembic's URL and enforce a distinct DDL role in production."""
    if app_env.strip().lower() in {"production", "prod"}:
        if not migration_database_url:
            raise RuntimeError(
                "MIGRATION_DATABASE_URL is required in production; refusing to run "
                "Alembic with the restricted runtime DATABASE_URL."
            )

        runtime = make_url(database_url)
        migration = make_url(migration_database_url)
        if not runtime.drivername.startswith("postgresql") or not migration.drivername.startswith("postgresql"):
            raise RuntimeError("Production runtime and migration URLs must both target PostgreSQL.")
        if not runtime.username or not migration.username or runtime.username == migration.username:
            raise RuntimeError(
                "Production MIGRATION_DATABASE_URL must use a distinct database role "
                "from the runtime DATABASE_URL."
            )
        if not runtime.database or runtime.database != migration.database:
            raise RuntimeError(
                "Production runtime and migration URLs must target the same database."
            )

    return migration_database_url or database_url
