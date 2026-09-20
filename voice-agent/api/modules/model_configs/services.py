"""
Model configuration service with validation and tenant isolation.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from api.modules.model_configs.repositories import ModelConfigRepository
from api.modules.model_configs.schemas import ModelConfigResponse
from api.utils.errors import BadRequestError, NotFoundError
from api import database

logger = logging.getLogger("voice-agent.api.model_configs.services")

SUPPORTED_PROVIDERS = {
    "stt": {"deepgram"},
    "llm": {"openai"},
    "tts": {"openai", "elevenlabs"},
}


class ModelConfigService:
    def __init__(self):
        self.repository = ModelConfigRepository()

    async def validate_credential_reference(
        self,
        capability: str,
        provider: str,
        credential_source: str,
        credential_id: Optional[str],
        client_id: str,
    ) -> None:
        """Validate referenced credential ownership, provider type, and active status."""
        if credential_source == "byo":
            if not credential_id:
                raise BadRequestError(
                    f"BYO credential source for {capability} requires a valid 'credential_id'",
                    "CREDENTIAL_REQUIRED"
                )
            # Verify credential exists and belongs to client
            rows = await database.query(
                """
                SELECT id, credential_uuid, client_id, credential_type, credential_data, is_active
                FROM external_credentials
                WHERE (id::text = $1 OR credential_uuid::text = $1)
                """,
                [str(credential_id)]
            )
            if not rows:
                raise NotFoundError(
                    f"Referenced credential '{credential_id}' was not found",
                    "CREDENTIAL_NOT_FOUND"
                )
            row = rows[0]
            if str(row.get("client_id")) != str(client_id):
                raise BadRequestError(
                    f"Credential '{credential_id}' does not belong to your organization",
                    "CREDENTIAL_TENANT_MISMATCH"
                )
            if not row.get("is_active", True):
                raise BadRequestError(
                    f"Credential '{credential_id}' is inactive/disabled",
                    "CREDENTIAL_INACTIVE"
                )
            raw_data = row.get("credential_data") or {}
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception:
                    raw_data = {}
            cred_prov = raw_data.get("provider") or row.get("credential_type")
            if cred_prov and cred_prov.lower() not in (provider.lower(), "provider_api_key", "api_key"):
                if cred_prov.lower() != provider.lower():
                    raise BadRequestError(
                        f"Credential is for provider '{cred_prov}', but {capability} requires '{provider}'",
                        "CREDENTIAL_PROVIDER_MISMATCH"
                    )

    def validate_providers(self, payload: Dict[str, Any]) -> None:
        """Validate that requested providers are in the supported allowlist."""
        stt_p = payload.get("stt_provider")
        if stt_p and stt_p.lower() not in SUPPORTED_PROVIDERS["stt"]:
            raise BadRequestError(
                f"Unsupported STT provider '{stt_p}'. Supported: {', '.join(SUPPORTED_PROVIDERS['stt'])}",
                "UNSUPPORTED_STT_PROVIDER"
            )

        llm_p = payload.get("llm_provider")
        if llm_p and llm_p.lower() not in SUPPORTED_PROVIDERS["llm"]:
            raise BadRequestError(
                f"Unsupported LLM provider '{llm_p}'. Supported: {', '.join(SUPPORTED_PROVIDERS['llm'])}",
                "UNSUPPORTED_LLM_PROVIDER"
            )

        tts_p = payload.get("tts_provider")
        if tts_p and tts_p.lower() not in SUPPORTED_PROVIDERS["tts"]:
            raise BadRequestError(
                f"Unsupported TTS provider '{tts_p}'. Supported: {', '.join(SUPPORTED_PROVIDERS['tts'])}",
                "UNSUPPORTED_TTS_PROVIDER"
            )

    async def list_model_configs(self, client_id: str) -> List[Dict[str, Any]]:
        rows = await self.repository.find_all(client_id)
        return [self.map_to_response(r) for r in rows]

    async def get_model_config(self, config_id: str, client_id: str) -> Dict[str, Any]:
        row = await self.repository.find_by_id(config_id, client_id)
        if not row:
            raise NotFoundError("Model configuration not found", "MODEL_CONFIG_NOT_FOUND")
        return self.map_to_response(row)

    async def create_model_config(
        self, payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required to create model configuration", "CLIENT_REQUIRED")

        self.validate_providers(payload)

        # Validate credential references
        await self.validate_credential_reference(
            "STT",
            payload.get("stt_provider", "deepgram"),
            payload.get("stt_credential_source", "platform"),
            payload.get("stt_credential_id"),
            client_id
        )
        await self.validate_credential_reference(
            "LLM",
            payload.get("llm_provider", "openai"),
            payload.get("llm_credential_source", "platform"),
            payload.get("llm_credential_id"),
            client_id
        )
        await self.validate_credential_reference(
            "TTS",
            payload.get("tts_provider", "openai"),
            payload.get("tts_credential_source", "platform"),
            payload.get("tts_credential_id"),
            client_id
        )

        data = dict(payload)
        data["client_id"] = client_id
        data["user_id"] = user_context.get("id")

        created = await self.repository.create(data)
        return self.map_to_response(created)

    async def update_model_config(
        self, config_id: str, payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required", "CLIENT_REQUIRED")

        existing = await self.repository.find_by_id(config_id, client_id)
        if not existing:
            raise NotFoundError("Model configuration not found", "MODEL_CONFIG_NOT_FOUND")

        self.validate_providers(payload)

        # Validate any updated credentials
        stt_p = payload.get("stt_provider", existing.get("stt_provider", "deepgram"))
        stt_src = payload.get("stt_credential_source", existing.get("stt_credential_source", "platform"))
        stt_cid = payload.get("stt_credential_id", existing.get("stt_credential_id"))
        await self.validate_credential_reference("STT", stt_p, stt_src, stt_cid, client_id)

        llm_p = payload.get("llm_provider", existing.get("llm_provider", "openai"))
        llm_src = payload.get("llm_credential_source", existing.get("llm_credential_source", "platform"))
        llm_cid = payload.get("llm_credential_id", existing.get("llm_credential_id"))
        await self.validate_credential_reference("LLM", llm_p, llm_src, llm_cid, client_id)

        tts_p = payload.get("tts_provider", existing.get("tts_provider", "openai"))
        tts_src = payload.get("tts_credential_source", existing.get("tts_credential_source", "platform"))
        tts_cid = payload.get("tts_credential_id", existing.get("tts_credential_id"))
        await self.validate_credential_reference("TTS", tts_p, tts_src, tts_cid, client_id)

        updated = await self.repository.update(config_id, payload, client_id)
        if not updated:
            raise NotFoundError("Model configuration not found", "MODEL_CONFIG_NOT_FOUND")
        return self.map_to_response(updated)

    async def delete_model_config(self, config_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required", "CLIENT_REQUIRED")

        deleted = await self.repository.delete(config_id, client_id)
        if not deleted:
            raise NotFoundError("Model configuration not found", "MODEL_CONFIG_NOT_FOUND")
        return {"status": "inactive", "id": config_id}

    def map_to_response(self, r: Dict[str, Any]) -> Dict[str, Any]:
        def parse_opts(val: Any) -> Dict[str, Any]:
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return {}
            return {}

        return {
            "id": str(r["id"]),
            "client_id": str(r["client_id"]),
            "user_id": str(r["user_id"]) if r.get("user_id") else None,
            "name": r["name"],
            "description": r.get("description"),
            "status": r.get("status", "active"),
            "stt_provider": r.get("stt_provider", "deepgram"),
            "stt_model": r.get("stt_model"),
            "stt_credential_source": r.get("stt_credential_source", "platform"),
            "stt_credential_id": str(r["stt_credential_id"]) if r.get("stt_credential_id") else None,
            "stt_options": parse_opts(r.get("stt_options")),
            "llm_provider": r.get("llm_provider", "openai"),
            "llm_model": r.get("llm_model"),
            "llm_credential_source": r.get("llm_credential_source", "platform"),
            "llm_credential_id": str(r["llm_credential_id"]) if r.get("llm_credential_id") else None,
            "llm_options": parse_opts(r.get("llm_options")),
            "tts_provider": r.get("tts_provider", "openai"),
            "tts_model": r.get("tts_model"),
            "tts_voice": r.get("tts_voice"),
            "tts_credential_source": r.get("tts_credential_source", "platform"),
            "tts_credential_id": str(r["tts_credential_id"]) if r.get("tts_credential_id") else None,
            "tts_options": parse_opts(r.get("tts_options")),
            "created_at": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else str(r.get("created_at", "")),
            "updated_at": r["updated_at"].isoformat() if hasattr(r.get("updated_at"), "isoformat") else str(r.get("updated_at", "")),
        }
