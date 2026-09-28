from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://agentstudio:agentstudio@localhost:5434/agentstudio"
    default_tenant_id: str = "default_tenant"
    manifest_path: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parents[4]
            / "agents"
            / "production-scheduling"
            / "manifest.yaml"
        )
    )
    agent_repository_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "agent-repository"
    )
    demo_data_path: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parents[4]
            / "domains"
            / "manufacturing"
            / "printing"
            / "demo_data.json"
        )
    )
    model_name: str | None = None
    model_provider: str | None = None
    model_api_key: SecretStr | None = None
    model_api_base: str | None = None
    anthropic_api_key: SecretStr | None = None
    erp_query_api_url: str | None = None
    erp_api_token: SecretStr | None = None
    credential_encryption_key: SecretStr | None = None
    cors_allow_origins: list[str] = ["http://localhost:3002"]

    @property
    def effective_model_provider(self) -> str:
        if self.model_provider and self.model_provider.strip():
            return self.model_provider.strip().lower()
        if self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip():
            return "anthropic"
        if (
            self.model_api_base
            and self.model_api_base.strip()
            and self.model_name
            and self.model_name.strip()
        ):
            return "openai-compatible"
        return "anthropic"

    @property
    def effective_model_name(self) -> str:
        if self.model_name and self.model_name.strip():
            return self.model_name.strip()
        if self.effective_model_provider == "anthropic":
            return "claude-sonnet-4-5"
        return ""

    @property
    def effective_model_api_key(self) -> SecretStr | None:
        if self.effective_model_provider == "anthropic":
            return self.anthropic_api_key or self.model_api_key
        return self.model_api_key

    @property
    def model_configured(self) -> bool:
        api_key = self.effective_model_api_key
        has_key = bool(api_key and api_key.get_secret_value().strip())
        if self.effective_model_provider == "anthropic":
            return has_key and bool(self.effective_model_name)
        if self.effective_model_provider != "openai-compatible":
            return False
        has_base = bool(self.model_api_base and self.model_api_base.strip())
        return bool(self.effective_model_name and has_base and (has_key or has_base))

    @property
    def erp_api_configured(self) -> bool:
        return bool(
            self.erp_query_api_url
            and self.erp_query_api_url.strip()
            and self.erp_api_token
            and self.erp_api_token.get_secret_value().strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
