from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")
    database_url: str
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 5
    min_baseline_points: int = 6
    anomaly_z_threshold: float = 3.5

settings = Settings()
