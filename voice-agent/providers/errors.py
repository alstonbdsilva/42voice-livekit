"""
Provider platform exception classes and safe error classification.
"""
import logging
from typing import Any

logger = logging.getLogger("voice-agent.providers")


class ProviderError(Exception):
    """Base exception for provider platform errors."""
    def __init__(self, message: str, category: str = "provider_error"):
        super().__init__(message)
        self.message = message
        self.category = category


class UnsupportedProviderError(ProviderError):
    """Raised when an unknown or unsupported provider is requested."""
    def __init__(self, provider: str, capability: str):
        super().__init__(
            f"Unsupported provider '{provider}' for capability '{capability}'",
            category="unsupported_provider"
        )
        self.provider = provider
        self.capability = capability


class ProviderConfigError(ProviderError):
    """Raised when model configuration validation fails."""
    def __init__(self, message: str):
        super().__init__(message, category="invalid_configuration")


class CredentialMissingError(ProviderError):
    """Raised when a required BYO credential is not found."""
    def __init__(self, credential_id: str):
        super().__init__(f"Credential '{credential_id}' not found", category="credential_missing")


class CredentialInactiveError(ProviderError):
    """Raised when a referenced credential is inactive/disabled."""
    def __init__(self, credential_id: str):
        super().__init__(f"Credential '{credential_id}' is inactive", category="credential_inactive")


class CredentialTenantMismatchError(ProviderError):
    """Raised when a credential does not belong to the requesting tenant."""
    def __init__(self, credential_id: str, client_id: str):
        super().__init__(f"Credential '{credential_id}' does not belong to tenant", category="credential_tenant_mismatch")


class CredentialProviderMismatchError(ProviderError):
    """Raised when a credential provider type does not match the model provider."""
    def __init__(self, expected_provider: str, actual_provider: str):
        super().__init__(
            f"Credential provider '{actual_provider}' does not match expected '{expected_provider}'",
            category="credential_provider_mismatch"
        )


class CredentialDecryptionError(ProviderError):
    """Raised when decrypting a stored credential fails."""
    def __init__(self, message: str = "Failed to decrypt provider credential"):
        super().__init__(message, category="credential_decryption_failed")


class ProviderInitError(ProviderError):
    """Raised when provider initialization/instantiation fails."""
    def __init__(self, provider: str, capability: str, reason: str):
        super().__init__(
            f"Failed to initialize {provider} {capability}: {reason}",
            category="provider_initialization_failed"
        )


def classify_provider_error(error: Any, capability: str = "llm", provider: str = "openai") -> str:
    """
    Classify external AI provider errors cleanly without leaking credentials or raw data.
    """
    if isinstance(error, ProviderError):
        category = error.category
        logger.error(f"[PROVIDER_ERROR] capability={capability} provider={provider} category={category} reason={error.message}")
        return category

    err_str = str(error).lower()
    if any(q in err_str for q in ("429", "quota", "spend_limit", "rate_limit", "organization_spend_limit_exceeded")):
        logger.error(f"[PROVIDER_ERROR] capability={capability} provider={provider} category=quota_exceeded")
        return "quota_exceeded"
    elif any(a in err_str for a in ("401", "unauthorized", "invalid_api_key", "authentication", "forbidden", "403")):
        logger.error(f"[PROVIDER_ERROR] capability={capability} provider={provider} category=auth_failed")
        return "auth_failed"
    elif any(s in err_str for s in ("500", "502", "503", "504", "service_unavailable")):
        logger.error(f"[PROVIDER_ERROR] capability={capability} provider={provider} category=service_unavailable")
        return "service_unavailable"
    else:
        logger.error(f"[PROVIDER_ERROR] capability={capability} provider={provider} category=provider_error")
        return "provider_error"
