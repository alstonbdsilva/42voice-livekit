"""
Credentials Database Repository.
Queries and persists external auth credentials scoped by client_id.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from api import database

logger = logging.getLogger("voice-agent.api.credentials.repositories")


class CredentialRepository:
    select_query_base = """
        SELECT id, credential_uuid, client_id, name, description,
               credential_type, credential_data, user_id,
               created_at, updated_at, is_active
        FROM external_credentials
    """

    async def find_all(self, client_id: str) -> List[Dict[str, Any]]:
        """Fetch all active credentials scoped to the client organization."""
        query = f"""
            {self.select_query_base}
            WHERE client_id = $1 AND is_active = TRUE
            ORDER BY created_at DESC
        """
        rows = await database.query(query, [client_id])
        return rows

    async def find_by_uuid(self, credential_uuid: str, client_id: str) -> Optional[Dict[str, Any]]:
        """Find a credential by public UUID and client_id."""
        query = f"""
            {self.select_query_base}
            WHERE credential_uuid = $1 AND client_id = $2 AND is_active = TRUE
        """
        rows = await database.query(query, [credential_uuid, client_id])
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new credential record."""
        rows = await database.query(
            """INSERT INTO external_credentials (client_id, name, description,
                                                 credential_type, credential_data, user_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING credential_uuid""",
            [
                data["client_id"],
                data["name"].strip(),
                data.get("description"),
                data["credential_type"],
                json.dumps(data.get("credential_data", {})),
                data.get("user_id"),
            ],
        )
        credential_uuid = rows[0]["credential_uuid"]
        return await self.find_by_uuid(str(credential_uuid), data["client_id"])

    async def update(
        self, credential_uuid: str, data: Dict[str, Any], client_id: str
    ) -> Optional[Dict[str, Any]]:
        """Update fields on a credential."""
        fields = []
        params = []
        idx = 1

        if "name" in data and data["name"] is not None:
            fields.append(f"name = ${idx}")
            params.append(data["name"].strip())
            idx += 1
        if "description" in data:
            fields.append(f"description = ${idx}")
            params.append(data["description"])
            idx += 1
        if "credential_type" in data and data["credential_type"] is not None:
            fields.append(f"credential_type = ${idx}")
            params.append(data["credential_type"])
            idx += 1
        if "credential_data" in data and data["credential_data"] is not None:
            fields.append(f"credential_data = ${idx}")
            params.append(json.dumps(data["credential_data"]))
            idx += 1

        if not fields:
            return await self.find_by_uuid(credential_uuid, client_id)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([credential_uuid, client_id])

        await database.query(
            f"UPDATE external_credentials SET {', '.join(fields)} WHERE credential_uuid = ${idx} AND client_id = ${idx + 1} AND is_active = TRUE",
            params,
        )
        return await self.find_by_uuid(credential_uuid, client_id)

    async def delete(self, credential_uuid: str, client_id: str) -> bool:
        """Soft delete a credential by setting is_active = FALSE."""
        result = await database.query(
            "UPDATE external_credentials SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE credential_uuid = $1 AND client_id = $2 AND is_active = TRUE RETURNING id",
            [credential_uuid, client_id],
        )
        return len(result) > 0
