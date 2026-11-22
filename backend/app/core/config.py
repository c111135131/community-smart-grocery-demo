"""Application settings loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root is three levels above this file (backend/app/core/config.py).
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Runtime settings. Defaults match .env.example for local demo use."""

    database_url: str = (
        "postgresql+psycopg://grocery:grocery_demo_pw@localhost:5432/community_grocery"
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Demo key for the educational hash-table check code. NOT a real secret and
    # NOT cryptographic security (see docs/IOT_PROTOCOL.md section 5).
    iot_secret_key: str = "demo-secret-not-for-production"

    # --- AI service (docs/ARCHITECTURE.md, Layer 4). Mock provider works with no key. ---
    ai_provider: str = "mock"  # "mock" (default) or "anthropic"
    anthropic_api_key: str = ""  # only read when ai_provider == "anthropic"; never log it
    ai_model: str = ""  # model id for the real provider; required when it is enabled
    ai_timeout_seconds: float = 20.0
    knowledge_base_path: str = ""  # empty -> <repo>/knowledge_base/nutrition_seed.json

    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")

    @property
    def knowledge_base_file(self) -> Path:
        if self.knowledge_base_path:
            return Path(self.knowledge_base_path)
        return _ROOT_ENV.parent / "knowledge_base" / "nutrition_seed.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
