"""
Explicit provider registry with allowlist validation.
"""
import logging
from typing import Dict, Optional, Tuple, Any
from providers.types import ProviderCapability, ResolvedProviderConfig
from providers.base import BaseProviderFactory
from providers.errors import UnsupportedProviderError

logger = logging.getLogger("voice-agent.providers.registry")


class ProviderRegistry:
    """Registry maintaining explicit allowlisted provider factories."""

    def __init__(self):
        self._factories: Dict[Tuple[str, str], BaseProviderFactory] = {}

    def register(self, factory: BaseProviderFactory) -> None:
        """Register a provider factory for its capability and provider name."""
        key = (factory.capability.value.lower(), factory.provider.lower())
        self._factories[key] = factory
        logger.debug(f"Registered provider factory: capability={factory.capability.value} provider={factory.provider}")

    def get(self, capability: ProviderCapability, provider: str) -> BaseProviderFactory:
        """Look up factory or raise UnsupportedProviderError."""
        cap_val = capability.value.lower() if isinstance(capability, ProviderCapability) else str(capability).lower()
        prov_val = provider.lower()
        key = (cap_val, prov_val)
        factory = self._factories.get(key)
        if not factory:
            raise UnsupportedProviderError(provider=provider, capability=cap_val)
        return factory

    def is_supported(self, capability: ProviderCapability, provider: str) -> bool:
        """Check if capability + provider combination is registered."""
        cap_val = capability.value.lower() if isinstance(capability, ProviderCapability) else str(capability).lower()
        prov_val = provider.lower()
        return (cap_val, prov_val) in self._factories

    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        """Create provider instance using registered factory."""
        factory = self.get(config.capability, config.provider)
        return factory.create(config, api_key=api_key, runtime_options=runtime_options)


provider_registry = ProviderRegistry()
