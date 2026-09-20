import logging
from typing import Optional
from cryptography.fernet import Fernet
from config import get_settings

logger = logging.getLogger("voice-agent.api.utils.encryption")


class TokenEncryptor:
    """Fernet symmetric token encryptor."""

    def __init__(self, key_override: Optional[str] = None, key_name: str = "CALENDLY_ENCRYPTION_KEY"):
        settings = get_settings()
        if key_override:
            key_str = key_override
        elif key_name == "PROVIDER_CREDENTIAL_ENCRYPTION_KEY":
            key_str = (
                getattr(settings, "provider_credential_encryption_key", None)
                or getattr(settings, "external_credentials_encryption_key", None)
                or getattr(settings, "calendly_encryption_key", None)
            )
        else:
            key_str = getattr(settings, "calendly_encryption_key", None)

        self.key = key_str
        if not key_str:
            logger.warning(f"{key_name} is not configured. Falling back to temporary key.")
            # Generate a temporary key for safety (not persistent across restarts)
            key_str = Fernet.generate_key().decode()
            self.key = key_str

        try:
            self.cipher = Fernet(key_str.encode())
        except Exception as e:
            logger.error(f"Failed to initialize encryption cipher with provided key: {e}. Generating fallback key.")
            self.cipher = Fernet(Fernet.generate_key())

    def encrypt(self, plain_text: str) -> str:
        """Encrypt plain text to secure cipher token."""
        if not plain_text:
            return ""
        try:
            return self.cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise RuntimeError("Cryptographic encryption failure") from e

    def decrypt(self, cipher_text: str) -> str:
        """Decrypt cipher token back to plain text."""
        if not cipher_text:
            return ""
        try:
            return self.cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise RuntimeError("Cryptographic decryption failure") from e


# Global instances:
# 1. token_encryptor: for Calendly and legacy integrations (preserves full backward compatibility)
token_encryptor = TokenEncryptor(key_name="CALENDLY_ENCRYPTION_KEY")

# 2. provider_encryptor: dedicated for AI provider API keys
provider_encryptor = TokenEncryptor(key_name="PROVIDER_CREDENTIAL_ENCRYPTION_KEY")
