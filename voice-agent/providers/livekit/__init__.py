"""
LiveKit provider adapter registration.
"""
from providers.registry import provider_registry
from providers.livekit.stt import LiveKitDeepgramSTTFactory
from providers.livekit.llm import LiveKitOpenAILLMFactory
from providers.livekit.tts import LiveKitOpenAITTSFactory, LiveKitElevenLabsTTSFactory


def register_livekit_providers():
    """Register all supported LiveKit provider factories with the provider registry."""
    provider_registry.register(LiveKitDeepgramSTTFactory())
    provider_registry.register(LiveKitOpenAILLMFactory())
    provider_registry.register(LiveKitOpenAITTSFactory())
    provider_registry.register(LiveKitElevenLabsTTSFactory())


# Auto-register on import
register_livekit_providers()
