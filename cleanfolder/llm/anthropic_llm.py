"""Anthropic LLM provider (Claude models)."""

from __future__ import annotations

import os

from cleanfolder.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key_env: str = "ANTHROPIC_API_KEY"):
        self._model = model
        self._api_key = os.environ.get(api_key_env, "")

    @property
    def name(self) -> str:
        return "anthropic"

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def complete(self, prompt: str, *, system: str = "") -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system or "You are a helpful file organization assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
