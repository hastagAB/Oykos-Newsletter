"""Tests for LLM client - S017.

The blueprint mandates the Responses API with Structured Outputs, so these
tests mock ``/v1/responses`` rather than chat completions.
"""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response
from pydantic import BaseModel

from oykos.config import Settings
from oykos.llm.client import LLMClient, StructuredOutputError

RESPONSES_URL = r"https://api\.openai\.com/v1/responses"


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        openai_api_key="sk-test-key",
        smtp_username="test@example.it",
        smtp_password="test-pass",
        openai_max_retries=0,
        _env_file=None,
    )  # type: ignore[call-arg]


def _mock_response(text: str) -> dict:
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": "completed",
        "model": "gpt-5.4",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            },
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }


def _mock_empty_response() -> dict:
    payload = _mock_response("")
    payload["output"] = []
    return payload


class SampleModel(BaseModel):
    name: str
    value: int


@pytest.mark.asyncio
@respx.mock
async def test_complete_uses_responses_api() -> None:
    route = respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_response("Hello world")),
    )

    client = LLMClient(_make_settings())
    result = await client.complete("Say hello")

    assert result == "Hello world"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_complete_structured_parses_schema() -> None:
    respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_response(json.dumps({"name": "test", "value": 42}))),
    )

    client = LLMClient(_make_settings())
    result = await client.complete_structured("Get data", SampleModel)

    assert result.name == "test"
    assert result.value == 42


@pytest.mark.asyncio
@respx.mock
async def test_complete_structured_sends_strict_json_schema() -> None:
    """Structured Outputs must be enforced server side, not by prompt text."""
    route = respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_response(json.dumps({"name": "a", "value": 1}))),
    )

    client = LLMClient(_make_settings())
    await client.complete_structured("Get data", SampleModel)

    body = json.loads(route.calls[0].request.content)
    text_format = body["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert "value" in text_format["schema"]["properties"]


@pytest.mark.asyncio
@respx.mock
async def test_complete_structured_raises_when_nothing_parsed() -> None:
    respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_empty_response()),
    )

    client = LLMClient(_make_settings())
    with pytest.raises(StructuredOutputError):
        await client.complete_structured("Get data", SampleModel)


@pytest.mark.asyncio
@respx.mock
async def test_triage_uses_triage_model() -> None:
    route = respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_response("category_a")),
    )

    client = LLMClient(_make_settings())
    result = await client.triage("Classify this")

    assert result == "category_a"
    assert json.loads(route.calls[0].request.content)["model"] == "gpt-5-mini"


@pytest.mark.asyncio
@respx.mock
async def test_triage_structured_uses_triage_model() -> None:
    route = respx.post(url__regex=RESPONSES_URL).mock(
        return_value=Response(200, json=_mock_response(json.dumps({"name": "x", "value": 3}))),
    )

    client = LLMClient(_make_settings())
    result = await client.triage_structured("Classify", SampleModel)

    assert result.value == 3
    assert json.loads(route.calls[0].request.content)["model"] == "gpt-5-mini"
