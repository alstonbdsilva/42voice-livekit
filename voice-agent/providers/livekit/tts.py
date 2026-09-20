"""
LiveKit OpenAI and ElevenLabs TTS provider adapters.
"""
import logging
from typing import Any, Optional
from livekit.plugins import openai
from providers.base import BaseProviderFactory
from providers.types import ProviderCapability, ResolvedProviderConfig
from providers.errors import ProviderConfigError, ProviderInitError

logger = logging.getLogger("voice-agent.providers.livekit.tts")

# Valid OpenAI voice set
VALID_OPENAI_VOICES = {
    "alloy", "ash", "ballad", "coral", "echo",
    "fable", "onyx", "nova", "sage", "shimmer"
}

ALLOWED_OPENAI_TTS_OPTIONS = {"model", "voice", "speed"}
ALLOWED_ELEVENLABS_TTS_OPTIONS = {"model", "voice_id", "language", "streaming_latency"}


class LiveKitOpenAITTSFactory(BaseProviderFactory):
    @property
    def capability(self) -> ProviderCapability:
        return ProviderCapability.TTS

    @property
    def provider(self) -> str:
        return "openai"

    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        voice = config.voice or "alloy"
        if runtime_options and "voice" in runtime_options and runtime_options["voice"]:
            voice = runtime_options["voice"]

        if voice.lower() in VALID_OPENAI_VOICES:
            voice = voice.lower()

        tts_kwargs: dict = {
            "model": config.model or "tts-1",
            "voice": voice,
            "speed": 1.05,
        }

        if config.safe_options:
            for k, v in config.safe_options.items():
                if k in ALLOWED_OPENAI_TTS_OPTIONS and v is not None:
                    if k == "speed":
                        tts_kwargs["speed"] = float(v)
                    elif k == "voice" and str(v).lower() in VALID_OPENAI_VOICES:
                        tts_kwargs["voice"] = str(v).lower()
                    else:
                        tts_kwargs[k] = v

        if api_key:
            tts_kwargs["api_key"] = api_key

        try:
            return openai.TTS(**tts_kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI TTS: {e}")
            raise ProviderInitError(provider=self.provider, capability=self.capability.value, reason=str(e)) from e


class LiveKitElevenLabsTTSFactory(BaseProviderFactory):
    @property
    def capability(self) -> ProviderCapability:
        return ProviderCapability.TTS

    @property
    def provider(self) -> str:
        return "elevenlabs"

    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        try:
            from livekit.plugins import elevenlabs
        except ImportError as err:
            raise ProviderInitError(
                provider=self.provider,
                capability=self.capability.value,
                reason="livekit-plugins-elevenlabs package is not installed"
            ) from err

        voice_id = config.voice or "21m00Tcm4TlvDq8ikWAM"
        if runtime_options and "voice" in runtime_options and runtime_options["voice"]:
            voice_id = runtime_options["voice"]

        tts_kwargs: dict = {
            "model": config.model or "eleven_multilingual_v2",
            "voice_id": voice_id,
        }

        if config.safe_options:
            for k, v in config.safe_options.items():
                if k in ALLOWED_ELEVENLABS_TTS_OPTIONS and v is not None:
                    tts_kwargs[k] = v

        if api_key:
            tts_kwargs["api_key"] = api_key

        try:
            return elevenlabs.TTS(**tts_kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs TTS: {e}")
            raise ProviderInitError(provider=self.provider, capability=self.capability.value, reason=str(e)) from e
