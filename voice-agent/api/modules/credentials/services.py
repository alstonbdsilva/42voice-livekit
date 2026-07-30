"""
Credentials Service.
Business logic for managing webhook credentials.
"""

import json
from typing import Any, Dict, List, Optional
from api.modules.credentials.repositories import CredentialRepository
from api.utils.errors import BadRequestError, NotFoundError

VALID_TYPES = {"none", "api_key", "bearer_token", "basic_auth", "custom_header"}


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

        if cred_type == "api_key":
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
        """Fetch raw credential including decrypted data for backend utility calls."""
        row = await self.repository.find_by_uuid(credential_uuid, client_id)
        if not row:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")
        
        # Deserialize data field
        definition = row.get("credential_data")
        if isinstance(definition, str):
            definition = json.loads(definition)
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

        try:
            created = await self.repository.create(
                {
                    "client_id": client_id,
                    "name": payload["name"],
                    "description": payload.get("description"),
                    "credential_type": cred_type,
                    "credential_data": cred_data,
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

        # Load existing first
        existing = await self.repository.find_by_uuid(credential_uuid, client_id)
        if not existing:
            raise NotFoundError("Credential not found", "CREDENTIAL_NOT_FOUND")

        cred_type = payload.get("credential_type")
        cred_data = payload.get("credential_data")

        if cred_type:
            self.validate_type(cred_type)
        else:
            cred_type = existing["credential_type"]

        if cred_data:
            self.validate_data(cred_type, cred_data)

        updated = await self.repository.update(credential_uuid, payload, client_id)
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
        """Convert repository record into credential list item. Does not expose credentials data."""
        return {
            "uuid": str(r["credential_uuid"]),
            "name": r["name"],
            "description": r.get("description"),
            "credential_type": r["credential_type"],
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"],
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") and hasattr(r["updated_at"], "isoformat") else r.get("updated_at"),
        }
