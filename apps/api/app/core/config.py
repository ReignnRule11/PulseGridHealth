from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")
    database_url: str
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

settings = Settings()
