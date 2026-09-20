"""
LiveKit OpenAI LLM provider adapter.
"""
import logging
from typing import Any, Optional
from livekit.plugins import openai
from providers.base import BaseProviderFactory
from providers.types import ProviderCapability, ResolvedProviderConfig
from providers.errors import ProviderInitError

logger = logging.getLogger("voice-agent.providers.livekit.llm")

# Safe allowlisted options for OpenAI LLM
ALLOWED_OPENAI_OPTIONS = {
    "model",
    "temperature",
    "max_completion_tokens",
    "max_tokens",
}


class LiveKitOpenAILLMFactory(BaseProviderFactory):
    @property
    def capability(self) -> ProviderCapability:
        return ProviderCapability.LLM

    @property
    def provider(self) -> str:
        return "openai"

    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        llm_kwargs: dict = {
            "model": config.model or "gpt-4o-mini",
        }

        # Apply safe options from config
        if config.safe_options:
            for k, v in config.safe_options.items():
                if k in ALLOWED_OPENAI_OPTIONS and v is not None:
                    if k == "max_tokens":
                        llm_kwargs["max_completion_tokens"] = int(v)
                    elif k == "temperature":
                        llm_kwargs["temperature"] = float(v)
                    else:
                        llm_kwargs[k] = v

        if api_key:
            llm_kwargs["api_key"] = api_key

        try:
            return openai.LLM(**llm_kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI LLM: {e}")
            raise ProviderInitError(provider=self.provider, capability=self.capability.value, reason=str(e)) from e
