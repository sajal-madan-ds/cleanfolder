"""LLM router — picks the right provider based on config and availability."""

from __future__ import annotations

from cleanfolder.llm.base import LLMProvider
from cleanfolder.llm.openai_llm import OpenAIProvider
from cleanfolder.llm.anthropic_llm import AnthropicProvider
from cleanfolder.llm.ollama_llm import OllamaProvider
from cleanfolder.llm.vllm_llm import VLLMProvider


_PROVIDER_FACTORIES: dict[str, type] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "vllm": VLLMProvider,
}


def build_provider(name: str, cfg: dict) -> LLMProvider:
    """Instantiate a single provider from its config section."""
    factory = _PROVIDER_FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"Unknown LLM provider: {name!r}. Available: {list(_PROVIDER_FACTORIES)}")

    provider_cfg = cfg.get("llm", {}).get(name, {})
    kwargs: dict = {}

    if "model" in provider_cfg:
        kwargs["model"] = provider_cfg["model"]
    if "api_key_env" in provider_cfg:
        kwargs["api_key_env"] = provider_cfg["api_key_env"]
    if "base_url" in provider_cfg:
        kwargs["base_url"] = provider_cfg["base_url"]

    return factory(**kwargs)


async def get_provider(cfg: dict, *, preferred: str | None = None) -> LLMProvider:
    """
    Return the first available provider.

    Tries *preferred* first (if given), then walks the fallback_order from config.
    Raises RuntimeError if nothing is available.
    """
    llm_cfg = cfg.get("llm", {})
    fallback_order: list[str] = llm_cfg.get("fallback_order", ["openai", "anthropic", "ollama", "vllm"])

    if preferred:
        order = [preferred] + [p for p in fallback_order if p != preferred]
    else:
        default = llm_cfg.get("default_provider", fallback_order[0])
        order = [default] + [p for p in fallback_order if p != default]

    for name in order:
        try:
            provider = build_provider(name, cfg)
            if await provider.is_available():
                return provider
        except Exception:
            continue

    raise RuntimeError(
        "No LLM provider is available. Configure at least one in config.yaml or set the "
        "appropriate environment variable (e.g. OPENAI_API_KEY)."
    )
