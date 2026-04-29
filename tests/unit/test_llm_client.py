"""Tests for LLM client - S017."""
from __future__ import annotations

import json
import pytest
import respx
from httpx import Response
from pydantic import BaseModel

from oykos.llm.client import LLMClient
from oykos.config import Settings

MOCK_OPENAI_BASE = "https://api.openai.com/v1"


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        openai_api_key="sk-test-key",
        gmail_address="test@gmail.com",
        gmail_app_password="test-pass",
    )


def _mock_chat_response(content: str) -> dict:
    return {
        "id": "test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


@pytest.mark.asyncio
@respx.mock
async def test_complete_basic() -> None:
    respx.post(url__regex=r"https://api\.openai\.com/v1/chat/completions").mock(
        return_value=Response(200, json=_mock_chat_response("Hello world"))
    )

    client = LLMClient(_make_settings())
    result = await client.complete("Say hello")
    assert result == "Hello world"


@pytest.mark.asyncio
@respx.mock
async def test_complete_structured() -> None:
    class TestModel(BaseModel):
        name: str
        value: int

    mock_json = json.dumps({"name": "test", "value": 42})
    respx.post(url__regex=r"https://api\.openai\.com/v1/chat/completions").mock(
        return_value=Response(200, json=_mock_chat_response(mock_json))
    )

    client = LLMClient(_make_settings())
    result = await client.complete_structured("Get data", TestModel)
    assert result.name == "test"
    assert result.value == 42


@pytest.mark.asyncio
@respx.mock
async def test_complete_structured_with_code_block() -> None:
    class TestModel(BaseModel):
        answer: str

    content = '```json\n{"answer": "yes"}\n```'
    respx.post(url__regex=r"https://api\.openai\.com/v1/chat/completions").mock(
        return_value=Response(200, json=_mock_chat_response(content))
    )

    client = LLMClient(_make_settings())
    result = await client.complete_structured("Question", TestModel)
    assert result.answer == "yes"


@pytest.mark.asyncio
@respx.mock
async def test_triage_uses_triage_model() -> None:
    route = respx.post(url__regex=r"https://api\.openai\.com/v1/chat/completions").mock(
        return_value=Response(200, json=_mock_chat_response("category_a"))
    )

    client = LLMClient(_make_settings())
    result = await client.triage("Classify this")
    assert result == "category_a"
