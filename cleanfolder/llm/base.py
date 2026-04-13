"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface that every LLM backend must implement."""

    @abstractmethod
    async def complete(self, prompt: str, *, system: str = "") -> str:
        """Send a prompt and return the model's text response."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this provider is reachable and configured."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'openai')."""
        ...
