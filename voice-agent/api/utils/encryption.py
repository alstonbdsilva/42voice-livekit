import logging
from cryptography.fernet import Fernet
from config import get_settings

logger = logging.getLogger("voice-agent.api.utils.encryption")

class TokenEncryptor:
    def __init__(self):
        settings = get_settings()
        self.key = settings.calendly_encryption_key
        
        key_str = self.key
        if not key_str:
            logger.warning("CALENDLY_ENCRYPTION_KEY is not configured. Falling back to temporary key.")
            # Generate a temporary key for safety (though not persistent across restarts)
            key_str = Fernet.generate_key().decode()
            self.key = key_str
            
        try:
            self.cipher = Fernet(key_str.encode())
        except Exception as e:
            logger.error(f"Failed to initialize encryption cipher: {e}. Generating new key.")
            self.cipher = Fernet(Fernet.generate_key())

    def encrypt(self, plain_text: str) -> str:
        """Encrypt plain text to secure cipher token."""
        if not plain_text:
            return ""
        try:
            return self.cipher.encrypt(plain_text.encode()).decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise RuntimeError("Cryptographic encryption failure") from e

    def decrypt(self, cipher_text: str) -> str:
        """Decrypt cipher token back to plain text."""
        if not cipher_text:
            return ""
        try:
            return self.cipher.decrypt(cipher_text.encode()).decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise RuntimeError("Cryptographic decryption failure") from e

# Global single-instance helper
token_encryptor = TokenEncryptor()
