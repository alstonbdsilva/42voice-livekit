"""
Configuration module for the voice agent backend.
Handles environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
import sys


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    deepgram_api_key: str = Field(..., env="DEEPGRAM_API_KEY")
    elevenlabs_api_key: str = Field(..., env="ELEVENLABS_API_KEY")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # LiveKit Configuration - Remote Server
    livekit_url: str = Field(default="wss://ws.42voice.com", env="LIVEKIT_URL")
    livekit_api_key: str = Field(default="devkey", env="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="secret", env="LIVEKIT_API_SECRET")
    
    # Twilio SIP Configuration
    twilio_sip_username: Optional[str] = Field(default=None, env="TWILIO_SIP_USERNAME")
    twilio_sip_password: Optional[str] = Field(default=None, env="TWILIO_SIP_PASSWORD")
    twilio_account_sid: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    twilio_sip_trunk_id: Optional[str] = Field(default=None, env="TWILIO_SIP_TRUNK_ID")
    twilio_sip_domain: Optional[str] = Field(default=None, env="TWILIO_SIP_DOMAIN")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=True, env="RELOAD")
    
    # Deepgram Configuration
    deepgram_stt_model: str = Field(default="nova-2", env="DEEPGRAM_STT_MODEL")
    deepgram_stt_language: str = Field(default="hi", env="DEEPGRAM_STT_LANGUAGE")
    
    # ElevenLabs Configuration
    elevenlabs_tts_model: str = Field(default="eleven_multilingual_v2", env="ELEVENLABS_TTS_MODEL")
    elevenlabs_tts_voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", env="ELEVENLABS_TTS_VOICE_ID")
    elevenlabs_tts_language: str = Field(default="hi", env="ELEVENLABS_TTS_LANGUAGE")
    
    # OpenAI Configuration
    openai_model: str = Field(default="gpt-4-turbo", env="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=1024, env="OPENAI_MAX_TOKENS")
    
    # Session Configuration
    session_timeout: int = Field(default=3600, env="SESSION_TIMEOUT")  # 1 hour
    max_conversation_history: int = Field(default=20, env="MAX_CONVERSATION_HISTORY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        # Get the directory where this config.py file is located
        _config_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(_config_dir, ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
