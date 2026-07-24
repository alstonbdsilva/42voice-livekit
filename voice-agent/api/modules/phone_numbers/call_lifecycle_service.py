"""
Call Lifecycle Service.
Manages call state transitions and metric updates.
Reusable by inbound, outbound, campaigns, queues, and IVR services.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.services.agent_routing_service import AgentRoutingService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.call_lifecycle_service")


class CallLifecycleService:
    """Service for managing call lifecycle and agent metrics."""
    
    @staticmethod
    async def on_call_started(agent_id: str) -> bool:
        """
        Called when a call is initiated to an agent.
        
        Updates:
        - Increment active calls
        - Set last_call_started
        - Update availability if at capacity
        """
        try:
            # Increment active calls
            await AgentRoutingService.increment_active_calls(agent_id)
            
            # Update last_call_started
            query = """
                UPDATE agent_status 
                SET last_call_started = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            
            # Check if at capacity and update availability
            status = await AgentRoutingService.get_agent_status(agent_id)
            if status and status["current_active_calls"] >= status["max_concurrent_calls"]:
                await AgentRoutingService.update_agent_availability(
                    agent_id,
                    AgentRoutingService.AVAILABILITY_BUSY
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error on call started: {e}")
            return False
    
    @staticmethod
    async def on_call_answered(agent_id: str) -> bool:
        """
        Called when agent answers the call.
        
        Updates:
        - Increment answered_calls
        - Update last_call_started timestamp
        """
        try:
            query = """
                UPDATE agent_status 
                SET answered_calls = answered_calls + 1,
                    last_call_started = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error on call answered: {e}")
            return False
    
    @staticmethod
    async def on_call_completed(
        agent_id: str,
        call_duration_seconds: int
    ) -> bool:
        """
        Called when call completes successfully.
        
        Updates:
        - Decrement active calls
        - Increment total_calls
        - Increment today_calls
        - Update average_call_duration
        - Set last_call_ended
        - Update availability back to available
        """
        try:
            # Get current status
            status = await AgentRoutingService.get_agent_status(agent_id)
            if not status:
                return False
            
            # Calculate new average
            total_calls = status["total_calls"] + 1
            current_avg = status["average_call_duration"] or 0
            new_avg = int((current_avg * status["total_calls"] + call_duration_seconds) / total_calls)
            
            # Update metrics
            query = """
                UPDATE agent_status 
                SET current_active_calls = GREATEST(0, current_active_calls - 1),
                    total_calls = total_calls + 1,
                    today_calls = today_calls + 1,
                    average_call_duration = $1,
                    last_call_ended = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            await database.query(query, [new_avg, UUID(agent_id)])
            
            # Update availability back to available if not paused/offline
            current_status = await AgentRoutingService.get_agent_status(agent_id)
            if current_status and current_status["availability"] == AgentRoutingService.AVAILABILITY_BUSY:
                await AgentRoutingService.update_agent_availability(
                    agent_id,
                    AgentRoutingService.AVAILABILITY_AVAILABLE
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error on call completed: {e}")
            return False
    
    @staticmethod
    async def on_call_failed(agent_id: str) -> bool:
        """
        Called when call fails (e.g., agent rejects, transfer fails).
        
        Updates:
        - Decrement active calls
        - Increment failed_calls
        - Set last_call_ended
        - Update availability back to available
        """
        try:
            query = """
                UPDATE agent_status 
                SET current_active_calls = GREATEST(0, current_active_calls - 1),
                    failed_calls = failed_calls + 1,
                    last_call_ended = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            
            # Update availability back to available if not paused/offline
            status = await AgentRoutingService.get_agent_status(agent_id)
            if status and status["availability"] == AgentRoutingService.AVAILABILITY_BUSY:
                await AgentRoutingService.update_agent_availability(
                    agent_id,
                    AgentRoutingService.AVAILABILITY_AVAILABLE
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error on call failed: {e}")
            return False
    
    @staticmethod
    async def on_call_missed(agent_id: str) -> bool:
        """
        Called when call goes unanswered/missed.
        
        Updates:
        - Decrement active calls
        - Increment missed_calls
        - Set last_call_ended
        - Update availability back to available
        """
        try:
            query = """
                UPDATE agent_status 
                SET current_active_calls = GREATEST(0, current_active_calls - 1),
                    missed_calls = missed_calls + 1,
                    last_call_ended = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            
            # Update availability back to available if not paused/offline
            status = await AgentRoutingService.get_agent_status(agent_id)
            if status and status["availability"] == AgentRoutingService.AVAILABILITY_BUSY:
                await AgentRoutingService.update_agent_availability(
                    agent_id,
                    AgentRoutingService.AVAILABILITY_AVAILABLE
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error on call missed: {e}")
            return False
    
    @staticmethod
    async def get_agent_metrics(agent_id: str) -> Optional[dict]:
        """Get comprehensive agent metrics."""
        try:
            query = """
                SELECT 
                    agent_id,
                    availability,
                    current_active_calls,
                    max_concurrent_calls,
                    answered_calls,
                    missed_calls,
                    failed_calls,
                    average_call_duration,
                    total_calls,
                    today_calls,
                    last_call_started,
                    last_call_ended,
                    last_heartbeat,
                    health_status,
                    updated_at
                FROM agent_status
                WHERE agent_id = $1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting agent metrics: {e}")
            return None
