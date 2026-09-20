"""
Provider platform package.
"""
from providers.types import (
    ProviderCapability,
    CredentialSource,
    ProviderDescriptor,
    ResolvedProviderConfig,
    RealtimeModelBundle,
)
from providers.errors import (
    ProviderError,
    UnsupportedProviderError,
    ProviderConfigError,
    CredentialMissingError,
    CredentialInactiveError,
    CredentialTenantMismatchError,
    CredentialProviderMismatchError,
    CredentialDecryptionError,
    ProviderInitError,
    classify_provider_error,
)
from providers.base import BaseProviderFactory
from providers.registry import ProviderRegistry, provider_registry
from providers.credentials import CredentialResolver, credential_resolver, format_credential_hint
from providers.resolver import ProviderConfigurationResolver, provider_resolver
from providers.bundle import build_legacy_provider_configs, create_model_bundle

__all__ = [
    "ProviderCapability",
    "CredentialSource",
    "ProviderDescriptor",
    "ResolvedProviderConfig",
    "RealtimeModelBundle",
    "ProviderError",
    "UnsupportedProviderError",
    "ProviderConfigError",
    "CredentialMissingError",
    "CredentialInactiveError",
    "CredentialTenantMismatchError",
    "CredentialProviderMismatchError",
    "CredentialDecryptionError",
    "ProviderInitError",
    "classify_provider_error",
    "BaseProviderFactory",
    "ProviderRegistry",
    "provider_registry",
    "CredentialResolver",
    "credential_resolver",
    "format_credential_hint",
    "ProviderConfigurationResolver",
    "provider_resolver",
    "build_legacy_provider_configs",
    "create_model_bundle",
]
