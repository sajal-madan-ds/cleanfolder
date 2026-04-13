"""OpenAI LLM provider (GPT-4o, GPT-4o-mini, etc.)."""

from __future__ import annotations

import os

from cleanfolder.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key_env: str = "OPENAI_API_KEY"):
        self._model = model
        self._api_key = os.environ.get(api_key_env, "")

    @property
    def name(self) -> str:
        return "openai"

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def complete(self, prompt: str, *, system: str = "") -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
