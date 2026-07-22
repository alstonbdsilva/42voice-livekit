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
    select_query_base = """
        SELECT a.id, a.name, a.type, a.call_type, a.use_case, a.activity_description, a.channels, a.status,
               a.total_calls, a.total_messages, a.total_minutes, a.success_rate, a.escalation_rate,
               a.prompt_version, a.kb_version, a.total_cost, a.last_activity, a.user_id, a.client_id, a.created_at, a.updated_at,
               COALESCE(
                 (SELECT json_agg(json_build_object('id', r.id, 'name', r.name)) 
                  FROM agent_resellers ar JOIN resellers r ON ar.reseller_id = r.id 
                  WHERE ar.agent_id = a.id), '[]'::json
               ) AS assigned_resellers,
               COALESCE(
                 (SELECT json_agg(json_build_object('id', c.id, 'name', c.name)) 
                  FROM agent_clients ac JOIN clients c ON ac.client_id = c.id 
                  WHERE ac.agent_id = a.id), '[]'::json
               ) AS assigned_clients
        FROM agents a
    """

    async def find_all(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch all agents based on role and organization context."""
        role = filter_data.get("role")
        user_id = filter_data.get("userId")
        client_id = filter_data.get("clientId")
        reseller_id = filter_data.get("resellerId")
        
        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            return await database.query(
                f"{self.select_query_base} ORDER BY a.name ASC"
            )
            
        if role == "RESELLER" and reseller_id:
            return await database.query(
                f"""{self.select_query_base}
                   WHERE a.id IN (SELECT agent_id FROM agent_resellers WHERE reseller_id = $1)
                      OR a.id IN (SELECT agent_id FROM agent_clients WHERE client_id IN (SELECT id FROM clients WHERE reseller_id = $1))
                      OR a.client_id IN (SELECT id FROM clients WHERE reseller_id = $1) 
                      OR a.user_id = $2 
                   ORDER BY a.name ASC""",
                [reseller_id, user_id]
            )
            
        if client_id:
            return await database.query(
                f"""{self.select_query_base}
                   WHERE a.id IN (SELECT agent_id FROM agent_clients WHERE client_id = $1)
                      OR a.client_id = $1 
                      OR a.user_id = $2 
                   ORDER BY a.name ASC""",
                [client_id, user_id]
            )
            
        return await database.query(
            f"{self.select_query_base} WHERE a.user_id = $1 ORDER BY a.name ASC",
            [user_id]
        )

    async def find_by_id(self, agent_id: Any, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find a single agent by ID."""
        rows = await database.query(
            f"{self.select_query_base} WHERE a.id = $1",
            [agent_id],
            client=client
        )
        return rows[0] if rows else None

    async def find_by_name(self, name: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find a single agent by name (case-insensitive)."""
        rows = await database.query(
            f"{self.select_query_base} WHERE LOWER(a.name) = LOWER($1)",
            [name.strip()],
            client=client
        )
        return rows[0] if rows else None

    async def update_status(self, agent_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update agent status field."""
        await database.query(
            """UPDATE agents 
               SET status = $1, updated_at = CURRENT_TIMESTAMP 
               WHERE id = $2""",
            [status, agent_id]
        )
        return await self.find_by_id(agent_id)

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Create a new agent record and associate multi-reseller/client assignments."""
        status = data.get("status", "active")
        channels = data.get("channels", ["voice"])
        call_type = data.get("callType", "inbound")
        use_case = data.get("useCase", "")
        activity_description = data.get("activityDescription", "")
        agent_type = data.get("type", "Inbound Voice" if call_type == "inbound" else "Outbound Voice")
        user_id = data.get("userId")
        client_id = data.get("clientId")
        reseller_ids = data.get("resellerIds", [])
        client_ids = data.get("clientIds", [])
        
        rows = await database.query(
            """INSERT INTO agents (name, type, call_type, use_case, activity_description, channels, status, user_id, client_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id""",
            [
                data["name"].strip(),
                agent_type,
                call_type,
                use_case,
                activity_description,
                channels,
                status,
                user_id,
                client_id
            ],
            client=client
        )
        agent_id = rows[0]["id"]

        # Insert reseller assignments
        for rid in reseller_ids:
            await database.query(
                "INSERT INTO agent_resellers (agent_id, reseller_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [agent_id, rid],
                client=client
            )

        # Insert client assignments
        for cid in client_ids:
            await database.query(
                "INSERT INTO agent_clients (agent_id, client_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [agent_id, cid],
                client=client
            )

        agent = await self.find_by_id(agent_id, client=client)
        if not agent:
            agent = {
                "id": agent_id,
                "name": data["name"].strip(),
                "type": agent_type,
                "call_type": call_type,
                "use_case": use_case,
                "activity_description": activity_description,
                "channels": channels,
                "status": status,
                "total_calls": 0,
                "total_messages": 0,
                "total_minutes": 0,
                "success_rate": Decimal("0.00"),
                "escalation_rate": Decimal("0.00"),
                "prompt_version": 1,
                "kb_version": 1,
                "total_cost": Decimal("0.0000"),
                "user_id": user_id,
                "client_id": client_id,
                "assigned_resellers": reseller_ids,
                "assigned_clients": client_ids
            }
        return agent

    async def update_assignments(self, agent_id: str, reseller_ids: Optional[List[str]] = None, client_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Update reseller and client assignments for an agent."""
        if reseller_ids is not None:
            await database.query("DELETE FROM agent_resellers WHERE agent_id = $1", [agent_id])
            for rid in reseller_ids:
                await database.query(
                    "INSERT INTO agent_resellers (agent_id, reseller_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [agent_id, rid]
                )
        if client_ids is not None:
            await database.query("DELETE FROM agent_clients WHERE agent_id = $1", [agent_id])
            for cid in client_ids:
                await database.query(
                    "INSERT INTO agent_clients (agent_id, client_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [agent_id, cid]
                )
        return await self.find_by_id(agent_id)

    async def clone_agent(self, agent_id: str, reseller_ids: Optional[List[str]] = None, client_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Clone an existing agent configuration into a new independent agent record for a reseller or client."""
        original = await self.find_by_id(agent_id)
        if not original:
            return None
        
        clone_data = {
            "name": original["name"],
            "type": original["type"],
            "callType": original["call_type"],
            "useCase": original.get("use_case", ""),
            "activityDescription": original.get("activity_description", ""),
            "channels": original.get("channels", ["voice"]),
            "status": "active",
            "userId": original.get("user_id"),
            "resellerIds": reseller_ids or [],
            "clientIds": client_ids or []
        }
        return await self.create(clone_data)

    async def update_details(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update configurable agent details (name, use_case, activity_description)."""
        fields = []
        params = []
        param_idx = 1
        
        if "name" in data and data["name"] is not None:
            fields.append(f"name = ${param_idx}")
            params.append(data["name"].strip())
            param_idx += 1
            
        if "useCase" in data and data["useCase"] is not None:
            fields.append(f"use_case = ${param_idx}")
            params.append(data["useCase"].strip())
            param_idx += 1

        if "activityDescription" in data and data["activityDescription"] is not None:
            fields.append(f"activity_description = ${param_idx}")
            params.append(data["activityDescription"].strip())
            param_idx += 1

        if "callType" in data and data["callType"] is not None:
            fields.append(f"call_type = ${param_idx}")
            params.append(data["callType"])
            param_idx += 1
            
        if not fields:
            return await self.find_by_id(agent_id)

        fields.append(f"updated_at = CURRENT_TIMESTAMP")
        params.append(agent_id)
        
        query = f"UPDATE agents SET {', '.join(fields)} WHERE id = ${param_idx}"
        await database.query(query, params)
        return await self.find_by_id(agent_id)

    async def increment_stats(self, agent_id: Any, stats: Dict[str, Any], client: Optional[Any] = None) -> None:
        """Increment call and message metrics for an agent."""
        agent = await self.find_by_id(agent_id, client=client)
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
            ],
            client=client
        )
