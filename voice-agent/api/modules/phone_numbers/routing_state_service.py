"""
Routing State Service.
Manages persistent routing state for round-robin and other stateful strategies.
Designed to work with database or Redis without major refactoring.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.routing_state_service")


class RoutingStateService:
    """Service for managing persistent routing state."""
    
    @staticmethod
    async def initialize_state(
        phone_number_id: str,
        routing_strategy: str
    ) -> Optional[Dict[str, Any]]:
        """Initialize routing state for a phone number."""
        try:
            query = """
                INSERT INTO routing_state (phone_number_id, routing_strategy, last_selected_agent_id)
                VALUES ($1, $2, NULL)
                ON CONFLICT (phone_number_id) DO UPDATE 
                SET routing_strategy = $2, updated_at = CURRENT_TIMESTAMP
                RETURNING id, phone_number_id, routing_strategy, last_selected_agent_id, updated_at
            """
            
            rows = await database.query(query, [UUID(phone_number_id), routing_strategy])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing routing state: {e}")
            return None
    
    @staticmethod
    async def get_state(phone_number_id: str) -> Optional[Dict[str, Any]]:
        """Get routing state for a phone number."""
        try:
            query = """
                SELECT id, phone_number_id, routing_strategy, last_selected_agent_id, updated_at
                FROM routing_state
                WHERE phone_number_id = $1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting routing state: {e}")
            return None
    
    @staticmethod
    async def update_last_selected(
        phone_number_id: str,
        agent_id: str
    ) -> bool:
        """Update the last selected agent for round-robin."""
        try:
            query = """
                UPDATE routing_state 
                SET last_selected_agent_id = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [UUID(agent_id), UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating last selected agent: {e}")
            return False
    
    @staticmethod
    async def update_strategy(
        phone_number_id: str,
        routing_strategy: str
    ) -> bool:
        """Update routing strategy."""
        try:
            query = """
                UPDATE routing_state 
                SET routing_strategy = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [routing_strategy, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating routing strategy: {e}")
            return False
    
    @staticmethod
    async def get_next_round_robin_agent(
        phone_number_id: str,
        available_agents: list
    ) -> Optional[Dict[str, Any]]:
        """
        Get next agent in round-robin sequence.
        Survives application restart by reading from database.
        """
        try:
            if not available_agents:
                return None
            
            state = await RoutingStateService.get_state(phone_number_id)
            last_selected_id = state.get("last_selected_agent_id") if state else None
            
            # Find index of last selected agent
            last_index = -1
            if last_selected_id:
                for i, agent in enumerate(available_agents):
                    if str(agent.get("agent_id")) == str(last_selected_id):
                        last_index = i
                        break
            
            # Select next agent (wrap around if at end)
            next_index = (last_index + 1) % len(available_agents)
            next_agent = available_agents[next_index]
            
            # Update state
            await RoutingStateService.update_last_selected(
                phone_number_id,
                str(next_agent.get("agent_id"))
            )
            
            return next_agent
            
        except Exception as e:
            logger.error(f"Error getting next round-robin agent: {e}")
            return available_agents[0] if available_agents else None
    
    @staticmethod
    async def reset_state(phone_number_id: str) -> bool:
        """Reset routing state (useful when agents change)."""
        try:
            query = """
                UPDATE routing_state 
                SET last_selected_agent_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $1
            """
            
            await database.query(query, [UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error resetting routing state: {e}")
            return False
