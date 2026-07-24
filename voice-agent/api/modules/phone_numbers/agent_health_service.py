"""
Agent Health Service.
Manages agent heartbeat and health status monitoring.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database
from api.services.agent_routing_service import AgentRoutingService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.agent_health_service")


class AgentHealthService:
    """Service for monitoring agent health and heartbeat."""
    
    # Health status constants
    HEALTH_HEALTHY = "healthy"
    HEALTH_UNHEALTHY = "unhealthy"
    HEALTH_UNKNOWN = "unknown"
    
    # Heartbeat timeout in seconds
    HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes
    
    @staticmethod
    async def record_heartbeat(agent_id: str) -> bool:
        """
        Record agent heartbeat.
        Called periodically by agent to indicate it's alive.
        """
        try:
            query = """
                UPDATE agent_status 
                SET last_heartbeat = CURRENT_TIMESTAMP,
                    health_status = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            
            await database.query(query, [AgentHealthService.HEALTH_HEALTHY, UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error recording heartbeat: {e}")
            return False
    
    @staticmethod
    async def get_health_status(agent_id: str) -> Optional[str]:
        """Get agent health status."""
        try:
            query = """
                SELECT health_status FROM agent_status WHERE agent_id = $1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows[0]["health_status"] if rows else AgentHealthService.HEALTH_UNKNOWN
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return AgentHealthService.HEALTH_UNKNOWN
    
    @staticmethod
    async def validate_health(agent_id: str) -> bool:
        """
        Validate agent health.
        Returns True if agent is healthy, False if unhealthy/unknown.
        """
        try:
            query = """
                SELECT health_status, last_heartbeat FROM agent_status WHERE agent_id = $1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            if not rows:
                return False
            
            status = rows[0]
            health = status["health_status"]
            last_heartbeat = status["last_heartbeat"]
            
            # Check if health is explicitly healthy
            if health == AgentHealthService.HEALTH_HEALTHY:
                # Check if heartbeat is still recent
                if last_heartbeat:
                    age = datetime.now(timezone.utc) - last_heartbeat.astimezone(timezone.utc)
                    if age > timedelta(seconds=AgentHealthService.HEARTBEAT_TIMEOUT_SECONDS):
                        # Heartbeat expired, mark as unhealthy
                        await AgentHealthService.mark_unhealthy(agent_id)
                        return False
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating health: {e}")
            return False
    
    @staticmethod
    async def mark_healthy(agent_id: str) -> bool:
        """Mark agent as healthy."""
        try:
            query = """
                UPDATE agent_status 
                SET health_status = $1, last_heartbeat = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            
            await database.query(query, [AgentHealthService.HEALTH_HEALTHY, UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error marking agent healthy: {e}")
            return False
    
    @staticmethod
    async def mark_unhealthy(agent_id: str) -> bool:
        """
        Mark agent as unhealthy.
        Automatically sets agent to offline to prevent routing.
        """
        try:
            query = """
                UPDATE agent_status 
                SET health_status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            
            await database.query(query, [AgentHealthService.HEALTH_UNHEALTHY, UUID(agent_id)])
            
            # Also set agent to offline to prevent routing
            await AgentRoutingService.update_agent_availability(
                agent_id,
                AgentRoutingService.AVAILABILITY_OFFLINE
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking agent unhealthy: {e}")
            return False
    
    @staticmethod
    async def mark_unknown(agent_id: str) -> bool:
        """Mark agent health status as unknown."""
        try:
            query = """
                UPDATE agent_status 
                SET health_status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2
            """
            
            await database.query(query, [AgentHealthService.HEALTH_UNKNOWN, UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error marking agent unknown: {e}")
            return False
    
    @staticmethod
    async def check_expired_heartbeats() -> List[str]:
        """
        Check for agents with expired heartbeats.
        Should be called periodically (e.g., every minute).
        Returns list of agent IDs that became unhealthy.
        """
        try:
            timeout_seconds = AgentHealthService.HEARTBEAT_TIMEOUT_SECONDS
            
            query = f"""
                SELECT agent_id FROM agent_status 
                WHERE health_status = 'healthy' 
                AND last_heartbeat IS NOT NULL
                AND (CURRENT_TIMESTAMP - last_heartbeat) > INTERVAL '{timeout_seconds} seconds'
            """
            
            rows = await database.query(query)
            unhealthy_agents = []
            
            for row in rows:
                agent_id = str(row["agent_id"])
                await AgentHealthService.mark_unhealthy(agent_id)
                unhealthy_agents.append(agent_id)
            
            if unhealthy_agents:
                logger.info(f"Marked {len(unhealthy_agents)} agents as unhealthy due to expired heartbeat")
            
            return unhealthy_agents
            
        except Exception as e:
            logger.error(f"Error checking expired heartbeats: {e}")
            return []
    
    @staticmethod
    async def get_unhealthy_agents() -> List[Dict[str, Any]]:
        """Get all unhealthy agents."""
        try:
            query = """
                SELECT a.id, a.name, a.type, s.health_status, s.last_heartbeat
                FROM agents a
                JOIN agent_status s ON a.id = s.agent_id
                WHERE s.health_status = 'unhealthy'
                AND a.status = 'active'
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting unhealthy agents: {e}")
            return []
