"""
Configuration module for the voice agent backend.
Handles environment variables and application settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
import os
import sys


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    deepgram_api_key: str = Field(..., validation_alias="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(..., validation_alias="ELEVENLABS_API_KEY")
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    
    # LiveKit Configuration - Remote Server
    livekit_url: str = Field(default="wss://ws.42voice.com", validation_alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="devkey", validation_alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="secret", validation_alias="LIVEKIT_API_SECRET")
    
    # Twilio SIP Configuration
    twilio_sip_username: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_USERNAME")
    twilio_sip_password: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_PASSWORD")
    twilio_account_sid: Optional[str] = Field(default=None, validation_alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, validation_alias="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, validation_alias="TWILIO_PHONE_NUMBER")
    twilio_sip_trunk_id: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_TRUNK_ID")
    twilio_sip_domain: Optional[str] = Field(default=None, validation_alias="TWILIO_SIP_DOMAIN")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    reload: bool = Field(default=True, validation_alias="RELOAD")
    
    # Deepgram Configuration
    deepgram_stt_model: str = Field(default="nova-2", validation_alias="DEEPGRAM_STT_MODEL")
    deepgram_stt_language: str = Field(default="en-US", validation_alias="DEEPGRAM_STT_LANGUAGE")
    
    # ElevenLabs Configuration
    elevenlabs_tts_model: str = Field(default="eleven_multilingual_v2", validation_alias="ELEVENLABS_TTS_MODEL")
    elevenlabs_tts_voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", validation_alias="ELEVENLABS_TTS_VOICE_ID")
    elevenlabs_tts_language: str = Field(default="en", validation_alias="ELEVENLABS_TTS_LANGUAGE")
    
    # OpenAI Configuration
    openai_model: str = Field(default="gpt-4-turbo", validation_alias="OPENAI_MODEL")
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
    aws_region: str = Field(default="ap-southeast-1", validation_alias="AWS_REGION")
    s3_bucket_name: str = Field(..., validation_alias="S3_BUCKET_NAME")
    s3_bucket_path: str = Field(default="recordings/", validation_alias="S3_BUCKET_PATH")
    
    # Transcript Configuration
    enable_transcripts: bool = Field(default=True, validation_alias="ENABLE_TRANSCRIPTS")
    transcript_language: str = Field(default="en", validation_alias="TRANSCRIPT_LANGUAGE")
    transcript_summary_enabled: bool = Field(default=True, validation_alias="TRANSCRIPT_SUMMARY_ENABLED")
    
    # Recording Configuration
    enable_recording: bool = Field(default=True, validation_alias="ENABLE_RECORDING")
    
    # Backend Server Configuration
    backend_url: str = Field(default="http://localhost:5000/api/v1", validation_alias="BACKEND_URL")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")
    
    # Database Configuration (integrated from Express)
    pghost: str = Field(default="db.tmjrutymtgvppnjowkih.supabase.co", validation_alias="PGHOST")
    pgport: int = Field(default=5432, validation_alias="PGPORT")
    pgdatabase: str = Field(default="postgres", validation_alias="PGDATABASE")
    pguser: str = Field(default="postgres", validation_alias="PGUSER")
    pgpassword: str = Field(default="Loke@9381408134", validation_alias="PGPASSWORD")
    pgmax_connections: int = Field(default=20, validation_alias="PGMAX_CONNECTIONS")

    # JWT Settings (integrated from Express)
    jwt_access_secret: str = Field(default="dev_access_secret_key_987654321_abcdefghijklmnopqrstuvwxyz", validation_alias="JWT_ACCESS_SECRET")
    jwt_access_expiry: str = Field(default="15m", validation_alias="JWT_ACCESS_EXPIRY")
    jwt_refresh_secret: str = Field(default="dev_refresh_secret_key_123456789_zyxwvutsrqponmlkjihgfedcba", validation_alias="JWT_REFRESH_SECRET")
    jwt_refresh_expiry: str = Field(default="7d", validation_alias="JWT_REFRESH_EXPIRY")

    # Cryptography & Security
    bcrypt_salt_rounds: int = Field(default=12, validation_alias="BCRYPT_SALT_ROUNDS")

    # Rate Limiting
    rate_limit_window_ms: int = Field(default=900000, validation_alias="RATE_LIMIT_WINDOW_MS")
    rate_limit_max: int = Field(default=100, validation_alias="RATE_LIMIT_MAX")

    # Stripe Configuration
    stripe_secret_key: str = Field(default="sk_test_mock", validation_alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str = Field(default="pk_test_mock", validation_alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: str = Field(default="whsec_mock", validation_alias="STRIPE_WEBHOOK_SECRET")

    # SMTP Configuration (integrated from Express)
    smtp_host: Optional[str] = Field(default="smtp.mailtrap.io", validation_alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=2525, validation_alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default="mock", validation_alias="SMTP_USER")
    smtp_pass: Optional[str] = Field(default="mock", validation_alias="SMTP_PASS")
    smtp_from: str = Field(default="noreply@42voice.com", validation_alias="SMTP_FROM")

    # Agent Configuration
    agent_names: Optional[str] = Field(default="Voice Agent", validation_alias="AGENT_NAMES")
    
    # Fallback Media Configuration
    fallback_audio_url: str = Field(default="https://www.w3schools.com/html/horse.mp3", validation_alias="FALLBACK_AUDIO_URL")

    # Calendly Integration Settings
    calendly_client_id: Optional[str] = Field(default=None, validation_alias="CALENDLY_CLIENT_ID")
    calendly_client_secret: Optional[str] = Field(default=None, validation_alias="CALENDLY_CLIENT_SECRET")
    calendly_redirect_uri: Optional[str] = Field(default=None, validation_alias="CALENDLY_REDIRECT_URI")
    calendly_encryption_key: Optional[str] = Field(default=None, validation_alias="CALENDLY_ENCRYPTION_KEY")
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
