"""
Base interface for provider factories.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from providers.types import ProviderCapability, ResolvedProviderConfig


class BaseProviderFactory(ABC):
    """Abstract factory for instantiating provider plugins."""

    @property
    @abstractmethod
    def capability(self) -> ProviderCapability:
        """The capability handled by this factory (STT, LLM, TTS)."""
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """The provider identifier (e.g., 'deepgram', 'openai', 'elevenlabs')."""
        pass

    @abstractmethod
    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        """
        Instantiate the provider plugin object.
        Runtime options can supply dynamic call-level context (e.g. STT keywords).
        """
        pass
