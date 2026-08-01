"""
Agents Service.
Orchestrates agent configurations and operational metrics mapping.
"""

import logging
from typing import Dict, Any, List, Optional
from api.modules.agents.repositories import AgentRepository

logger = logging.getLogger("voice-agent.api.agents.services")


class AgentService:
    def __init__(self):
        self.agent_repository = AgentRepository()

    async def get_all_agents(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List all agents scoped to authorization filter context."""
        agents = await self.agent_repository.find_all(filter_data)
        return [self.map_to_response(a) for a in agents]

    async def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Fetch individual agent configuration."""
        agent = await self.agent_repository.find_by_id(agent_id)
        if not agent:
            return None
        return self.map_to_response(agent)

    async def update_agent_status(self, agent_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update agent active/inactive state status."""
        updated = await self.agent_repository.update_status(agent_id, status)
        if not updated:
            return None
        return self.map_to_response(updated)

    async def update_agent_assignments(self, agent_id: str, reseller_ids: Optional[List[str]], client_ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
        """Update reseller and client assignments for an agent. Clones template if assigning unassigned agent."""
        existing = await self.agent_repository.find_by_id(agent_id)
        if not existing:
            return None
            
        assigned_resellers = existing.get("assigned_resellers", [])
        assigned_clients = existing.get("assigned_clients", [])
        is_unassigned = len(assigned_resellers) == 0 and len(assigned_clients) == 0
        has_new_targets = (reseller_ids and len(reseller_ids) > 0) or (client_ids and len(client_ids) > 0)

        if is_unassigned and has_new_targets:
            updated = await self.agent_repository.clone_agent(agent_id, reseller_ids, client_ids)
        else:
            updated = await self.agent_repository.update_assignments(agent_id, reseller_ids, client_ids)

        if not updated:
            return None
        return self.map_to_response(updated)

    async def update_agent_details(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update configurable fields (name, use_case, activity_description)."""
        updated = await self.agent_repository.update_details(agent_id, data)
        if not updated:
            return None
        return self.map_to_response(updated)

    async def create_agent(self, payload: Dict[str, Any], user_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new voice agent record with role-based scoping."""
        role = user_context.get("role")
        user_id = user_context.get("id")
        user_client_id = user_context.get("client_id")
        user_reseller_id = user_context.get("reseller_id")

        agent_data = {
            "name": payload["name"],
            "callType": payload.get("callType", "inbound"),
            "useCase": payload.get("useCase", ""),
            "activityDescription": payload.get("activityDescription", ""),
            "type": payload.get("type", "Inbound Voice" if payload.get("callType", "inbound") == "inbound" else "Outbound Voice"),
            "channels": payload.get("channels", ["voice"]),
            "status": "active",
            "userId": user_id,
            "resellerIds": [],
            "clientIds": [],
            "voiceName": payload.get("voiceName", "aria"),
            "voiceGender": payload.get("voiceGender", "female"),
            "guardrails": payload.get("guardrails", {}),
            "customGuardrails": payload.get("customGuardrails", ""),
            "knowledgeItems": payload.get("knowledgeItems", []),
            "toolIds": payload.get("toolIds", [])
        }

        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            agent_data["resellerIds"] = payload.get("resellerIds", [])
            agent_data["clientIds"] = payload.get("clientIds", [])
        elif role == "RESELLER":
            # Resellers can assign to their reseller bucket (or self) and/or to clients under them
            if user_reseller_id:
                agent_data["resellerIds"] = [str(user_reseller_id)]
            agent_data["clientIds"] = payload.get("clientIds", [])
        elif role == "CLIENT":
            if user_client_id:
                agent_data["clientId"] = user_client_id
                agent_data["clientIds"] = [str(user_client_id)]
            if user_reseller_id:
                agent_data["resellerIds"] = [str(user_reseller_id)]

        created = await self.agent_repository.create(agent_data)
        if not created:
            return None
        return self.map_to_response(created)

    def map_to_response(self, a: Dict[str, Any]) -> Dict[str, Any]:
        """Maps postgres database columns to React DataTable camelCase properties."""
        import json
        
        assigned_resellers = a.get("assigned_resellers", [])
        if isinstance(assigned_resellers, str):
            assigned_resellers = json.loads(assigned_resellers)
            
        assigned_clients = a.get("assigned_clients", [])
        if isinstance(assigned_clients, str):
            assigned_clients = json.loads(assigned_clients)

        guardrails = a.get("guardrails") or {}
        if isinstance(guardrails, str):
            guardrails = json.loads(guardrails)
            
        knowledge_items = a.get("knowledge_items") or []
        if isinstance(knowledge_items, str):
            knowledge_items = json.loads(knowledge_items)
            
        tool_ids = a.get("tool_ids") or []
        if isinstance(tool_ids, str):
            tool_ids = json.loads(tool_ids)

        return {
            "id": str(a["id"]),
            "name": a["name"],
            "type": a["type"],
            "callType": a.get("call_type") or "inbound",
            "useCase": a.get("use_case") or "",
            "activityDescription": a.get("activity_description") or "",
            "channels": a["channels"] if isinstance(a["channels"], list) else list(a["channels"]),
            "status": a["status"],
            "totalCalls": a["total_calls"],
            "totalMessages": a["total_messages"],
            "totalMinutes": a["total_minutes"],
            "successRate": float(a["success_rate"]),
            "escalationRate": float(a["escalation_rate"]),
            "promptVersion": a["prompt_version"],
            "kbVersion": a["kb_version"],
            "totalCost": float(a["total_cost"]),
            "lastActivity": a["last_activity"].isoformat() if hasattr(a["last_activity"], "isoformat") else a["last_activity"],
            "clientId": str(a["client_id"]) if a.get("client_id") else None,
            "assignedResellers": assigned_resellers or [],
            "assignedClients": assigned_clients or [],
            "voiceName": a.get("voice_name") or "aria",
            "voiceGender": a.get("voice_gender") or "female",
            "guardrails": guardrails,
            "customGuardrails": a.get("custom_guardrails") or "",
            "knowledgeItems": knowledge_items,
            "toolIds": tool_ids
        }
