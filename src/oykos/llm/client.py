"""OpenAI client wrapper - S017."""
from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from oykos.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async OpenAI client wrapper with structured output support."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
        )
        self._model = settings.openai_model
        self._triage_model = settings.openai_triage_model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Send a chat completion and return the text response."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=model or self._model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return content.strip()

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str = "",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        """Send a chat completion and parse the response as a Pydantic model."""
        schema = response_model.model_json_schema()
        system_with_schema = (
            f"{system}\n\nYou MUST respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```"
        )

        raw = await self.complete(
            prompt=prompt,
            system=system_with_schema,
            model=model,
            temperature=temperature,
            max_tokens=4000,
        )

        # Extract JSON from markdown code blocks if present
        cleaned = raw
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]

        data = json.loads(cleaned)
        return response_model.model_validate(data)

    async def triage(self, prompt: str, system: str = "") -> str:
        """Use the cheaper triage model for quick classification tasks."""
        return await self.complete(
            prompt=prompt,
            system=system,
            model=self._triage_model,
            temperature=0.1,
            max_tokens=500,
        )
