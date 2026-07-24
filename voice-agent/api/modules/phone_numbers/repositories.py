"""
Phone Numbers Repository.
Data access layer for phone numbers and assignments.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.repositories")


class PhoneNumberRepository:
    """Repository for phone number operations."""
    
    @staticmethod
    async def create(
        number: str,
        provider: str,
        user_id: str,
        client_id: Optional[str] = None,
        call_type: str = "inbound",
        friendly_name: Optional[str] = None,
        provider_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new phone number."""
        try:
            query = """
                INSERT INTO phone_numbers 
                (number, provider, provider_id, user_id, client_id, call_type, friendly_name, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
                RETURNING id, number, provider, user_id, client_id, call_type, friendly_name, status, created_at
            """
            
            rows = await database.query(
                query,
                [number, provider, provider_id, UUID(user_id), UUID(client_id) if client_id else None, call_type, friendly_name]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating phone number: {e}")
            return None
    
    @staticmethod
    async def get_by_id(phone_number_id: str) -> Optional[Dict[str, Any]]:
        """Get phone number by ID."""
        try:
            query = """
                SELECT id, number, provider, provider_id, user_id, client_id, call_type, 
                       friendly_name, status, created_at, updated_at
                FROM phone_numbers
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting phone number: {e}")
            return None
    
    @staticmethod
    async def get_by_number(number: str) -> Optional[Dict[str, Any]]:
        """Get phone number by phone number string."""
        try:
            query = """
                SELECT id, number, provider, provider_id, user_id, client_id, call_type,
                       friendly_name, status, created_at, updated_at
                FROM phone_numbers
                WHERE number = $1
            """
            
            rows = await database.query(query, [number])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting phone number by number: {e}")
            return None
    
    @staticmethod
    async def get_by_user(user_id: str) -> List[Dict[str, Any]]:
        """Get all phone numbers for a user."""
        try:
            query = """
                SELECT id, number, provider, provider_id, user_id, client_id, call_type,
                       friendly_name, status, created_at, updated_at
                FROM phone_numbers
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting phone numbers for user: {e}")
            return []
    
    @staticmethod
    async def get_by_client(client_id: str) -> List[Dict[str, Any]]:
        """Get all phone numbers for a client."""
        try:
            query = """
                SELECT id, number, provider, provider_id, user_id, client_id, call_type,
                       friendly_name, status, created_at, updated_at
                FROM phone_numbers
                WHERE client_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(client_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting phone numbers for client: {e}")
            return []
    
    @staticmethod
    async def update(
        phone_number_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update phone number fields."""
        try:
            allowed_fields = ["call_type", "friendly_name", "status"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await PhoneNumberRepository.get_by_id(phone_number_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(phone_number_id)]
            
            query = f"""
                UPDATE phone_numbers
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, number, provider, user_id, client_id, call_type, friendly_name, status, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating phone number: {e}")
            return None
    
    @staticmethod
    async def delete(phone_number_id: str) -> bool:
        """Delete a phone number."""
        try:
            query = "DELETE FROM phone_numbers WHERE id = $1"
            await database.query(query, [UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting phone number: {e}")
            return False


class PhoneNumberAgentRepository:
    """Repository for phone number to agent assignments."""
    
    @staticmethod
    async def create(
        phone_number_id: str,
        agent_id: str,
        priority: int = 0,
        routing_strategy: str = "priority",
        is_primary: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Create a new assignment."""
        try:
            query = """
                INSERT INTO phone_number_agents
                (phone_number_id, agent_id, priority, routing_strategy, is_primary, status)
                VALUES ($1, $2, $3, $4, $5, 'active')
                RETURNING id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(phone_number_id), UUID(agent_id), priority, routing_strategy, is_primary]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating assignment: {e}")
            return None
    
    @staticmethod
    async def get_by_id(assignment_id: str) -> Optional[Dict[str, Any]]:
        """Get assignment by ID."""
        try:
            query = """
                SELECT id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at, updated_at
                FROM phone_number_agents
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(assignment_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting assignment: {e}")
            return None
    
    @staticmethod
    async def get_by_phone_and_agent(
        phone_number_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get assignment by phone number and agent."""
        try:
            query = """
                SELECT id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at, updated_at
                FROM phone_number_agents
                WHERE phone_number_id = $1 AND agent_id = $2
            """
            
            rows = await database.query(query, [UUID(phone_number_id), UUID(agent_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting assignment: {e}")
            return None
    
    @staticmethod
    async def get_by_phone(phone_number_id: str) -> List[Dict[str, Any]]:
        """Get all assignments for a phone number."""
        try:
            query = """
                SELECT id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at, updated_at
                FROM phone_number_agents
                WHERE phone_number_id = $1
                ORDER BY priority ASC, created_at ASC
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting assignments for phone: {e}")
            return []
    
    @staticmethod
    async def get_by_agent(agent_id: str) -> List[Dict[str, Any]]:
        """Get all assignments for an agent."""
        try:
            query = """
                SELECT id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at, updated_at
                FROM phone_number_agents
                WHERE agent_id = $1
                ORDER BY priority ASC, created_at ASC
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting assignments for agent: {e}")
            return []
    
    @staticmethod
    async def update(
        assignment_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update assignment fields."""
        try:
            allowed_fields = ["priority", "routing_strategy", "is_primary", "status"]
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await PhoneNumberAgentRepository.get_by_id(assignment_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [UUID(assignment_id)]
            
            query = f"""
                UPDATE phone_number_agents
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
                RETURNING id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating assignment: {e}")
            return None
    
    @staticmethod
    async def delete(assignment_id: str) -> bool:
        """Delete an assignment."""
        try:
            query = "DELETE FROM phone_number_agents WHERE id = $1"
            await database.query(query, [UUID(assignment_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting assignment: {e}")
            return False
