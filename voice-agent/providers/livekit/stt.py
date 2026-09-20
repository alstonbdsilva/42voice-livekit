"""
LiveKit Deepgram STT provider adapter.
"""
import logging
from typing import Any, Optional
from livekit.plugins import deepgram
from providers.base import BaseProviderFactory
from providers.types import ProviderCapability, ResolvedProviderConfig
from providers.errors import ProviderConfigError, ProviderInitError

logger = logging.getLogger("voice-agent.providers.livekit.stt")

# Safe allowlisted options for Deepgram STT
ALLOWED_DEEPGRAM_OPTIONS = {
    "model",
    "language",
    "smart_format",
    "interim_results",
    "punctuate",
    "endpointing_ms",
    "filler_words",
    "keywords",
}


class LiveKitDeepgramSTTFactory(BaseProviderFactory):
    @property
    def capability(self) -> ProviderCapability:
        return ProviderCapability.STT

    @property
    def provider(self) -> str:
        return "deepgram"

    def create(
        self,
        config: ResolvedProviderConfig,
        api_key: Optional[str] = None,
        runtime_options: Optional[dict] = None
    ) -> Any:
        # Default options aligned with existing production baseline
        stt_kwargs: dict = {
            "model": config.model or "nova-2-phonecall",
            "language": "en-US",
            "smart_format": True,
            "interim_results": True,
        }

        # Apply safe options from config
        if config.safe_options:
            for k, v in config.safe_options.items():
                if k in ALLOWED_DEEPGRAM_OPTIONS and v is not None:
                    stt_kwargs[k] = v

        # Apply runtime call-level options (e.g. dynamic STT keyword hints)
        if runtime_options:
            if "keywords" in runtime_options and runtime_options["keywords"]:
                stt_kwargs["keywords"] = runtime_options["keywords"]
            if "language" in runtime_options and runtime_options["language"]:
                stt_kwargs["language"] = runtime_options["language"]

        # Pass explicit API key if provided
        if api_key:
            stt_kwargs["api_key"] = api_key

        try:
            return deepgram.STT(**stt_kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize Deepgram STT: {e}")
            raise ProviderInitError(provider=self.provider, capability=self.capability.value, reason=str(e)) from e
