"""
Agent Routing Service.
Production-grade intelligent routing engine with availability management,
concurrent call limits, failover, and multiple routing strategies.
"""

import logging
import random
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.services.agent_routing")


class AgentRoutingService:
    """Production-grade routing engine with availability, capacity, and failover support."""
    
    # Routing strategies
    STRATEGY_PRIMARY_FIRST = "primary_first"
    STRATEGY_PRIORITY = "priority"
    STRATEGY_ROUND_ROBIN = "round_robin"
    STRATEGY_LEAST_ACTIVE = "least_active"
    STRATEGY_LEAST_BUSY = "least_busy"
    STRATEGY_RANDOM = "random"
    STRATEGY_FAILOVER = "failover"
    
    SUPPORTED_STRATEGIES = [
        STRATEGY_PRIMARY_FIRST,
        STRATEGY_PRIORITY,
        STRATEGY_ROUND_ROBIN,
        STRATEGY_LEAST_ACTIVE,
        STRATEGY_LEAST_BUSY,
        STRATEGY_RANDOM,
        STRATEGY_FAILOVER
    ]
    
    # Availability statuses
    AVAILABILITY_AVAILABLE = "available"
    AVAILABILITY_BUSY = "busy"
    AVAILABILITY_OFFLINE = "offline"
    AVAILABILITY_PAUSED = "paused"
    AVAILABILITY_MAINTENANCE = "maintenance"
    
    AVAILABLE_STATUSES = [AVAILABILITY_AVAILABLE]
    UNAVAILABLE_STATUSES = [AVAILABILITY_OFFLINE, AVAILABILITY_PAUSED, AVAILABILITY_MAINTENANCE]
    
    @staticmethod
    async def get_assigned_agents(
        phone_number_id: str,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all agents assigned to a phone number.
        
        Args:
            phone_number_id: UUID of the phone number
            include_inactive: Whether to include inactive assignments
            
        Returns:
            List of agent assignments with agent details
        """
        try:
            status_filter = "" if include_inactive else "AND pna.status = 'active' AND a.status = 'active'"
            
            query = f"""
                SELECT 
                    pna.id as assignment_id,
                    pna.agent_id,
                    pna.priority,
                    pna.routing_strategy,
                    pna.is_primary,
                    pna.status as assignment_status,
                    a.id,
                    a.name,
                    a.type,
                    a.call_type,
                    a.status,
                    a.user_id,
                    a.client_id
                FROM phone_number_agents pna
                JOIN agents a ON pna.agent_id = a.id
                WHERE pna.phone_number_id = $1 {status_filter}
                ORDER BY pna.priority ASC, pna.created_at ASC
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting assigned agents for phone {phone_number_id}: {e}")
            return []
    
    @staticmethod
    async def validate_agent_ownership(
        agent_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """
        Validate that an agent belongs to the same user/client.
        
        Args:
            agent_id: UUID of the agent
            user_id: UUID of the user
            client_id: Optional UUID of the client
            
        Returns:
            True if agent belongs to user, False otherwise
        """
        try:
            query = """
                SELECT id FROM agents 
                WHERE id = $1 AND (user_id = $2 OR client_id = $3)
            """
            rows = await database.query(query, [UUID(agent_id), UUID(user_id), UUID(client_id) if client_id else None])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error validating agent ownership: {e}")
            return False
    
    @staticmethod
    async def validate_phone_ownership(
        phone_number_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """
        Validate that a phone number belongs to the same user/client.
        
        Args:
            phone_number_id: UUID of the phone number
            user_id: UUID of the user
            client_id: Optional UUID of the client
            
        Returns:
            True if phone number belongs to user, False otherwise
        """
        try:
            query = """
                SELECT id FROM phone_numbers 
                WHERE id = $1 AND (user_id = $2 OR client_id = $3)
            """
            rows = await database.query(query, [UUID(phone_number_id), UUID(user_id), UUID(client_id) if client_id else None])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error validating phone ownership: {e}")
            return False
    
    @staticmethod
    async def check_duplicate_assignment(
        phone_number_id: str,
        agent_id: str
    ) -> bool:
        """
        Check if an agent is already assigned to a phone number.
        
        Args:
            phone_number_id: UUID of the phone number
            agent_id: UUID of the agent
            
        Returns:
            True if assignment exists, False otherwise
        """
        try:
            query = """
                SELECT id FROM phone_number_agents 
                WHERE phone_number_id = $1 AND agent_id = $2
            """
            rows = await database.query(query, [UUID(phone_number_id), UUID(agent_id)])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate assignment: {e}")
            return False
    
    @staticmethod
    async def validate_agent_active(agent_id: str) -> bool:
        """
        Validate that an agent is active and not deleted.
        
        Args:
            agent_id: UUID of the agent
            
        Returns:
            True if agent is active, False otherwise
        """
        try:
            query = "SELECT id FROM agents WHERE id = $1 AND status = 'active'"
            rows = await database.query(query, [UUID(agent_id)])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error validating agent active status: {e}")
            return False
    
    @staticmethod
    async def validate_phone_active(phone_number_id: str) -> bool:
        """
        Validate that a phone number is active and not deleted.
        
        Args:
            phone_number_id: UUID of the phone number
            
        Returns:
            True if phone number is active, False otherwise
        """
        try:
            query = "SELECT id FROM phone_numbers WHERE id = $1 AND status = 'active'"
            rows = await database.query(query, [UUID(phone_number_id)])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error validating phone active status: {e}")
            return False
    
    @staticmethod
    async def validate_availability(agent_id: str) -> bool:
        """
        Check if agent is available for calls.
        
        Returns:
            True if agent is available, False otherwise
        """
        try:
            query = """
                SELECT availability FROM agent_status 
                WHERE agent_id = $1 AND availability = 'available'
            """
            rows = await database.query(query, [UUID(agent_id)])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error validating availability: {e}")
            return False
    
    @staticmethod
    async def validate_capacity(agent_id: str) -> bool:
        """
        Check if agent has capacity for another call.
        
        Returns:
            True if agent can accept calls, False if at capacity
        """
        try:
            query = """
                SELECT current_active_calls, max_concurrent_calls FROM agent_status 
                WHERE agent_id = $1
            """
            rows = await database.query(query, [UUID(agent_id)])
            
            if not rows:
                return True  # No status record, assume available
            
            status = rows[0]
            return status["current_active_calls"] < status["max_concurrent_calls"]
            
        except Exception as e:
            logger.error(f"Error validating capacity: {e}")
            return False
    
    @staticmethod
    async def get_agent_status(agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current agent status."""
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
    async def update_agent_availability(
        agent_id: str,
        availability: str,
        current_active_calls: Optional[int] = None
    ) -> bool:
        """Update agent availability status."""
        try:
            if availability not in [
                AgentRoutingService.AVAILABILITY_AVAILABLE,
                AgentRoutingService.AVAILABILITY_BUSY,
                AgentRoutingService.AVAILABILITY_OFFLINE,
                AgentRoutingService.AVAILABILITY_PAUSED,
                AgentRoutingService.AVAILABILITY_MAINTENANCE
            ]:
                logger.error(f"Invalid availability status: {availability}")
                return False
            
            if current_active_calls is not None:
                query = """
                    UPDATE agent_status 
                    SET availability = $1, current_active_calls = $2, updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = $3
                """
                await database.query(query, [availability, current_active_calls, UUID(agent_id)])
            else:
                query = """
                    UPDATE agent_status 
                    SET availability = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = $2
                """
                await database.query(query, [availability, UUID(agent_id)])
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating agent availability: {e}")
            return False
    
    @staticmethod
    async def increment_active_calls(agent_id: str) -> bool:
        """Increment active call count."""
        try:
            query = """
                UPDATE agent_status 
                SET current_active_calls = current_active_calls + 1,
                    last_call_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing active calls: {e}")
            return False
    
    @staticmethod
    async def decrement_active_calls(agent_id: str) -> bool:
        """Decrement active call count."""
        try:
            query = """
                UPDATE agent_status 
                SET current_active_calls = GREATEST(0, current_active_calls - 1),
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $1
            """
            await database.query(query, [UUID(agent_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error decrementing active calls: {e}")
            return False
    
    @staticmethod
    async def select_primary_agent(
        phone_number_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Select the primary agent for a phone number.
        Validates availability and capacity.
        
        Returns:
            Primary agent or None if unavailable/at capacity
        """
        try:
            query = """
                SELECT pna.agent_id, a.id, a.name, a.type, a.status, a.user_id, a.client_id
                FROM phone_number_agents pna
                JOIN agents a ON pna.agent_id = a.id
                WHERE pna.phone_number_id = $1 AND pna.is_primary = TRUE AND a.status = 'active'
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            if not rows:
                return None
            
            agent = rows[0]
            agent_id = str(agent["agent_id"])
            
            # Check availability and capacity
            if not await AgentRoutingService.validate_availability(agent_id):
                logger.info(f"Primary agent {agent_id} not available")
                return None
            
            if not await AgentRoutingService.validate_capacity(agent_id):
                logger.info(f"Primary agent {agent_id} at capacity")
                return None
            
            return agent
            
        except Exception as e:
            logger.error(f"Error selecting primary agent: {e}")
            return None
    
    @staticmethod
    async def select_by_priority(
        agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select first available agent by priority."""
        try:
            for agent in agents:
                agent_id = str(agent["agent_id"])
                
                if not await AgentRoutingService.validate_availability(agent_id):
                    continue
                
                if not await AgentRoutingService.validate_capacity(agent_id):
                    continue
                
                return agent
            
            return None
            
        except Exception as e:
            logger.error(f"Error selecting by priority: {e}")
            return None
    
    @staticmethod
    async def select_by_least_active(
        agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select agent with fewest active calls."""
        try:
            available = []
            
            for agent in agents:
                agent_id = str(agent["agent_id"])
                
                if not await AgentRoutingService.validate_availability(agent_id):
                    continue
                
                if not await AgentRoutingService.validate_capacity(agent_id):
                    continue
                
                status = await AgentRoutingService.get_agent_status(agent_id)
                if status:
                    agent["current_active_calls"] = status["current_active_calls"]
                else:
                    agent["current_active_calls"] = 0
                
                available.append(agent)
            
            if not available:
                return None
            
            return min(available, key=lambda a: a.get("current_active_calls", 0))
            
        except Exception as e:
            logger.error(f"Error selecting by least active: {e}")
            return None
    
    @staticmethod
    async def select_by_least_busy(
        agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select agent with lowest active call ratio."""
        try:
            available = []
            
            for agent in agents:
                agent_id = str(agent["agent_id"])
                
                if not await AgentRoutingService.validate_availability(agent_id):
                    continue
                
                if not await AgentRoutingService.validate_capacity(agent_id):
                    continue
                
                status = await AgentRoutingService.get_agent_status(agent_id)
                if status:
                    ratio = status["current_active_calls"] / status["max_concurrent_calls"]
                    agent["busy_ratio"] = ratio
                else:
                    agent["busy_ratio"] = 0
                
                available.append(agent)
            
            if not available:
                return None
            
            return min(available, key=lambda a: a.get("busy_ratio", 0))
            
        except Exception as e:
            logger.error(f"Error selecting by least busy: {e}")
            return None
    
    @staticmethod
    async def select_by_round_robin(
        agents: List[Dict[str, Any]],
        phone_number_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Select next available agent in round-robin order.
        Persists state across application restarts.
        """
        try:
            available = []
            
            for agent in agents:
                agent_id = str(agent["agent_id"])
                
                if not await AgentRoutingService.validate_availability(agent_id):
                    continue
                
                if not await AgentRoutingService.validate_capacity(agent_id):
                    continue
                
                available.append(agent)
            
            if not available:
                return None
            
            # Use routing state service if phone_number_id provided
            if phone_number_id:
                from api.modules.phone_numbers.routing_state_service import RoutingStateService
                return await RoutingStateService.get_next_round_robin_agent(phone_number_id, available)
            
            # Fallback: return first available
            return available[0]
            
        except Exception as e:
            logger.error(f"Error selecting by round-robin: {e}")
            return available[0] if available else None
    
    @staticmethod
    async def select_by_random(
        agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select random available agent."""
        try:
            available = []
            
            for agent in agents:
                agent_id = str(agent["agent_id"])
                
                if not await AgentRoutingService.validate_availability(agent_id):
                    continue
                
                if not await AgentRoutingService.validate_capacity(agent_id):
                    continue
                
                available.append(agent)
            
            if not available:
                return None
            
            return random.choice(available)
            
        except Exception as e:
            logger.error(f"Error selecting by random: {e}")
            return None
    
    @staticmethod
    async def select_agent(
        phone_number_id: str,
        routing_strategy: Optional[str] = None,
        include_primary: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Intelligently select an agent for a call.
        
        Implements:
        1. Primary agent first (if enabled and available)
        2. Fallback to routing strategy
        3. Failover to next available agent
        
        Args:
            phone_number_id: UUID of the phone number
            routing_strategy: Override routing strategy
            include_primary: Whether to try primary agent first
            
        Returns:
            Selected agent or None if no agents available
        """
        try:
            # Try primary agent first
            if include_primary:
                primary = await AgentRoutingService.select_primary_agent(phone_number_id)
                if primary:
                    return primary
            
            # Get all assigned agents
            agents = await AgentRoutingService.get_assigned_agents(phone_number_id)
            
            if not agents:
                logger.warning(f"No agents assigned to phone {phone_number_id}")
                return None
            
            # Determine routing strategy
            if not routing_strategy:
                routing_strategy = agents[0].get("routing_strategy", AgentRoutingService.STRATEGY_PRIORITY)
            
            # Validate strategy
            if routing_strategy not in AgentRoutingService.SUPPORTED_STRATEGIES:
                logger.warning(f"Unknown routing strategy: {routing_strategy}, defaulting to priority")
                routing_strategy = AgentRoutingService.STRATEGY_PRIORITY
            
            # Apply routing strategy
            if routing_strategy == AgentRoutingService.STRATEGY_PRIMARY_FIRST:
                return await AgentRoutingService.select_primary_agent(phone_number_id)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_PRIORITY:
                return await AgentRoutingService.select_by_priority(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_ROUND_ROBIN:
                return await AgentRoutingService.select_by_round_robin(agents, phone_number_id)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_LEAST_ACTIVE:
                return await AgentRoutingService.select_by_least_active(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_LEAST_BUSY:
                return await AgentRoutingService.select_by_least_busy(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_RANDOM:
                return await AgentRoutingService.select_by_random(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_FAILOVER:
                return await AgentRoutingService.select_by_priority(agents)
            
            return await AgentRoutingService.select_by_priority(agents)
            
        except Exception as e:
            logger.error(f"Error selecting agent for phone {phone_number_id}: {e}")
            return None
    
    @staticmethod
    async def select_agent_by_capability(
        capability_id: str,
        routing_strategy: str = STRATEGY_PRIORITY
    ) -> Optional[Dict[str, Any]]:
        """
        Select an agent based on capability.
        Used for intent-based routing.
        
        Args:
            capability_id: UUID of the capability
            routing_strategy: Routing strategy to use
            
        Returns:
            Selected agent or None if no agents available
        """
        try:
            from api.modules.phone_numbers.capability_service import CapabilityService
            
            # Get agents with this capability
            agents = await CapabilityService.get_agents_by_capability(capability_id)
            
            if not agents:
                logger.warning(f"No agents with capability {capability_id}")
                return None
            
            # Apply routing strategy
            if routing_strategy == AgentRoutingService.STRATEGY_PRIORITY:
                return await AgentRoutingService.select_by_priority(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_ROUND_ROBIN:
                return await AgentRoutingService.select_by_round_robin(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_LEAST_ACTIVE:
                return await AgentRoutingService.select_by_least_active(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_LEAST_BUSY:
                return await AgentRoutingService.select_by_least_busy(agents)
            
            elif routing_strategy == AgentRoutingService.STRATEGY_RANDOM:
                return await AgentRoutingService.select_by_random(agents)
            
            return await AgentRoutingService.select_by_priority(agents)
            
        except Exception as e:
            logger.error(f"Error selecting agent by capability: {e}")
            return None
    
    @staticmethod
    async def get_phone_numbers_for_agent(
        agent_id: str,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all phone numbers assigned to an agent.
        
        Args:
            agent_id: UUID of the agent
            include_inactive: Whether to include inactive assignments
            
        Returns:
            List of phone number assignments
        """
        try:
            status_filter = "" if include_inactive else "AND pna.status = 'active' AND pn.status = 'active'"
            
            query = f"""
                SELECT 
                    pna.id as assignment_id,
                    pna.phone_number_id,
                    pna.priority,
                    pna.routing_strategy,
                    pna.is_primary,
                    pna.status as assignment_status,
                    pn.id,
                    pn.number,
                    pn.provider,
                    pn.call_type,
                    pn.friendly_name,
                    pn.status
                FROM phone_number_agents pna
                JOIN phone_numbers pn ON pna.phone_number_id = pn.id
                WHERE pna.agent_id = $1 {status_filter}
                ORDER BY pna.priority ASC, pna.created_at ASC
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting phone numbers for agent {agent_id}: {e}")
            return []
    
    @staticmethod
    async def create_assignment(
        phone_number_id: str,
        agent_id: str,
        priority: int = 0,
        routing_strategy: str = STRATEGY_PRIORITY,
        is_primary: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new phone number to agent assignment.
        
        Args:
            phone_number_id: UUID of the phone number
            agent_id: UUID of the agent
            priority: Priority level (lower = higher priority)
            routing_strategy: Routing strategy for this assignment
            is_primary: Whether this is the primary agent
            
        Returns:
            Created assignment or None on error
        """
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
    async def delete_assignment(assignment_id: str) -> bool:
        """
        Delete a phone number to agent assignment.
        
        Args:
            assignment_id: UUID of the assignment
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            query = "DELETE FROM phone_number_agents WHERE id = $1"
            await database.query(query, [UUID(assignment_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting assignment: {e}")
            return False
    
    @staticmethod
    async def update_routing_strategy(
        phone_number_id: str,
        routing_strategy: str
    ) -> bool:
        """
        Update the routing strategy for a phone number.
        
        Args:
            phone_number_id: UUID of the phone number
            routing_strategy: New routing strategy
            
        Returns:
            True if updated, False otherwise
        """
        try:
            if routing_strategy not in AgentRoutingService.SUPPORTED_STRATEGIES:
                logger.error(f"Invalid routing strategy: {routing_strategy}")
                return False
            
            query = """
                UPDATE phone_number_agents 
                SET routing_strategy = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [routing_strategy, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating routing strategy: {e}")
            return False
