"""
Agents Database Repository.
Queries agent configuration details and logs operational statistics.
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from api import database

logger = logging.getLogger("voice-agent.api.agents.repositories")


class AgentRepository:
    private_columns = (
        "id, name, type, channels, status, total_calls, total_messages, total_minutes, "
        "success_rate, escalation_rate, prompt_version, kb_version, total_cost, "
        "last_activity, user_id, client_id, created_at, updated_at"
    )

    async def find_all(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch all agents based on role and organization context."""
        role = filter_data.get("role")
        user_id = filter_data.get("userId")
        client_id = filter_data.get("clientId")
        reseller_id = filter_data.get("resellerId")
        
        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            return await database.query(
                f"SELECT {self.private_columns} FROM agents ORDER BY name ASC"
            )
            
        if role == "RESELLER" and reseller_id:
            return await database.query(
                f"""SELECT {self.private_columns} FROM agents 
                   WHERE client_id IN (SELECT id FROM clients WHERE reseller_id = $1) 
                   OR user_id = $2 
                   ORDER BY name ASC""",
                [reseller_id, user_id]
            )
            
        if client_id:
            return await database.query(
                f"""SELECT {self.private_columns} FROM agents 
                   WHERE client_id = $1 OR user_id = $2 
                   ORDER BY name ASC""",
                [client_id, user_id]
            )
            
        return await database.query(
            f"SELECT {self.private_columns} FROM agents WHERE user_id = $1 ORDER BY name ASC",
            [user_id]
        )

    async def find_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Find a single agent by ID."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM agents WHERE id = $1",
            [agent_id]
        )
        return rows[0] if rows else None

    async def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a single agent by name (case-insensitive)."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM agents WHERE LOWER(name) = LOWER($1)",
            [name.strip()]
        )
        return rows[0] if rows else None

    async def update_status(self, agent_id: str, status: str) -> Dict[str, Any]:
        """Update agent status field."""
        rows = await database.query(
            f"""UPDATE agents 
               SET status = $1, updated_at = CURRENT_TIMESTAMP 
               WHERE id = $2 
               RETURNING {self.private_columns}""",
            [status, agent_id]
        )
        return rows[0]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent record (e.g. registered dynamically)."""
        status = data.get("status", "active")
        channels = data.get("channels", ["voice"])
        user_id = data.get("userId")
        client_id = data.get("clientId")
        
        rows = await database.query(
            f"""INSERT INTO agents (name, type, channels, status, user_id, client_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING {self.private_columns}""",
            [
                data["name"].strip(),
                data["type"],
                channels,
                status,
                user_id,
                client_id
            ]
        )
        return rows[0]

    async def increment_stats(self, agent_id: str, stats: Dict[str, Any]) -> None:
        """Increment call and message metrics for an agent."""
        agent = await self.find_by_id(agent_id)
        if not agent:
            return
            
        new_calls = agent["total_calls"] + stats["callCount"]
        new_messages = agent["total_messages"] + stats["messageCount"]
        new_minutes = agent["total_minutes"] + stats["durationMinutes"]
        new_cost = float(agent["total_cost"]) + stats["cost"]
        
        # Calculate rates
        success_count = round((float(agent["success_rate"]) / 100.0) * agent["total_calls"])
        escalation_count = round((float(agent["escalation_rate"]) / 100.0) * agent["total_calls"])
        
        if stats["callCount"] > 0:
            if stats["is_success"]:
                success_count += 1
            if stats["is_escalated"]:
                escalation_count += 1
                
        new_success_rate = round((success_count / new_calls) * 100.0, 2) if new_calls > 0 else 0.00
        new_escalation_rate = round((escalation_count / new_calls) * 100.0, 2) if new_calls > 0 else 0.00
        
        await database.query(
            """UPDATE agents 
               SET total_calls = $1, 
                   total_messages = $2, 
                   total_minutes = $3, 
                   total_cost = $4, 
                   success_rate = $5, 
                   escalation_rate = $6, 
                   last_activity = CURRENT_TIMESTAMP, 
                   updated_at = CURRENT_TIMESTAMP 
               WHERE id = $7""",
            [
                new_calls, 
                new_messages, 
                new_minutes, 
                Decimal(str(new_cost)), 
                Decimal(str(new_success_rate)), 
                Decimal(str(new_escalation_rate)), 
                agent_id
            ]
        )
