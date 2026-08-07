"""Application configuration via pydantic-settings - S001."""
from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Accept both the field name and the aliases, so SMTP_USERNAME and the
        # legacy GMAIL_ADDRESS resolve to the same setting.
        populate_by_name=True,
    )

    # Database
    database_url: str

    # OpenAI - GPT-5.4 primary for editorial synthesis, GPT-5 mini for triage.
    openai_api_key: SecretStr
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.4"
    openai_triage_model: str = "gpt-5-mini"
    openai_timeout_seconds: float = 120.0
    openai_max_retries: int = 3

    # SMTP delivery. Defaults target Zoho Mail's EU data centre; the host must
    # match the data centre your Zoho account actually lives in:
    #   .com -> smtp.zoho.com      .eu  -> smtp.zoho.eu
    #   .in  -> smtp.zoho.in       .au  -> smtp.zoho.com.au
    #   .jp  -> smtp.zoho.jp       .ca  -> smtp.zohocloud.ca
    # Port 465 uses implicit SSL; port 587 uses STARTTLS.
    smtp_host: str = "smtp.zoho.eu"
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    smtp_username: str = Field(
        default="",
        validation_alias=AliasChoices("SMTP_USERNAME", "GMAIL_ADDRESS"),
    )
    smtp_password: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("SMTP_PASSWORD", "GMAIL_APP_PASSWORD"),
    )
    # Zoho rate limits both messages per connection and messages per hour. These
    # keep a large send inside those limits instead of getting throttled midway.
    smtp_throttle_seconds: float = 1.0
    smtp_max_per_connection: int = 50

    sender_email: str = ""
    recipient_emails: str = ""

    # Newsletter composition. No Italy/foreign quota: the editorial feedback of
    # 2026-08-07 requires every item to compete on relevance to PLS practice,
    # with Italian applicability weighted inside the score instead.
    newsletter_title: str = "L'Essenziale in Pediatria"
    max_newsletter_items: int = 4
    min_reading_minutes: int = 3
    max_reading_minutes: int = 5

    # Upcoming events for PLS (editorial feedback section 6).
    events_enabled: bool = True
    events_window_days: int = 30
    max_events: int = 4
    # 81 registry rows is too many for one weekly run; priority 1 always runs
    # and the rest rotate.
    max_event_sources_per_run: int = 28
    event_registry_path: str = ""

    # Trigger alerts: hard events only, capped per blueprint Section 5.
    max_alerts_per_month: int = 2

    # Editorial review. Without a token the review UI refuses to serve, so a
    # misconfigured deployment cannot accidentally expose it.
    review_token: SecretStr = SecretStr("")
    review_session_hours: int = 12
    # 0 disables auto-send: the issue waits for a human indefinitely, which is
    # the safe default for medical content.
    auto_send_after_hours: int = 0

    # WordPress publishing (oykomed.it). Uses an Application Password from
    # Users > Profile > Application Passwords - not the account password.
    wordpress_url: str = ""
    wordpress_user: str = ""
    wordpress_app_password: SecretStr = SecretStr("")
    wordpress_status: str = "publish"
    wordpress_category_id: int = 0

    # Closing call to action on every issue.
    cta_url: str = "https://oykomed.it"

    # Masthead logo. The oykomed.it default carries a build hash and will 404
    # when that site redeploys, so self-host it and point this at the copy.
    logo_url: str = "https://oykomed.it/_next/static/media/logo-sm.abbdf224.png"

    # Show issues that have not been sent yet on the public pages. Intended for
    # the pre-launch shakedown only: it exposes AI-drafted medical copy that no
    # editor has signed off, so those pages are served noindex. Turn it off
    # before the first real send.
    public_show_unsent: bool = False

    # Measurement (guidelines section 11). Click tracking links a subscriber to
    # what they read, so it is personal data: leave it off unless the privacy
    # notice covers it. Open rates are deliberately not tracked - Apple Mail
    # Privacy Protection makes them meaningless.
    click_tracking: bool = False
    # Signs tracked links. Separate from REVIEW_TOKEN because those links live in
    # inboxes for weeks: rotating the review secret must not break them.
    tracking_secret: SecretStr = SecretStr("")
    # Vary exactly one element per issue: none | subject | preheader | cta.
    ab_element: str = "none"

    @field_validator("ab_element")
    @classmethod
    def _known_ab_element(cls, value: str) -> str:
        allowed = {"none", "subject", "preheader", "cta"}
        if value not in allowed:
            msg = f"ab_element must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return value

    # Subscriber management
    base_url: str = "http://localhost:8000"
    unsubscribe_mailto: str = ""

    # Healthcheck
    healthcheck_ping_url: str = ""

    # App
    log_level: str = "INFO"
    preview_mode: bool = False

    @field_validator("recipient_emails", mode="before")
    @classmethod
    def _strip_recipients(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @property
    def resolved_sender(self) -> str:
        """The address messages are sent from.

        Zoho only accepts a From address that the authenticated account owns:
        the mailbox itself, a verified alias, or an address on a verified
        domain. Anything else is rejected at RCPT time.
        """
        return self.sender_email or self.smtp_username

    @property
    def recipient_list(self) -> list[str]:
        if not self.recipient_emails:
            return []
        return [e.strip() for e in self.recipient_emails.split(",") if e.strip()]

    @property
    def preferences_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/preferences"

    @property
    def event_registry(self) -> str:
        """Path to the PLS event source registry, packaged unless overridden."""
        if self.event_registry_path:
            return self.event_registry_path
        return str(Path(__file__).parent / "events" / "data" / "pls_event_sources.xlsx")

    @property
    def archive_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/archive"

    @property
    def privacy_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/privacy"

    @property
    def review_enabled(self) -> bool:
        """The review UI only serves when a token is configured."""
        return bool(self.review_token.get_secret_value())

    @property
    def wordpress_enabled(self) -> bool:
        return bool(
            self.wordpress_url
            and self.wordpress_user
            and self.wordpress_app_password.get_secret_value(),
        )

    @property
    def tracking_enabled(self) -> bool:
        """Tracking needs a signing secret; without one links would be forgeable."""
        return self.click_tracking and bool(self.tracking_secret.get_secret_value())

    def preferences_url_for(self, token: str) -> str:
        """Per-subscriber preferences link, keyed by their unsubscribe token."""
        return f"{self.base_url.rstrip('/')}/preferences/{token}"
