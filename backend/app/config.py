from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(ROOT_DIR / "backend" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Storage backend: "supabase" or "sqlite"
    storage_backend: str = "supabase"
    sqlite_path: str = str(ROOT_DIR / "backend" / "webdelta.dev.db")

    # Supabase
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_attachments_bucket: str = "attachments"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    # Playwright
    playwright_headless: bool = True
    page_timeout_ms: int = 30_000
    attachment_timeout_ms: int = 60_000


settings = Settings()

