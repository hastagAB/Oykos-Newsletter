"""Application configuration via pydantic-settings - S001."""
from __future__ import annotations

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str

    # OpenAI
    openai_api_key: SecretStr
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    openai_triage_model: str = "gpt-4o-mini"

    # Email / Gmail SMTP
    gmail_address: str
    gmail_app_password: SecretStr
    sender_email: str = ""
    recipient_emails: str = ""

    # Newsletter
    newsletter_title: str = "L'Essenziale in Pediatria"
    max_newsletter_items: int = 12
    italy_ratio: float = 0.7

    # Subscriber management
    base_url: str = "http://localhost:8000"

    # Healthcheck
    healthcheck_ping_url: str = ""

    # A/B testing
    ab_test_percent: int = 10

    # App
    log_level: str = "INFO"
    preview_mode: bool = False

    @field_validator("recipient_emails", mode="before")
    @classmethod
    def _strip_recipients(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @property
    def resolved_sender(self) -> str:
        return self.sender_email or self.gmail_address

    @property
    def recipient_list(self) -> list[str]:
        if not self.recipient_emails:
            return []
        return [e.strip() for e in self.recipient_emails.split(",") if e.strip()]
