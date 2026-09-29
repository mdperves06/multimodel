from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "AI Control Center"
    environment: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_control_center"
    # "memory://" is an in-process Redis for local development and tests only.
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = ""
    encryption_key: str = ""
    cors_origins: str = "http://localhost:3000"

    access_token_minutes: int = 720
    cookie_name: str = "acc_session"
    trust_proxy: bool = False

    rate_limit_enabled: bool = True
    auth_rate_limit_per_minute: int = 10
    global_rate_limit_per_minute: int = 300

    storage_type: str = "local"  # local | s3 | r2
    storage_local_path: str = "./storage"
    storage_bucket: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""

    openai_base_url: str = "https://api.openai.com/v1"
    enable_mock_provider: bool = False
    embedded_worker: bool = False

    max_job_attempts: int = 5
    max_outputs_per_job: int = 10
    max_active_jobs_per_user: int = 50

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        try:
            Fernet(self.encryption_key.encode())
        except Exception as exc:
            raise ValueError(
                "ENCRYPTION_KEY must be a valid Fernet key. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
        if self.is_production:
            if self.redis_url.startswith("memory://"):
                raise ValueError("REDIS_URL=memory:// is not allowed in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed in production")
            if self.enable_mock_provider:
                raise ValueError("ENABLE_MOCK_PROVIDER is not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
