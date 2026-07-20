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

    async def update_agent_status(self, agent_id: str, status: str) -> Dict[str, Any]:
        """Update agent active/inactive state status."""
        updated = await self.agent_repository.update_status(agent_id, status)
        return self.map_to_response(updated)

    def map_to_response(self, a: Dict[str, Any]) -> Dict[str, Any]:
        """Maps postgres database columns to React DataTable camelCase properties."""
        return {
            "id": str(a["id"]),
            "name": a["name"],
            "type": a["type"],
            "channels": a["channels"],
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
            "clientId": str(a["client_id"]) if a["client_id"] else None
        }
