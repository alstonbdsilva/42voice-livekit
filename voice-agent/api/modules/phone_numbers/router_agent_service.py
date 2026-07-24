"""
Router Agent Service.
Manages router agents for intent-based routing.
Router agents are agents with agent_type = 'ROUTER'.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.router_agent_service")


class RouterAgentService:
    """Service for managing router agents."""
    
    @staticmethod
    async def set_router_agent_for_phone(
        phone_number_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Set the router agent for a phone number.
        Updates the agent's agent_type to ROUTER.
        """
        try:
            # Update agent type to ROUTER
            query = """
                UPDATE agents
                SET agent_type = 'ROUTER'
                WHERE id = $1
                RETURNING id, name, type, status, agent_type
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            
            if rows:
                return {
                    "agent_id": str(rows[0]["id"]),
                    "name": rows[0]["name"],
                    "type": rows[0]["type"],
                    "status": rows[0]["status"],
                    "agent_type": rows[0]["agent_type"],
                    "phone_number_id": phone_number_id
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error setting router agent: {e}")
            return None
    
    @staticmethod
    async def get_router_agent_for_phone(phone_number_id: str) -> Optional[Dict[str, Any]]:
        """
        Get router agent for a phone number.
        Finds an agent with agent_type = 'ROUTER' assigned to this phone number.
        """
        try:
            query = """
                SELECT a.id, a.name, a.type, a.status, a.agent_type
                FROM agents a
                JOIN phone_number_agents pna ON a.id = pna.agent_id
                WHERE pna.phone_number_id = $1 AND a.agent_type = 'ROUTER' AND a.status = 'active'
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            
            if rows:
                row = rows[0]
                return {
                    "agent_id": str(row["id"]),
                    "name": row["name"],
                    "type": row["type"],
                    "status": row["status"],
                    "agent_type": row["agent_type"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting router agent: {e}")
            return None
    
    @staticmethod
    async def get_all_router_agents(user_id: str, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all router agents for a user/client."""
        try:
            query = """
                SELECT id, name, type, status, agent_type, user_id, client_id
                FROM agents
                WHERE agent_type = 'ROUTER'
                AND (user_id = $1 OR client_id = $2)
                AND status = 'active'
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id), UUID(client_id) if client_id else None])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting router agents: {e}")
            return []
    
    @staticmethod
    async def convert_to_router_agent(agent_id: str) -> bool:
        """Convert an agent to router agent type."""
        try:
            query = """
                UPDATE agents
                SET agent_type = 'ROUTER'
                WHERE id = $1
            """
            
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error converting agent to router: {e}")
            return False
    
    @staticmethod
    async def convert_to_voice_agent(agent_id: str) -> bool:
        """Convert a router agent back to voice agent type."""
        try:
            query = """
                UPDATE agents
                SET agent_type = 'VOICE'
                WHERE id = $1
            """
            
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error converting router to voice agent: {e}")
            return False
