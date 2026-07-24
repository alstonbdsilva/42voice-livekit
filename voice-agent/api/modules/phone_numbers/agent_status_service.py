"""
Agent Status Service.
Manages agent availability, capacity, and call tracking.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database
from api.services.agent_routing_service import AgentRoutingService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.agent_status_service")


class AgentStatusService:
    """Service for managing agent status and availability."""
    
    @staticmethod
    async def initialize_agent_status(
        agent_id: str,
        max_concurrent_calls: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize agent status record.
        Called when agent is created.
        """
        try:
            query = """
                INSERT INTO agent_status 
                (agent_id, availability, max_concurrent_calls, current_active_calls, today_calls)
                VALUES ($1, 'available', $2, 0, 0)
                ON CONFLICT (agent_id) DO NOTHING
                RETURNING id, agent_id, availability, current_active_calls, max_concurrent_calls, today_calls
            """
            
            rows = await database.query(query, [UUID(agent_id), max_concurrent_calls])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing agent status: {e}")
            return None
    
    @staticmethod
    async def get_agent_status(agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent status."""
        try:
            query = """
                SELECT id, agent_id, availability, current_active_calls, 
                       max_concurrent_calls, today_calls, last_call_at, last_seen, updated_at
                FROM agent_status
                WHERE agent_id = $1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return None
    
    @staticmethod
    async def set_available(agent_id: str) -> bool:
        """Set agent to available."""
        return await AgentRoutingService.update_agent_availability(
            agent_id,
            AgentRoutingService.AVAILABILITY_AVAILABLE
        )
    
    @staticmethod
    async def set_busy(agent_id: str) -> bool:
        """Set agent to busy."""
        return await AgentRoutingService.update_agent_availability(
            agent_id,
            AgentRoutingService.AVAILABILITY_BUSY
        )
    
    @staticmethod
    async def set_offline(agent_id: str) -> bool:
        """Set agent to offline."""
        return await AgentRoutingService.update_agent_availability(
            agent_id,
            AgentRoutingService.AVAILABILITY_OFFLINE
        )
    
    @staticmethod
    async def set_paused(agent_id: str) -> bool:
        """Set agent to paused."""
        return await AgentRoutingService.update_agent_availability(
            agent_id,
            AgentRoutingService.AVAILABILITY_PAUSED
        )
    
    @staticmethod
    async def set_maintenance(agent_id: str) -> bool:
        """Set agent to maintenance."""
        return await AgentRoutingService.update_agent_availability(
            agent_id,
            AgentRoutingService.AVAILABILITY_MAINTENANCE
        )
    
    @staticmethod
    async def increment_active_calls(agent_id: str) -> bool:
        """Increment active call count."""
        return await AgentRoutingService.increment_active_calls(agent_id)
    
    @staticmethod
    async def decrement_active_calls(agent_id: str) -> bool:
        """Decrement active call count."""
        return await AgentRoutingService.decrement_active_calls(agent_id)
    
    @staticmethod
    async def increment_today_calls(agent_id: str) -> bool:
        """Increment today's call count."""
        try:
            query = """
                UPDATE agent_status 
                SET today_calls = today_calls + 1, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing today calls: {e}")
            return False
    
    @staticmethod
    async def update_max_concurrent_calls(
        agent_id: str,
        max_concurrent_calls: int
    ) -> bool:
        """Update max concurrent calls for agent."""
        try:
            if max_concurrent_calls <= 0:
                logger.error("Max concurrent calls must be > 0")
                return False
            
            query = """
                UPDATE agent_status 
                SET max_concurrent_calls = $1, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            await database.query(query, [max_concurrent_calls, UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating max concurrent calls: {e}")
            return False
    
    @staticmethod
    async def reset_daily_stats(agent_id: str) -> bool:
        """Reset daily call count (called at midnight)."""
        try:
            query = """
                UPDATE agent_status 
                SET today_calls = 0, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error resetting daily stats: {e}")
            return False
    
    @staticmethod
    async def get_agents_by_availability(
        availability: str,
        limit: int = 100
    ) -> list:
        """Get agents with specific availability status."""
        try:
            query = """
                SELECT a.id, a.name, a.type, a.status, 
                       s.availability, s.current_active_calls, s.max_concurrent_calls
                FROM agents a
                LEFT JOIN agent_status s ON a.id = s.agent_id
                WHERE s.availability = $1 AND a.status = 'active'
                LIMIT $2
            """
            
            rows = await database.query(query, [availability, limit])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agents by availability: {e}")
            return []
    
    @staticmethod
    async def get_agents_at_capacity() -> list:
        """Get agents that are at or exceeding capacity."""
        try:
            query = """
                SELECT a.id, a.name, a.type,
                       s.current_active_calls, s.max_concurrent_calls
                FROM agents a
                JOIN agent_status s ON a.id = s.agent_id
                WHERE s.current_active_calls >= s.max_concurrent_calls
                AND a.status = 'active'
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting agents at capacity: {e}")
            return []
