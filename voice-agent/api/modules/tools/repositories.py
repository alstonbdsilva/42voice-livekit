"""
Tools Database Repository.
Queries and persists reusable agent tool configurations (HTTP API, End Call,
Transfer Call, Calculator, MCP).
"""

import json
import logging
from typing import Any, Dict, List, Optional

from api import database

logger = logging.getLogger("voice-agent.api.tools.repositories")


class ToolRepository:
    select_query_base = """
        SELECT t.id, t.tool_uuid, t.name, t.description, t.category, t.icon,
               t.icon_color, t.status, t.definition, t.user_id, t.client_id,
               t.created_at, t.updated_at,
               u.email AS created_by_email
        FROM tools t
        LEFT JOIN users u ON u.id = t.user_id
    """

    async def find_all(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch all tools scoped to the requesting user's role/context."""
        role = filter_data.get("role")
        user_id = filter_data.get("userId")
        client_id = filter_data.get("clientId")
        status = filter_data.get("status")
        category = filter_data.get("category")

        conditions = []
        params: List[Any] = []

        if role not in ("SUPER_ADMIN", "FINANCE_ADMIN"):
            idx = len(params) + 1
            if client_id:
                conditions.append(f"(t.user_id = ${idx} OR t.client_id = ${idx + 1})")
                params.extend([user_id, client_id])
            else:
                conditions.append(f"t.user_id = ${idx}")
                params.append(user_id)

        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            idx = len(params) + 1
            conditions.append(f"t.status = ANY(${idx})")
            params.append(statuses)

        if category:
            idx = len(params) + 1
            conditions.append(f"t.category = ${idx}")
            params.append(category)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"{self.select_query_base} {where_clause} ORDER BY t.created_at DESC"
        return await database.query(query, params)

    async def find_by_uuid(
        self, tool_uuid: str, filter_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find a single tool by its public UUID, scoped to the requester."""
        conditions = ["t.tool_uuid = $1"]
        params: List[Any] = [tool_uuid]

        if filter_data:
            role = filter_data.get("role")
            user_id = filter_data.get("userId")
            client_id = filter_data.get("clientId")
            if role not in ("SUPER_ADMIN", "FINANCE_ADMIN"):
                if client_id:
                    conditions.append("(t.user_id = $2 OR t.client_id = $3)")
                    params.extend([user_id, client_id])
                else:
                    conditions.append("t.user_id = $2")
                    params.append(user_id)

        query = f"{self.select_query_base} WHERE {' AND '.join(conditions)}"
        rows = await database.query(query, params)
        return rows[0] if rows else None

    async def find_by_uuids(self, tool_uuids: List[str]) -> List[Dict[str, Any]]:
        """Fetch active tools by their public UUIDs (used by the voice runtime)."""
        if not tool_uuids:
            return []
        query = f"{self.select_query_base} WHERE t.tool_uuid = ANY($1) AND t.status = 'active'"
        return await database.query(query, [tool_uuids])

    async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new tool record."""
        rows = await database.query(
            """INSERT INTO tools (name, description, category, icon, icon_color,
                                   status, definition, user_id, client_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING tool_uuid""",
            [
                data["name"].strip(),
                data.get("description"),
                data["category"],
                data.get("icon") or "globe",
                data.get("icon_color") or "#3B82F6",
                data.get("status", "active"),
                json.dumps(data.get("definition", {})),
                data.get("user_id"),
                data.get("client_id"),
            ],
        )
        tool_uuid = rows[0]["tool_uuid"]
        return await self.find_by_uuid(str(tool_uuid))

    async def update(
        self, tool_uuid: str, data: Dict[str, Any], filter_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Update mutable fields on a tool."""
        fields = []
        params: List[Any] = []
        idx = 1

        if "name" in data and data["name"] is not None:
            fields.append(f"name = ${idx}")
            params.append(data["name"].strip())
            idx += 1
        if "description" in data:
            fields.append(f"description = ${idx}")
            params.append(data["description"])
            idx += 1
        if "icon" in data and data["icon"] is not None:
            fields.append(f"icon = ${idx}")
            params.append(data["icon"])
            idx += 1
        if "icon_color" in data and data["icon_color"] is not None:
            fields.append(f"icon_color = ${idx}")
            params.append(data["icon_color"])
            idx += 1
        if "definition" in data and data["definition"] is not None:
            fields.append(f"definition = ${idx}")
            params.append(json.dumps(data["definition"]))
            idx += 1
        if "status" in data and data["status"] is not None:
            fields.append(f"status = ${idx}")
            params.append(data["status"])
            idx += 1

        if not fields:
            return await self.find_by_uuid(tool_uuid, filter_data)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(tool_uuid)

        await database.query(
            f"UPDATE tools SET {', '.join(fields)} WHERE tool_uuid = ${idx}",
            params,
        )
        return await self.find_by_uuid(tool_uuid, filter_data)

    async def set_status(
        self, tool_uuid: str, status: str, filter_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Archive/unarchive a tool by flipping its status."""
        existing = await self.find_by_uuid(tool_uuid, filter_data)
        if not existing:
            return None
        await database.query(
            "UPDATE tools SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE tool_uuid = $2",
            [status, tool_uuid],
        )
        return await self.find_by_uuid(tool_uuid, filter_data)
