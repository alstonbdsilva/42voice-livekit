"""
Capability Service.
Manages capabilities and agent capability assignments.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.capability_service")


class CapabilityService:
    """Service for managing capabilities."""
    
    @staticmethod
    async def create_capability(
        name: str,
        user_id: str,
        client_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new capability."""
        try:
            query = """
                INSERT INTO capabilities (name, description, user_id, client_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id, name, description, user_id, client_id, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [name, description, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating capability: {e}")
            return None
    
    @staticmethod
    async def get_capability(capability_id: str) -> Optional[Dict[str, Any]]:
        """Get capability details."""
        try:
            query = """
                SELECT id, name, description, user_id, client_id, created_at, updated_at
                FROM capabilities
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(capability_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting capability: {e}")
            return None
    
    @staticmethod
    async def get_user_capabilities(user_id: str) -> List[Dict[str, Any]]:
        """Get all capabilities for a user."""
        try:
            query = """
                SELECT id, name, description, created_at, updated_at
                FROM capabilities
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user capabilities: {e}")
            return []
    
    @staticmethod
    async def get_client_capabilities(client_id: str) -> List[Dict[str, Any]]:
        """Get all capabilities for a client."""
        try:
            query = """
                SELECT id, name, description, created_at, updated_at
                FROM capabilities
                WHERE client_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting client capabilities: {e}")
            return []
    
    @staticmethod
    async def assign_capability_to_agent(
        agent_id: str,
        capability_id: str,
        priority: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Assign a capability to an agent."""
        try:
            query = """
                INSERT INTO agent_capabilities (agent_id, capability_id, priority)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id, capability_id) DO UPDATE
                SET priority = $3, updated_at = CURRENT_TIMESTAMP
                RETURNING id, agent_id, capability_id, priority, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [UUID(agent_id), UUID(capability_id), priority]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error assigning capability: {e}")
            return None
    
    @staticmethod
    async def get_agent_capabilities(agent_id: str) -> List[Dict[str, Any]]:
        """Get all capabilities for an agent."""
        try:
            query = """
                SELECT ac.id, ac.agent_id, ac.capability_id, ac.priority,
                       c.name, c.description, c.created_at
                FROM agent_capabilities ac
                JOIN capabilities c ON ac.capability_id = c.id
                WHERE ac.agent_id = $1
                ORDER BY ac.priority ASC
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agent capabilities: {e}")
            return []
    
    @staticmethod
    async def get_agents_by_capability(capability_id: str) -> List[Dict[str, Any]]:
        """Get all agents with a specific capability."""
        try:
            query = """
                SELECT ac.id, ac.agent_id, ac.priority,
                       a.id as agent_id, a.name, a.type, a.status
                FROM agent_capabilities ac
                JOIN agents a ON ac.agent_id = a.id
                WHERE ac.capability_id = $1 AND a.status = 'active'
                ORDER BY ac.priority ASC
            """
            
            rows = await database.query(query, [UUID(capability_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agents by capability: {e}")
            return []
    
    @staticmethod
    async def remove_capability_from_agent(
        agent_id: str,
        capability_id: str
    ) -> bool:
        """Remove a capability from an agent."""
        try:
            query = """
                DELETE FROM agent_capabilities
                WHERE agent_id = $1 AND capability_id = $2
            """
            
            await database.query(query, [UUID(agent_id), UUID(capability_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error removing capability: {e}")
            return False
    
    @staticmethod
    async def delete_capability(capability_id: str) -> bool:
        """Delete a capability."""
        try:
            query = "DELETE FROM capabilities WHERE id = $1"
            await database.query(query, [UUID(capability_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting capability: {e}")
            return False
    
    @staticmethod
    async def set_capability_target_agent(
        capability_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Set capability target to a specific agent."""
        try:
            query = """
                UPDATE capabilities
                SET target_type = 'agent', target_agent_id = $1, target_group_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                RETURNING id, name, description, target_type, target_agent_id, target_group_id
            """
            
            rows = await database.query(query, [UUID(agent_id), UUID(capability_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error setting capability target agent: {e}")
            return None
    
    @staticmethod
    async def set_capability_target_group(
        capability_id: str,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """Set capability target to an agent group."""
        try:
            query = """
                UPDATE capabilities
                SET target_type = 'group', target_group_id = $1, target_agent_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                RETURNING id, name, description, target_type, target_agent_id, target_group_id
            """
            
            rows = await database.query(query, [UUID(group_id), UUID(capability_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error setting capability target group: {e}")
            return None
    
    @staticmethod
    async def get_capability_target(capability_id: str) -> Optional[Dict[str, Any]]:
        """Get the target (agent or group) for a capability."""
        try:
            query = """
                SELECT id, name, target_type, target_agent_id, target_group_id
                FROM capabilities
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(capability_id)])
            if not rows:
                return None
            
            cap = rows[0]
            return {
                "capability_id": str(cap["id"]),
                "capability_name": cap["name"],
                "target_type": cap["target_type"],
                "target_agent_id": str(cap["target_agent_id"]) if cap["target_agent_id"] else None,
                "target_group_id": str(cap["target_group_id"]) if cap["target_group_id"] else None
            }
            
        except Exception as e:
            logger.error(f"Error getting capability target: {e}")
            return None
