"""
Phone Numbers Service.
Business logic for phone number and agent assignment operations.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from api.modules.phone_numbers.repositories import PhoneNumberRepository, PhoneNumberAgentRepository
from api.services.agent_routing_service import AgentRoutingService
from api.modules.phone_numbers.agent_status_service import AgentStatusService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.services")


class PhoneNumberService:
    """Service for phone number operations."""
    
    def __init__(self):
        self.phone_repo = PhoneNumberRepository()
        self.assignment_repo = PhoneNumberAgentRepository()
        self.routing_service = AgentRoutingService()
    
    async def create_phone_number(
        self,
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
            # Check if number already exists
            existing = await self.phone_repo.get_by_number(number)
            if existing:
                logger.warning(f"Phone number {number} already exists")
                return None
            
            return await self.phone_repo.create(
                number=number,
                provider=provider,
                user_id=user_id,
                client_id=client_id,
                call_type=call_type,
                friendly_name=friendly_name,
                provider_id=provider_id
            )
            
        except Exception as e:
            logger.error(f"Error creating phone number: {e}")
            return None
    
    async def get_phone_number(self, phone_number_id: str) -> Optional[Dict[str, Any]]:
        """Get phone number details."""
        return await self.phone_repo.get_by_id(phone_number_id)
    
    async def get_user_phone_numbers(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all phone numbers for a user."""
        return await self.phone_repo.get_by_user(user_id)
    
    async def get_client_phone_numbers(self, client_id: str) -> List[Dict[str, Any]]:
        """Get all phone numbers for a client."""
        return await self.phone_repo.get_by_client(client_id)
    
    async def update_phone_number(
        self,
        phone_number_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update phone number details."""
        return await self.phone_repo.update(phone_number_id, **kwargs)
    
    async def delete_phone_number(self, phone_number_id: str) -> bool:
        """Delete a phone number."""
        return await self.phone_repo.delete(phone_number_id)


class PhoneNumberAgentService:
    """Service for phone number to agent assignments."""
    
    def __init__(self):
        self.assignment_repo = PhoneNumberAgentRepository()
        self.routing_service = AgentRoutingService()
    
    async def assign_agent(
        self,
        phone_number_id: str,
        agent_id: str,
        user_id: str,
        client_id: Optional[str] = None,
        priority: int = 0,
        routing_strategy: str = "priority",
        is_primary: bool = False,
        max_concurrent_calls: int = 5,
        business_hours_timezone: Optional[str] = None,
        after_hours_agent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Assign an agent to a phone number with validation.
        
        Validates:
        - Agent belongs to same user/client
        - Phone number belongs to same user/client
        - No duplicate assignments
        - Agent is active
        - Phone number is active
        - Priority is unique per phone number
        """
        try:
            # Validate priority uniqueness
            from api import database
            priority_check = await database.query(
                "SELECT 1 FROM phone_number_agent_priority_check WHERE phone_number_id = $1 AND priority = $2",
                [UUID(phone_number_id), priority]
            )
            if priority_check:
                logger.warning(f"Priority {priority} already exists for phone {phone_number_id}")
                return None
            # Validate phone number ownership
            if not await self.routing_service.validate_phone_ownership(phone_number_id, user_id, client_id):
                logger.warning(f"Phone number {phone_number_id} does not belong to user {user_id}")
                return None
            
            # Validate agent ownership
            if not await self.routing_service.validate_agent_ownership(agent_id, user_id, client_id):
                logger.warning(f"Agent {agent_id} does not belong to user {user_id}")
                return None
            
            # Check for duplicate assignment
            if await self.routing_service.check_duplicate_assignment(phone_number_id, agent_id):
                logger.warning(f"Agent {agent_id} is already assigned to phone {phone_number_id}")
                return None
            
            # Validate agent is active
            if not await self.routing_service.validate_agent_active(agent_id):
                logger.warning(f"Agent {agent_id} is not active")
                return None
            
            # Validate phone number is active
            if not await self.routing_service.validate_phone_active(phone_number_id):
                logger.warning(f"Phone number {phone_number_id} is not active")
                return None
            
            # Initialize agent status if not exists
            await AgentStatusService.initialize_agent_status(agent_id, max_concurrent_calls)
            
            # Create assignment
            assignment = await self.assignment_repo.create(
                phone_number_id=phone_number_id,
                agent_id=agent_id,
                priority=priority,
                routing_strategy=routing_strategy,
                is_primary=is_primary
            )
            
            # Register priority in check table
            if assignment:
                from api import database
                try:
                    await database.query(
                        "INSERT INTO phone_number_agent_priority_check (phone_number_id, priority) VALUES ($1, $2)",
                        [UUID(phone_number_id), priority]
                    )
                except Exception as e:
                    logger.warning(f"Could not register priority: {e}")
            
            # Update assignment with additional fields if needed
            if assignment and (business_hours_timezone or after_hours_agent_id or max_concurrent_calls != 5):
                from api import database
                query = """
                    UPDATE phone_number_agents 
                    SET max_concurrent_calls = $1, 
                        business_hours_timezone = $2,
                        after_hours_agent_id = $3,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $4
                    RETURNING id, phone_number_id, agent_id, priority, routing_strategy, is_primary, status, created_at
                """
                from uuid import UUID
                rows = await database.query(
                    query,
                    [max_concurrent_calls, business_hours_timezone, 
                     UUID(after_hours_agent_id) if after_hours_agent_id else None,
                     UUID(assignment["id"])]
                )
                return rows[0] if rows else assignment
            
            return assignment
            
        except Exception as e:
            logger.error(f"Error assigning agent: {e}")
            return None
    
    async def get_phone_agents(
        self,
        phone_number_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all agents assigned to a phone number.
        Validates ownership before returning.
        """
        try:
            # Validate ownership
            if not await self.routing_service.validate_phone_ownership(phone_number_id, user_id, client_id):
                logger.warning(f"Phone number {phone_number_id} does not belong to user {user_id}")
                return []
            
            return await self.routing_service.get_assigned_agents(phone_number_id)
            
        except Exception as e:
            logger.error(f"Error getting phone agents: {e}")
            return []
    
    async def get_agent_phones(
        self,
        agent_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all phone numbers assigned to an agent.
        Validates ownership before returning.
        """
        try:
            # Validate ownership
            if not await self.routing_service.validate_agent_ownership(agent_id, user_id, client_id):
                logger.warning(f"Agent {agent_id} does not belong to user {user_id}")
                return []
            
            return await self.routing_service.get_phone_numbers_for_agent(agent_id)
            
        except Exception as e:
            logger.error(f"Error getting agent phones: {e}")
            return []
    
    async def remove_agent(
        self,
        phone_number_id: str,
        agent_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """
        Remove an agent from a phone number.
        Validates ownership before removing.
        """
        try:
            # Validate ownership
            if not await self.routing_service.validate_phone_ownership(phone_number_id, user_id, client_id):
                logger.warning(f"Phone number {phone_number_id} does not belong to user {user_id}")
                return False
            
            if not await self.routing_service.validate_agent_ownership(agent_id, user_id, client_id):
                logger.warning(f"Agent {agent_id} does not belong to user {user_id}")
                return False
            
            # Get assignment
            assignment = await self.assignment_repo.get_by_phone_and_agent(phone_number_id, agent_id)
            if not assignment:
                logger.warning(f"Assignment not found for phone {phone_number_id} and agent {agent_id}")
                return False
            
            # Delete priority check entry
            from api import database
            try:
                await database.query(
                    "DELETE FROM phone_number_agent_priority_check WHERE phone_number_id = $1 AND priority = $2",
                    [UUID(phone_number_id), assignment["priority"]]
                )
            except Exception as e:
                logger.warning(f"Could not delete priority check: {e}")
            
            # Delete assignment
            return await self.assignment_repo.delete(assignment["id"])
            
        except Exception as e:
            logger.error(f"Error removing agent: {e}")
            return False
    
    async def update_routing_strategy(
        self,
        phone_number_id: str,
        routing_strategy: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> bool:
        """
        Update the routing strategy for a phone number.
        Validates ownership before updating.
        """
        try:
            # Validate ownership
            if not await self.routing_service.validate_phone_ownership(phone_number_id, user_id, client_id):
                logger.warning(f"Phone number {phone_number_id} does not belong to user {user_id}")
                return False
            
            return await self.routing_service.update_routing_strategy(phone_number_id, routing_strategy)
            
        except Exception as e:
            logger.error(f"Error updating routing strategy: {e}")
            return False
    
    async def select_agent_for_call(
        self,
        phone_number_id: str,
        routing_strategy: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Select an agent for an incoming call.
        Used by inbound call handler.
        """
        try:
            return await self.routing_service.select_agent(phone_number_id, routing_strategy)
            
        except Exception as e:
            logger.error(f"Error selecting agent for call: {e}")
            return None
