"""
Provider configuration resolver for call-level model resolution.
"""
import json
import logging
from typing import Any, Dict, Optional
from api import database
from providers.types import (
    RealtimeModelBundle,
    ProviderCapability,
    ResolvedProviderConfig,
    CredentialSource,
)
from providers.errors import ProviderConfigError
from providers.bundle import build_legacy_provider_configs, create_model_bundle
# Ensure LiveKit provider factories are registered
import providers.livekit

logger = logging.getLogger("voice-agent.providers.resolver")


class ProviderConfigurationResolver:
    """Resolves exact call-level model configurations and builds RealtimeModelBundle."""

    async def resolve_bundle_for_agent(
        self,
        agent_data: Optional[Dict[str, Any]] = None,
        client_id: Optional[str] = None,
        dynamic_stt_keywords: Optional[list] = None,
        stt_language: Optional[str] = None,
        voice_override: Optional[str] = None,
    ) -> RealtimeModelBundle:
        """
        Resolve call-level model configuration and instantiate provider instances once per call.
        
        Policy:
        - If platform_model_configuration_id is None -> use exact legacy/default configuration.
        - If platform_model_configuration_id is set -> resolve exact DB row (explicit failure on error, NO silent fallback).
        """
        config_id = None
        effective_client_id = client_id

        if agent_data and isinstance(agent_data, dict):
            config_id = agent_data.get("platform_model_configuration_id") or agent_data.get("platformModelConfigurationId")
            if not effective_client_id:
                effective_client_id = agent_data.get("client_id") or agent_data.get("clientId")

        # 1. Legacy / Unconfigured Path
        if not config_id:
            logger.info("[MODEL_RESOLVE] mode=legacy stt_provider=deepgram llm_provider=openai tts_provider=openai credential_source=platform")
            legacy_configs = build_legacy_provider_configs(agent_data)
            return await create_model_bundle(
                stt_config=legacy_configs["stt"],
                llm_config=legacy_configs["llm"],
                tts_config=legacy_configs["tts"],
                model_configuration_id=None,
                client_id=str(effective_client_id) if effective_client_id else None,
                dynamic_stt_keywords=dynamic_stt_keywords,
                stt_language=stt_language,
                voice_override=voice_override,
            )

        # 2. Configured Model Configuration Path
        logger.info(f"[MODEL_RESOLVE] resolving model_config_id={config_id} client_id={effective_client_id}")
        rows = await database.query(
            """
            SELECT id, client_id, user_id, name, description, status,
                   stt_provider, stt_model, stt_credential_source, stt_credential_id, stt_options,
                   llm_provider, llm_model, llm_credential_source, llm_credential_id, llm_options,
                   tts_provider, tts_model, tts_voice, tts_credential_source, tts_credential_id, tts_options
            FROM platform_model_configurations
            WHERE id = $1::uuid
            """,
            [str(config_id)]
        )

        if not rows:
            raise ProviderConfigError(f"Configured model configuration '{config_id}' was not found")

        cfg_row = rows[0]

        # Tenant ownership check
        row_client_id = str(cfg_row["client_id"]) if cfg_row.get("client_id") else None
        if effective_client_id and row_client_id and row_client_id != str(effective_client_id):
            raise ProviderConfigError(f"Model configuration '{config_id}' does not belong to tenant '{effective_client_id}'")

        # Status check
        if cfg_row.get("status") != "active":
            raise ProviderConfigError(f"Model configuration '{config_id}' is inactive")

        # Helper to parse json options
        def parse_json_options(raw: Any) -> Dict[str, Any]:
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {}
            return {}

        stt_opts = parse_json_options(cfg_row.get("stt_options"))
        llm_opts = parse_json_options(cfg_row.get("llm_options"))
        tts_opts = parse_json_options(cfg_row.get("tts_options"))

        stt_src = CredentialSource(cfg_row.get("stt_credential_source") or "platform")
        llm_src = CredentialSource(cfg_row.get("llm_credential_source") or "platform")
        tts_src = CredentialSource(cfg_row.get("tts_credential_source") or "platform")

        stt_cfg = ResolvedProviderConfig(
            capability=ProviderCapability.STT,
            provider=cfg_row.get("stt_provider", "deepgram"),
            model=cfg_row.get("stt_model"),
            credential_source=stt_src,
            credential_id=str(cfg_row["stt_credential_id"]) if cfg_row.get("stt_credential_id") else None,
            safe_options=stt_opts,
        )

        llm_cfg = ResolvedProviderConfig(
            capability=ProviderCapability.LLM,
            provider=cfg_row.get("llm_provider", "openai"),
            model=cfg_row.get("llm_model"),
            credential_source=llm_src,
            credential_id=str(cfg_row["llm_credential_id"]) if cfg_row.get("llm_credential_id") else None,
            safe_options=llm_opts,
        )

        tts_voice = cfg_row.get("tts_voice") or voice_override
        tts_cfg = ResolvedProviderConfig(
            capability=ProviderCapability.TTS,
            provider=cfg_row.get("tts_provider", "openai"),
            model=cfg_row.get("tts_model"),
            voice=tts_voice,
            credential_source=tts_src,
            credential_id=str(cfg_row["tts_credential_id"]) if cfg_row.get("tts_credential_id") else None,
            safe_options=tts_opts,
        )

        logger.info(
            f"[MODEL_RESOLVE] resolved model_config_id={config_id} "
            f"stt_provider={stt_cfg.provider} stt_source={stt_cfg.credential_source.value} "
            f"llm_provider={llm_cfg.provider} llm_source={llm_cfg.credential_source.value} "
            f"tts_provider={tts_cfg.provider} tts_source={tts_cfg.credential_source.value}"
        )

        return await create_model_bundle(
            stt_config=stt_cfg,
            llm_config=llm_cfg,
            tts_config=tts_cfg,
            model_configuration_id=str(config_id),
            client_id=str(effective_client_id) if effective_client_id else row_client_id,
            dynamic_stt_keywords=dynamic_stt_keywords,
            stt_language=stt_language,
            voice_override=voice_override,
        )


provider_resolver = ProviderConfigurationResolver()
