"""
Credentials Service.
Business logic for managing webhook credentials and encrypted BYO provider API keys.
"""

import json
from typing import Any, Dict, List, Optional
from api.modules.credentials.repositories import CredentialRepository
from api.utils.encryption import provider_encryptor
from api.utils.errors import BadRequestError, NotFoundError
from providers.credentials import format_credential_hint

VALID_TYPES = {"none", "api_key", "bearer_token", "basic_auth", "custom_header", "provider_api_key"}
VALID_PROVIDERS = {"openai", "deepgram", "elevenlabs"}


class CredentialService:
    def __init__(self):
        self.repository = CredentialRepository()

    @staticmethod
    def validate_type(cred_type: str) -> None:
        if cred_type not in VALID_TYPES:
            raise BadRequestError(
                f"Invalid credential type '{cred_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}",
                "INVALID_CREDENTIAL_TYPE",
            )

    @staticmethod
    def validate_data(cred_type: str, data: Dict[str, Any]) -> None:
        """Validate credential data structures."""
        if cred_type == "none":
            return

        if cred_type == "provider_api_key":
            if "provider" not in data or not data["provider"]:
                raise BadRequestError(
                    "Provider API Key credential requires 'provider' field ('openai', 'deepgram', 'elevenlabs')",
                    "INVALID_CREDENTIAL_DATA",
                )
            if data["provider"].lower() not in VALID_PROVIDERS:
                raise BadRequestError(
                    f"Unsupported provider '{data['provider']}'. Supported: {', '.join(sorted(VALID_PROVIDERS))}",
                    "UNSUPPORTED_PROVIDER",
                )
            if "api_key" not in data and "encrypted_api_key" not in data:
                raise BadRequestError(
                    "Provider API Key credential requires 'api_key' secret",
                    "INVALID_CREDENTIAL_DATA",
                )
        elif cred_type == "api_key":
            if "header_name" not in data or "api_key" not in data:
                raise BadRequestError(
                    "API Key credential requires 'header_name' and 'api_key' fields",
                    "INVALID_CREDENTIAL_DATA",
                )
        elif cred_type == "bearer_token":
            if "token" not in data:
                raise BadRequestError(
                    "Bearer Token credential requires 'token' field",
                    "INVALID_CREDENTIAL_DATA",
                )
        elif cred_type == "basic_auth":
            if "username" not in data or "password" not in data:
                raise BadRequestError(
                    "Basic Auth credential requires 'username' and 'password' fields",
                    "INVALID_CREDENTIAL_DATA",
                )
        elif cred_type == "custom_header":
            if "header_name" not in data or "header_value" not in data:
                raise BadRequestError(
                    "Custom Header credential requires 'header_name' and 'header_value' fields",
                    "INVALID_CREDENTIAL_DATA",
                )

    async def list_credentials(self, client_id: str) -> List[Dict[str, Any]]:
        rows = await self.repository.find_all(client_id)
        return [self.map_to_public_response(row) for row in rows]

    async def get_credential(self, credential_uuid: str, client_id: str) -> Dict[str, Any]:
        row = await self.repository.find_by_uuid(credential_uuid, client_id)
        if not row:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")
        return self.map_to_public_response(row)

    async def get_raw_credential(self, credential_uuid: str, client_id: str) -> Dict[str, Any]:
        """Fetch raw credential including data definition for internal backend calls."""
        row = await self.repository.find_by_uuid(credential_uuid, client_id)
        if not row:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")

        definition = row.get("credential_data")
        if isinstance(definition, str):
            try:
                definition = json.loads(definition)
            except Exception:
                definition = {}
        row["credential_data"] = definition or {}
        return row

    async def create_credential(
        self, payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required to scope credentials", "CLIENT_REQUIRED")

        cred_type = payload.get("credential_type", "none")
        self.validate_type(cred_type)

        cred_data = payload.get("credential_data", {})
        self.validate_data(cred_type, cred_data)

        # Process provider_api_key encryption and hint generation
        stored_data = dict(cred_data)
        if cred_type == "provider_api_key":
            plain_key = stored_data.pop("api_key", None)
            if plain_key:
                stored_data["encrypted_api_key"] = provider_encryptor.encrypt(plain_key)
                stored_data["hint"] = format_credential_hint(plain_key)
            stored_data["provider"] = stored_data.get("provider", "").lower()

        try:
            created = await self.repository.create(
                {
                    "client_id": client_id,
                    "name": payload["name"],
                    "description": payload.get("description"),
                    "credential_type": cred_type,
                    "credential_data": stored_data,
                    "user_id": user_context.get("id"),
                }
            )
            return self.map_to_public_response(created)
        except Exception as e:
            if "unique_org_credential_name" in str(e) or "unique" in str(e).lower():
                raise BadRequestError(
                    f"A credential with the name '{payload['name']}' already exists",
                    "DUPLICATE_CREDENTIAL_NAME",
                )
            raise

    async def update_credential(
        self, credential_uuid: str, payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required to scope credentials", "CLIENT_REQUIRED")

        existing = await self.repository.find_by_uuid(credential_uuid, client_id)
        if not existing:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")

        cred_type = payload.get("credential_type") or existing["credential_type"]
        self.validate_type(cred_type)

        update_payload = dict(payload)
        cred_data = payload.get("credential_data")

        if cred_data is not None:
            self.validate_data(cred_type, cred_data)
            stored_data = dict(cred_data)
            if cred_type == "provider_api_key":
                plain_key = stored_data.pop("api_key", None)
                if plain_key:
                    # Key rotation / replacement
                    stored_data["encrypted_api_key"] = provider_encryptor.encrypt(plain_key)
                    stored_data["hint"] = format_credential_hint(plain_key)
                else:
                    # Keep existing encrypted key and hint if not supplied in update
                    existing_data = existing.get("credential_data")
                    if isinstance(existing_data, str):
                        try:
                            existing_data = json.loads(existing_data)
                        except Exception:
                            existing_data = {}
                    if isinstance(existing_data, dict):
                        if "encrypted_api_key" in existing_data and "encrypted_api_key" not in stored_data:
                            stored_data["encrypted_api_key"] = existing_data["encrypted_api_key"]
                        if "hint" in existing_data and "hint" not in stored_data:
                            stored_data["hint"] = existing_data["hint"]
                stored_data["provider"] = stored_data.get("provider", "").lower()
            update_payload["credential_data"] = stored_data

        updated = await self.repository.update(credential_uuid, update_payload, client_id)
        if not updated:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")
        return self.map_to_public_response(updated)

    async def delete_credential(self, credential_uuid: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        client_id = user_context.get("client_id")
        if not client_id:
            raise BadRequestError("Client context required to scope credentials", "CLIENT_REQUIRED")

        deleted = await self.repository.delete(credential_uuid, client_id)
        if not deleted:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")
        return {"status": "deleted", "uuid": credential_uuid}

    def map_to_public_response(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Convert repository record into safe public item. NEVER exposes raw secrets or ciphertexts."""
        raw_data = r.get("credential_data")
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                raw_data = {}
        if not isinstance(raw_data, dict):
            raw_data = {}

        provider_name = raw_data.get("provider")
        hint = raw_data.get("hint") or raw_data.get("credential_hint")

        resp = {
            "id": str(r.get("id")) if r.get("id") else None,
            "uuid": str(r["credential_uuid"]),
            "name": r["name"],
            "description": r.get("description"),
            "credential_type": r["credential_type"],
            "status": "active" if r.get("is_active", True) else "inactive",
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") and hasattr(r["updated_at"], "isoformat") else str(r.get("updated_at", "")),
        }
        if provider_name:
            resp["provider"] = provider_name
        if hint:
            resp["credentialHint"] = hint

        return resp
