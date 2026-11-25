"""Configuration management for Toko Indo Telur AI Service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    PORT: int = 8000
    BACKEND_BASE_URL: str = "http://localhost:3000"
    BACKEND_TIMEOUT_SECONDS: float = 5.0

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS: float = 15.0
    GEMINI_MAX_CALLS_PER_MINUTE: int = 30
    AI_SERVICE_API_KEY: str = ""

    LOW_STOCK_THRESHOLD: float = 5.0
    AUTO_REPLY_STOCK_ENABLED: bool = True
    USE_SAMPLE_PRODUCTS_FALLBACK: bool = True

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    MODEL_PATH: Path = BASE_DIR / "artifacts" / "intent_model.joblib"
    EVALUATION_REPORT_PATH: Path = BASE_DIR / "artifacts" / "evaluation_report.json"
    SAMPLE_PRODUCTS_PATH: Path = BASE_DIR / "data" / "sample_products.json"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def gemini_configured(self) -> bool:
        """Return True if a non-empty Gemini API key is configured."""
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())

    @property
    def backend_configured(self) -> bool:
        """Return True if a non-empty backend URL is configured."""
        return bool(self.BACKEND_BASE_URL and self.BACKEND_BASE_URL.strip())

    @property
    def api_key_auth_enabled(self) -> bool:
        """Return True if optional X-API-Key protection is enabled."""
        return bool(self.AI_SERVICE_API_KEY and self.AI_SERVICE_API_KEY.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()
