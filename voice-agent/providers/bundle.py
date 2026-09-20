"""
Model bundle builder and legacy default bundle constructor.
"""
import logging
from typing import Any, Dict, Optional
from providers.types import RealtimeModelBundle, ProviderCapability, ResolvedProviderConfig, CredentialSource
from providers.registry import provider_registry
from providers.credentials import credential_resolver

logger = logging.getLogger("voice-agent.providers.bundle")


def build_legacy_provider_configs(agent_data: Optional[Dict[str, Any]] = None) -> Dict[str, ResolvedProviderConfig]:
    """
    Build resolved provider configs representing current unconfigured/legacy baseline:
    - STT: deepgram (nova-2-phonecall, en-US)
    - LLM: openai (gpt-4o-mini)
    - TTS: openai (tts-1, alloy/voice from agent_data)
    """
    voice = "alloy"
    valid_openai_voices = {"alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"}
    if agent_data and isinstance(agent_data, dict):
        cand_voice = agent_data.get("voice_id") or agent_data.get("voice") or agent_data.get("voice_name") or agent_data.get("tts_voice")
        if cand_voice and isinstance(cand_voice, str) and cand_voice.lower() in valid_openai_voices:
            voice = cand_voice.lower()

    stt_cfg = ResolvedProviderConfig(
        capability=ProviderCapability.STT,
        provider="deepgram",
        model="nova-2-phonecall",
        credential_source=CredentialSource.PLATFORM,
        safe_options={"smart_format": True, "interim_results": True}
    )

    llm_cfg = ResolvedProviderConfig(
        capability=ProviderCapability.LLM,
        provider="openai",
        model="gpt-4o-mini",
        credential_source=CredentialSource.PLATFORM,
    )

    tts_cfg = ResolvedProviderConfig(
        capability=ProviderCapability.TTS,
        provider="openai",
        model="tts-1",
        voice=voice,
        credential_source=CredentialSource.PLATFORM,
        safe_options={"speed": 1.05}
    )

    return {"stt": stt_cfg, "llm": llm_cfg, "tts": tts_cfg}


async def create_model_bundle(
    stt_config: ResolvedProviderConfig,
    llm_config: ResolvedProviderConfig,
    tts_config: ResolvedProviderConfig,
    model_configuration_id: Optional[str] = None,
    client_id: Optional[str] = None,
    dynamic_stt_keywords: Optional[list] = None,
    stt_language: Optional[str] = None,
    voice_override: Optional[str] = None
) -> RealtimeModelBundle:
    """
    Instantiate model providers and construct RealtimeModelBundle.
    Secrets are resolved into ephemeral local memory and passed directly to constructors.
    """
    # 1. Resolve STT
    stt_key = await credential_resolver.resolve(
        credential_source=stt_config.credential_source,
        provider=stt_config.provider,
        credential_id=stt_config.credential_id,
        client_id=client_id
    )
    stt_runtime_opts: Dict[str, Any] = {}
    if dynamic_stt_keywords:
        stt_runtime_opts["keywords"] = dynamic_stt_keywords
    if stt_language:
        stt_runtime_opts["language"] = stt_language

    stt_instance = provider_registry.create(
        config=stt_config,
        api_key=stt_key,
        runtime_options=stt_runtime_opts
    )

    # 2. Resolve LLM
    llm_key = await credential_resolver.resolve(
        credential_source=llm_config.credential_source,
        provider=llm_config.provider,
        credential_id=llm_config.credential_id,
        client_id=client_id
    )
    llm_instance = provider_registry.create(
        config=llm_config,
        api_key=llm_key
    )

    # 3. Resolve TTS
    tts_key = await credential_resolver.resolve(
        credential_source=tts_config.credential_source,
        provider=tts_config.provider,
        credential_id=tts_config.credential_id,
        client_id=client_id
    )
    tts_runtime_opts: Dict[str, Any] = {}
    if voice_override:
        tts_runtime_opts["voice"] = voice_override

    tts_instance = provider_registry.create(
        config=tts_config,
        api_key=tts_key,
        runtime_options=tts_runtime_opts
    )

    return RealtimeModelBundle(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        model_configuration_id=model_configuration_id,
        stt_provider=stt_config.provider,
        stt_model=stt_config.model,
        stt_credential_source=stt_config.credential_source.value,
        llm_provider=llm_config.provider,
        llm_model=llm_config.model,
        llm_credential_source=llm_config.credential_source.value,
        tts_provider=tts_config.provider,
        tts_model=tts_config.model,
        tts_voice=tts_config.voice,
        tts_credential_source=tts_config.credential_source.value,
    )
