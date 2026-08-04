"""OpenAI client wrapper - S017.

Schema-first by construction: every structured call goes through the Responses
API with a strict JSON schema derived from a Pydantic model, so the model cannot
return a shape the pipeline is not prepared to handle (blueprint Section 8/9).
"""
from __future__ import annotations

import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from oykos.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MAX_OUTPUT_TOKENS = 2000
STRUCTURED_MAX_OUTPUT_TOKENS = 4000
TRIAGE_MAX_OUTPUT_TOKENS = 500


class StructuredOutputError(RuntimeError):
    """The model returned no parseable object for the requested schema."""


class LLMClient:
    """Async OpenAI client wrapper built on the Responses API."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
        self._model = settings.openai_model
        self._triage_model = settings.openai_triage_model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> str:
        """Send a request and return the plain text response."""
        response = await self._client.responses.create(
            model=model or self._model,
            instructions=system or None,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
        return (response.output_text or "").strip()

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        model: str | None = None,
        max_output_tokens: int = STRUCTURED_MAX_OUTPUT_TOKENS,
    ) -> T:
        """Send a request and get back a validated instance of ``response_model``.

        Uses OpenAI Structured Outputs: the schema is enforced server side, so
        there is no markdown fence stripping or best-effort JSON repair here.
        """
        response = await self._client.responses.parse(
            model=model or self._model,
            instructions=system or None,
            input=prompt,
            text_format=response_model,
            max_output_tokens=max_output_tokens,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise StructuredOutputError(
                f"Model returned no object matching {response_model.__name__}",
            )
        return parsed

    async def triage(self, prompt: str, system: str = "") -> str:
        """Use the cheaper triage model for quick classification tasks."""
        return await self.complete(
            prompt=prompt,
            system=system,
            model=self._triage_model,
            max_output_tokens=TRIAGE_MAX_OUTPUT_TOKENS,
        )

    async def triage_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
    ) -> T:
        """Structured classification on the economy model (blueprint: triage tier)."""
        return await self.complete_structured(
            prompt=prompt,
            response_model=response_model,
            system=system,
            model=self._triage_model,
        )
