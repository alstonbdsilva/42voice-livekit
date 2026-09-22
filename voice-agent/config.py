"""
Configuration module for the voice agent backend.
Handles environment variables and application settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    deepgram_api_key: str = Field(..., validation_alias="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(..., validation_alias="ELEVENLABS_API_KEY")
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    
    # LiveKit Configuration
    livekit_url: str = Field(..., validation_alias="LIVEKIT_URL")
    livekit_public_url: Optional[str] = Field(default=None, validation_alias="LIVEKIT_PUBLIC_URL")
    livekit_api_key: str = Field(..., validation_alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(..., validation_alias="LIVEKIT_API_SECRET")
    livekit_agent_name: str = Field(default="inbound-agent", validation_alias="LIVEKIT_AGENT_NAME")
    livekit_sip_public_uri: Optional[str] = Field(default=None, validation_alias="LIVEKIT_SIP_PUBLIC_URI")
    
    # Twilio SIP Configuration
    twilio_sip_username: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_USERNAME")
    twilio_sip_password: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_PASSWORD")
    twilio_account_sid: Optional[str] = Field(default=None, validation_alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, validation_alias="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, validation_alias="TWILIO_PHONE_NUMBER")
    twilio_sip_trunk_id: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_TRUNK_ID")
    twilio_sip_domain: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_DOMAIN")
    
    # Server Configuration
    host: str = Field(..., validation_alias="HOST")
    port: int = Field(..., validation_alias="PORT")
    reload: bool = Field(default=True, validation_alias="RELOAD")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    
    # Deepgram Configuration
    deepgram_stt_model: str = Field(default="nova-2", validation_alias="DEEPGRAM_STT_MODEL")
    deepgram_stt_language: str = Field(default="en-US", validation_alias="DEEPGRAM_STT_LANGUAGE")
    
    # Cartesia API Key (Credential only - model and voice come from DB/UI agent configuration)
    cartesia_api_key: Optional[str] = Field(default=None, validation_alias="CARTESIA_API_KEY")
    
    # OpenAI Configuration (LLM only - TTS is provided by ElevenLabs/Cartesia)
    openai_model: str = Field(..., validation_alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, validation_alias="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=1024, validation_alias="OPENAI_MAX_TOKENS")
    
    # Session Configuration
    session_timeout: int = Field(default=3600, validation_alias="SESSION_TIMEOUT")  # 1 hour
    max_conversation_history: int = Field(default=20, validation_alias="MAX_CONVERSATION_HISTORY")
    
    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    
    # AWS S3 Configuration for Recording
    aws_access_key_id: str = Field(..., validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., validation_alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(..., validation_alias="AWS_REGION")
    s3_bucket_name: str = Field(..., validation_alias="S3_BUCKET_NAME")
    s3_bucket_path: str = Field(default="recordings/", validation_alias="S3_BUCKET_PATH")
    
    # Transcript Configuration
    enable_transcripts: bool = Field(default=True, validation_alias="ENABLE_TRANSCRIPTS")
    transcript_language: str = Field(default="en", validation_alias="TRANSCRIPT_LANGUAGE")
    transcript_summary_enabled: bool = Field(default=True, validation_alias="TRANSCRIPT_SUMMARY_ENABLED")
    
    # Recording Configuration
    enable_recording: bool = Field(default=True, validation_alias="ENABLE_RECORDING")
    
    # Backend & Frontend Server Configuration
    backend_url: str = Field(..., validation_alias="BACKEND_URL")
    frontend_url: str = Field(..., validation_alias="FRONTEND_URL")
    
    # Redis Configuration
    redis_url: str = Field(..., validation_alias="REDIS_URL")
    
    # Database Configuration (integrated from Express)
    pghost: str = Field(..., validation_alias="PGHOST")
    pgport: int = Field(..., validation_alias="PGPORT")
    pgdatabase: str = Field(..., validation_alias="PGDATABASE")
    pguser: str = Field(..., validation_alias="PGUSER")
    pgpassword: str = Field(..., validation_alias="PGPASSWORD")
    pgmax_connections: int = Field(default=20, validation_alias="PGMAX_CONNECTIONS")
    # Database TLS mode. One of: auto | disable | require | verify-full
    #  - auto: TLS with certificate verification in production; no TLS locally.
    #  - disable: never use TLS.
    #  - require: always use TLS with encryption but no certificate verification.
    #  - verify-full: always use TLS with full certificate verification.
    # Only an explicit operator-set "require" disables verification; the
    # production auto path never disables certificate checks.
    db_ssl_mode: str = Field(default="auto", validation_alias="DB_SSL_MODE")

    # Internal Service Authentication (trusted worker -> backend)
    # Shared secret used by the voice-agent worker to authenticate POST /conversations/register.
    # MUST be set in production (fail-closed): requests without a valid token are rejected.
    internal_worker_token: Optional[str] = Field(default=None, validation_alias="INTERNAL_WORKER_TOKEN")

    # JWT Settings (integrated from Express)
    jwt_access_secret: str = Field(..., validation_alias="JWT_ACCESS_SECRET")
    jwt_access_expiry: str = Field(default="15m", validation_alias="JWT_ACCESS_EXPIRY")
    jwt_refresh_secret: str = Field(..., validation_alias="JWT_REFRESH_SECRET")
    jwt_refresh_expiry: str = Field(default="7d", validation_alias="JWT_REFRESH_EXPIRY")

    # Cryptography & Security
    bcrypt_salt_rounds: int = Field(default=12, validation_alias="BCRYPT_SALT_ROUNDS")

    # Rate Limiting
    rate_limit_window_ms: int = Field(default=900000, validation_alias="RATE_LIMIT_WINDOW_MS")
    rate_limit_max: int = Field(default=100, validation_alias="RATE_LIMIT_MAX")

    # Stripe Configuration
    stripe_secret_key: Optional[str] = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(default=None, validation_alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")

    # SMTP Configuration (integrated from Express)
    smtp_host: Optional[str] = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=None, validation_alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, validation_alias="SMTP_USER")
    smtp_pass: Optional[str] = Field(default=None, validation_alias="SMTP_PASS")
    smtp_from: Optional[str] = Field(default=None, validation_alias="SMTP_FROM")

    # Agent Configuration
    agent_names: Optional[str] = Field(default=None, validation_alias="AGENT_NAMES")
    
    # Fallback Media Configuration
    fallback_audio_url: Optional[str] = Field(default=None, validation_alias="FALLBACK_AUDIO_URL")

    # Calendly Integration Settings
    calendly_client_id: Optional[str] = Field(default=None, validation_alias="CALENDLY_CLIENT_ID")
    calendly_client_secret: Optional[str] = Field(default=None, validation_alias="CALENDLY_CLIENT_SECRET")
    calendly_redirect_uri: Optional[str] = Field(default=None, validation_alias="CALENDLY_REDIRECT_URI")
    calendly_encryption_key: Optional[str] = Field(default=None, validation_alias="CALENDLY_ENCRYPTION_KEY")

    @field_validator('internal_worker_token', mode='after')
    @classmethod
    def validate_internal_worker_token(cls, v, info):
        """Fail closed outside development: the internal worker token is
        mandatory in any non-development environment so that the register
        endpoint is never left unauthenticated in production/staging."""
        from pydantic import ValidationInfo
        env = info.data.get('environment', 'development')
        if env != 'development' and not v:
            raise ValueError(
                'INTERNAL_WORKER_TOKEN must be set in environment '
                f"'{env}': the register endpoint is unauthenticated otherwise."
            )
        return v

    @field_validator('backend_url', mode='before')
    @classmethod
    def validate_backend_url(cls, v):
        """Fail fast if BACKEND_URL is missing or not a valid HTTP/HTTPS URL."""
        if not v:
            raise ValueError('BACKEND_URL must be set')
        parsed = urlparse(str(v))
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError(f'BACKEND_URL must be a valid HTTP/HTTPS URL, got: {v}')
        return v
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get the global settings instance."""
    load_dotenv(override=True)
    return Settings()
