from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://agentstudio:agentstudio@localhost:5434/agentstudio"
    )
    default_tenant_id: str = "default_tenant"
    manifest_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4]
        / "agents"
        / "production-scheduling"
        / "manifest.yaml"
    )
    demo_data_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4]
        / "domains"
        / "manufacturing"
        / "printing"
        / "demo_data.json"
    )
    model_name: str | None = None
    model_api_key: SecretStr | None = None
    model_api_base: str | None = None
    cors_allow_origins: list[str] = ["http://localhost:3002"]

    @property
    def model_configured(self) -> bool:
        has_key = bool(
            self.model_api_key
            and self.model_api_key.get_secret_value().strip()
        )
        has_base = bool(self.model_api_base and self.model_api_base.strip())
        return bool(self.model_name and self.model_api_base and (has_key or has_base))


@lru_cache
def get_settings() -> Settings:
    return Settings()
