"""
Agent Group Service.
Manages agent groups and group memberships.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.agent_group_service")


class AgentGroupService:
    """Service for managing agent groups."""
    
    @staticmethod
    async def create_group(
        name: str,
        user_id: str,
        client_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new agent group."""
        try:
            query = """
                INSERT INTO agent_groups (name, description, user_id, client_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id, name, description, user_id, client_id, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [name, description, UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating agent group: {e}")
            return None
    
    @staticmethod
    async def get_group(group_id: str) -> Optional[Dict[str, Any]]:
        """Get agent group details."""
        try:
            query = """
                SELECT id, name, description, user_id, client_id, created_at, updated_at
                FROM agent_groups
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(group_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting agent group: {e}")
            return None
    
    @staticmethod
    async def get_user_groups(user_id: str) -> List[Dict[str, Any]]:
        """Get all agent groups for a user."""
        try:
            query = """
                SELECT id, name, description, created_at, updated_at
                FROM agent_groups
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user agent groups: {e}")
            return []
    
    @staticmethod
    async def get_client_groups(client_id: str) -> List[Dict[str, Any]]:
        """Get all agent groups for a client."""
        try:
            query = """
                SELECT id, name, description, created_at, updated_at
                FROM agent_groups
                WHERE client_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting client agent groups: {e}")
            return []
    
    @staticmethod
    async def update_group(
        group_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update agent group."""
        try:
            allowed_fields = ["name", "description"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await AgentGroupService.get_group(group_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(group_id)]
            
            query = f"""
                UPDATE agent_groups
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, name, description, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating agent group: {e}")
            return None
    
    @staticmethod
    async def delete_group(group_id: str) -> bool:
        """Delete an agent group."""
        try:
            query = "DELETE FROM agent_groups WHERE id = $1"
            await database.query(query, [UUID(group_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting agent group: {e}")
            return False
    
    @staticmethod
    async def add_agent_to_group(
        group_id: str,
        agent_id: str,
        priority: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Add an agent to a group."""
        try:
            query = """
                INSERT INTO agent_group_members (group_id, agent_id, priority)
                VALUES ($1, $2, $3)
                ON CONFLICT (group_id, agent_id) DO UPDATE
                SET priority = $3, updated_at = CURRENT_TIMESTAMP
                RETURNING id, group_id, agent_id, priority, created_at, updated_at
            """
            
            rows = await database.query(query, [UUID(group_id), UUID(agent_id), priority])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error adding agent to group: {e}")
            return None
    
    @staticmethod
    async def get_group_members(group_id: str) -> List[Dict[str, Any]]:
        """Get all members of a group."""
        try:
            query = """
                SELECT agm.id, agm.agent_id, agm.priority,
                       a.id as agent_id, a.name, a.type, a.status, a.agent_type
                FROM agent_group_members agm
                JOIN agents a ON agm.agent_id = a.id
                WHERE agm.group_id = $1
                ORDER BY agm.priority ASC
            """
            
            rows = await database.query(query, [UUID(group_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting group members: {e}")
            return []
    
    @staticmethod
    async def get_agent_groups(agent_id: str) -> List[Dict[str, Any]]:
        """Get all groups an agent belongs to."""
        try:
            query = """
                SELECT ag.id, ag.name, ag.description, agm.priority,
                       ag.created_at, ag.updated_at
                FROM agent_group_members agm
                JOIN agent_groups ag ON agm.group_id = ag.id
                WHERE agm.agent_id = $1
                ORDER BY agm.priority ASC
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agent groups: {e}")
            return []
    
    @staticmethod
    async def remove_agent_from_group(
        group_id: str,
        agent_id: str
    ) -> bool:
        """Remove an agent from a group."""
        try:
            query = """
                DELETE FROM agent_group_members
                WHERE group_id = $1 AND agent_id = $2
            """
            
            await database.query(query, [UUID(group_id), UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error removing agent from group: {e}")
            return False
