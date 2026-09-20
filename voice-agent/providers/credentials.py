"""
Tenant-safe credential resolution and encryption utilities for provider API keys.
"""
import json
import logging
from typing import Any, Dict, Optional
from config import get_settings
from api import database
from api.utils.encryption import provider_encryptor
from providers.types import CredentialSource
from providers.errors import (
    CredentialMissingError,
    CredentialInactiveError,
    CredentialTenantMismatchError,
    CredentialProviderMismatchError,
    CredentialDecryptionError,
)

logger = logging.getLogger("voice-agent.providers.credentials")


def format_credential_hint(secret: str) -> str:
    """
    Format a safe key hint for UI/API responses.
    Never exposes enough characters to reconstruct the secret.
    Example: '****1234' or 'sk-...1234'
    """
    if not secret:
        return "****"
    s = str(secret).strip()
    if len(s) >= 8:
        return f"****{s[-4:]}"
    return "****"


class CredentialResolver:
    """Resolves and decrypts provider credentials with strict tenant isolation."""

    def __init__(self, encryptor=None):
        self.encryptor = encryptor or provider_encryptor

    def get_platform_key(self, provider: str) -> str:
        """Fetch server-managed platform API key for a provider."""
        settings = get_settings()
        prov_norm = provider.lower()

        if prov_norm == "deepgram":
            key = getattr(settings, "deepgram_api_key", None)
            if not key or key == "YOUR_DEEPGRAM_API_KEY":
                raise CredentialMissingError("Platform Deepgram API key is not configured")
            return key
        elif prov_norm == "openai":
            key = getattr(settings, "openai_api_key", None)
            if not key or key == "YOUR_OPENAI_API_KEY":
                raise CredentialMissingError("Platform OpenAI API key is not configured")
            return key
        elif prov_norm == "elevenlabs":
            key = getattr(settings, "elevenlabs_api_key", None)
            if not key or key == "YOUR_ELEVENLABS_API_KEY":
                raise CredentialMissingError("Platform ElevenLabs API key is not configured")
            return key
        else:
            raise CredentialMissingError(f"No platform key configured for provider '{provider}'")

    async def resolve(
        self,
        credential_source: CredentialSource,
        provider: str,
        credential_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> str:
        """
        Resolve plain API key string for runtime use.
        Plaintext exists only ephemerally in local memory.
        """
        if credential_source == CredentialSource.PLATFORM:
            return self.get_platform_key(provider)

        # BYO Credential Path
        if not credential_id:
            raise CredentialMissingError("BYO credential specified without credential_id")

        if not client_id:
            raise CredentialTenantMismatchError(credential_id=str(credential_id), client_id="unknown")

        # Query external_credentials by id (UUID) or credential_uuid
        rows = await database.query(
            """
            SELECT id, credential_uuid, client_id, name, credential_type, credential_data, is_active
            FROM external_credentials
            WHERE (id::text = $1 OR credential_uuid::text = $1)
            """,
            [str(credential_id)]
        )

        if not rows:
            raise CredentialMissingError(credential_id=str(credential_id))

        row = rows[0]

        # 1. Tenant ownership validation
        row_client_id = str(row["client_id"]) if row.get("client_id") else None
        if row_client_id != str(client_id):
            logger.error(f"[SECURITY] Tenant mismatch: caller={client_id} cred_owner={row_client_id} cred_id={credential_id}")
            raise CredentialTenantMismatchError(credential_id=str(credential_id), client_id=str(client_id))

        # 2. Active status check
        if not row.get("is_active", True):
            raise CredentialInactiveError(credential_id=str(credential_id))

        # 3. Parse credential data
        raw_data = row.get("credential_data") or {}
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception as e:
                raise CredentialDecryptionError(f"Corrupted credential data JSON: {e}")

        # 4. Verify provider type match
        cred_prov = raw_data.get("provider") or row.get("credential_type")
        if cred_prov and cred_prov.lower() not in (provider.lower(), "provider_api_key", "api_key"):
            if cred_prov.lower() != provider.lower():
                raise CredentialProviderMismatchError(expected_provider=provider, actual_provider=cred_prov)

        # 5. Extract and decrypt ciphertext
        ciphertext = raw_data.get("encrypted_api_key") or raw_data.get("api_key")
        if not ciphertext:
            raise CredentialMissingError(f"No encrypted key found in credential '{credential_id}'")

        try:
            plaintext = self.encryptor.decrypt(ciphertext)
            if not plaintext:
                raise CredentialDecryptionError("Decrypted secret is empty")
            return plaintext
        except Exception as decrypt_err:
            logger.error(f"Failed to decrypt credential {credential_id}: {decrypt_err}")
            raise CredentialDecryptionError(f"Decryption failure for credential '{credential_id}'") from decrypt_err


credential_resolver = CredentialResolver()
