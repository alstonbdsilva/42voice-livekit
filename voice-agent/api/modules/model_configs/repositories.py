"""
Model configuration database repository.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from api import database

logger = logging.getLogger("voice-agent.api.model_configs.repositories")


class ModelConfigRepository:
    select_base = """
        SELECT id, client_id, user_id, name, description, status,
               stt_provider, stt_model, stt_credential_source, stt_credential_id, stt_options,
               llm_provider, llm_model, llm_credential_source, llm_credential_id, llm_options,
               tts_provider, tts_model, tts_voice, tts_credential_source, tts_credential_id, tts_options,
               created_at, updated_at
        FROM platform_model_configurations
    """

    async def find_all(self, client_id: str) -> List[Dict[str, Any]]:
        query = f"{self.select_base} WHERE client_id = $1 ORDER BY created_at DESC"
        return await database.query(query, [client_id])

    async def find_by_id(self, config_id: str, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if client_id:
            query = f"{self.select_base} WHERE id = $1::uuid AND client_id = $2::uuid"
            rows = await database.query(query, [config_id, client_id])
        else:
            query = f"{self.select_base} WHERE id = $1::uuid"
            rows = await database.query(query, [config_id])
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        query = """
            INSERT INTO platform_model_configurations (
                client_id, user_id, name, description, status,
                stt_provider, stt_model, stt_credential_source, stt_credential_id, stt_options,
                llm_provider, llm_model, llm_credential_source, llm_credential_id, llm_options,
                tts_provider, tts_model, tts_voice, tts_credential_source, tts_credential_id, tts_options
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21
            ) RETURNING id
        """
        rows = await database.query(
            query,
            [
                data["client_id"],
                data.get("user_id"),
                data["name"].strip(),
                data.get("description"),
                data.get("status", "active"),
                data.get("stt_provider", "deepgram"),
                data.get("stt_model"),
                data.get("stt_credential_source", "platform"),
                data.get("stt_credential_id"),
                json.dumps(data.get("stt_options", {})),
                data.get("llm_provider", "openai"),
                data.get("llm_model"),
                data.get("llm_credential_source", "platform"),
                data.get("llm_credential_id"),
                json.dumps(data.get("llm_options", {})),
                data.get("tts_provider", "openai"),
                data.get("tts_model"),
                data.get("tts_voice"),
                data.get("tts_credential_source", "platform"),
                data.get("tts_credential_id"),
                json.dumps(data.get("tts_options", {})),
            ]
        )
        created_id = str(rows[0]["id"])
        created = await self.find_by_id(created_id)
        if not created:
            raise RuntimeError("Failed to retrieve created model configuration")
        return created

    async def update(self, config_id: str, data: Dict[str, Any], client_id: str) -> Optional[Dict[str, Any]]:
        fields = []
        params = []
        param_idx = 1

        for col in [
            "name", "description", "status",
            "stt_provider", "stt_model", "stt_credential_source", "stt_credential_id",
            "llm_provider", "llm_model", "llm_credential_source", "llm_credential_id",
            "tts_provider", "tts_model", "tts_voice", "tts_credential_source", "tts_credential_id",
        ]:
            if col in data and data[col] is not None:
                fields.append(f"{col} = ${param_idx}")
                params.append(data[col])
                param_idx += 1

        for json_col in ["stt_options", "llm_options", "tts_options"]:
            if json_col in data and data[json_col] is not None:
                fields.append(f"{json_col} = ${param_idx}")
                params.append(json.dumps(data[json_col]) if isinstance(data[json_col], dict) else data[json_col])
                param_idx += 1

        if not fields:
            return await self.find_by_id(config_id, client_id)

        fields.append(f"updated_at = CURRENT_TIMESTAMP")
        params.append(config_id)
        params.append(client_id)

        query = f"UPDATE platform_model_configurations SET {', '.join(fields)} WHERE id = ${param_idx}::uuid AND client_id = ${param_idx + 1}::uuid RETURNING id"
        rows = await database.query(query, params)
        if not rows:
            return None
        return await self.find_by_id(config_id, client_id)

    async def delete(self, config_id: str, client_id: str) -> bool:
        """Soft delete by setting status to inactive or deleting."""
        rows = await database.query(
            "UPDATE platform_model_configurations SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE id = $1::uuid AND client_id = $2::uuid RETURNING id",
            [config_id, client_id]
        )
        return len(rows) > 0
