"""Tests for oykos.config - S001."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")

    from oykos.config import Settings

    s = Settings()  # type: ignore[call-arg]
    assert s.database_url == "sqlite+aiosqlite:///test.db"
    assert s.openai_api_key.get_secret_value() == "sk-test-key"
    assert s.gmail_address == "test@gmail.com"


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-pass")

    from oykos.config import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.openai_model == "gpt-4o"
    assert s.openai_triage_model == "gpt-4o-mini"
    assert s.log_level == "INFO"
    assert s.newsletter_title == "L'Essenziale in Pediatria"
    assert s.max_newsletter_items == 12
    assert s.italy_ratio == 0.7


def test_config_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    from oykos.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_config_recipient_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-pass")
    monkeypatch.setenv("RECIPIENT_EMAILS", "a@b.it,c@d.it,e@f.it")

    from oykos.config import Settings

    s = Settings()  # type: ignore[call-arg]
    assert s.recipient_list == ["a@b.it", "c@d.it", "e@f.it"]


def test_config_empty_recipients_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-pass")
    monkeypatch.setenv("RECIPIENT_EMAILS", "")

    from oykos.config import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.recipient_list == []
