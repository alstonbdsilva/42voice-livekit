"""
Phone Numbers Service.
Manages phone numbers, provisioning, and routing.
"""

import logging
import re
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.phone_numbers.phone_provider import (
    PhoneProvider,
    TwilioProvider,
    TelnyxProvider,
    SIPProvider
)
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.phone_numbers_service")


class PhoneNumbersService:
    """Service for managing phone numbers."""
    
    _providers = {
        "twilio": TwilioProvider(),
        "telnyx": TelnyxProvider(),
        "plivo": TwilioProvider(),  # Placeholder
        "signalwire": TwilioProvider(),  # Placeholder
        "exotel": TwilioProvider(),  # Placeholder
        "sip": SIPProvider()
    }
    
    @staticmethod
    async def search_numbers(
        tenant_id: str,
        provider: str,
        country_code: str,
        area_code: Optional[str] = None,
        contains: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search available phone numbers."""
        try:
            phone_provider = PhoneNumbersService._providers.get(provider)
            if not phone_provider:
                logger.error(f"Unknown provider: {provider}")
                return []
            
            numbers = await phone_provider.search_numbers(
                country_code,
                area_code,
                contains,
                limit
            )
            
            return numbers
            
        except Exception as e:
            logger.error(f"Error searching numbers: {e}")
            return []
    
    @staticmethod
    async def purchase_number(
        tenant_id: str,
        provider: str,
        number: str,
        friendly_name: Optional[str] = None,
        country_code: Optional[str] = None,
        region: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Purchase a phone number."""
        try:
            # Validate E164 format
            if not PhoneNumbersService._validate_e164(number):
                logger.error(f"Invalid E164 format: {number}")
                return None
            
            # Check if number already owned
            existing = await PhoneNumbersService.get_number_by_e164(tenant_id, number)
            if existing:
                logger.warning(f"Number already owned: {number}")
                return None
            
            # Purchase from provider
            phone_provider = PhoneNumbersService._providers.get(provider)
            if not phone_provider:
                logger.error(f"Unknown provider: {provider}")
                return None
            
            provider_result = await phone_provider.purchase_number(number, friendly_name)
            if not provider_result:
                logger.error(f"Failed to purchase number from {provider}")
                return None
            
            # Store in database
            query = """
                INSERT INTO phone_numbers 
                (tenant_id, provider, provider_number_id, e164_number, friendly_name,
                 country_code, region, timezone, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active')
                RETURNING id, tenant_id, provider, e164_number, friendly_name, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(tenant_id), provider, provider_result.get("number"), number,
                 friendly_name, country_code, region, timezone]
            )
            
            if rows:
                phone_number = rows[0]
                
                # Publish event
                await EventBus.publish_call_started(tenant_id, "phone_number_purchased")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    str(phone_number.get("id")),
                    tenant_id,
                    "purchased",
                    "system",
                    None,
                    {"provider": provider, "number": number}
                )
                
                return phone_number
            
            return None
            
        except Exception as e:
            logger.error(f"Error purchasing number: {e}")
            return None
    
    @staticmethod
    async def release_number(
        tenant_id: str,
        phone_number_id: str
    ) -> bool:
        """Release a phone number."""
        try:
            # Get phone number
            phone_number = await PhoneNumbersService.get_number(phone_number_id)
            if not phone_number or str(phone_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {phone_number_id}")
                return False
            
            # Release from provider
            phone_provider = PhoneNumbersService._providers.get(phone_number.get("provider"))
            if phone_provider:
                await phone_provider.release_number(phone_number.get("e164_number"))
            
            # Update status
            query = """
                UPDATE phone_numbers
                SET status = 'released', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(query, [UUID(phone_number_id)])
            
            # Publish event
            await EventBus.publish_call_started(tenant_id, "phone_number_released")
            
            # Log audit
            await PhoneNumbersService._log_audit(
                phone_number_id,
                tenant_id,
                "released",
                "system",
                None,
                {"number": phone_number.get("e164_number")}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error releasing number: {e}")
            return False
    
    @staticmethod
    async def assign_number(
        phone_number_id: str,
        assignment_type: str,
        workflow_id: Optional[str] = None,
        agent_group_id: Optional[str] = None,
        router_agent_id: Optional[str] = None,
        default_agent_id: Optional[str] = None,
        priority: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Assign phone number to workflow, agent group, or agent."""
        try:
            query = """
                INSERT INTO phone_number_assignments 
                (phone_number_id, assignment_type, workflow_id, agent_group_id,
                 router_agent_id, default_agent_id, priority, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                ON CONFLICT (phone_number_id, assignment_type) DO UPDATE
                SET workflow_id = $3, agent_group_id = $4, router_agent_id = $5,
                    default_agent_id = $6, priority = $7, updated_at = CURRENT_TIMESTAMP
                RETURNING id, phone_number_id, assignment_type, priority, is_active, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(phone_number_id), assignment_type,
                 UUID(workflow_id) if workflow_id else None,
                 UUID(agent_group_id) if agent_group_id else None,
                 UUID(router_agent_id) if router_agent_id else None,
                 UUID(default_agent_id) if default_agent_id else None,
                 priority]
            )
            
            if rows:
                # Publish event
                await EventBus.publish_call_started(phone_number_id, "phone_number_assigned")
                
                return rows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error assigning number: {e}")
            return None
    
    @staticmethod
    async def unassign_number(
        phone_number_id: str,
        assignment_type: str
    ) -> bool:
        """Unassign phone number."""
        try:
            query = """
                DELETE FROM phone_number_assignments
                WHERE phone_number_id = $1 AND assignment_type = $2
            """
            
            await database.query(query, [UUID(phone_number_id), assignment_type])
            
            # Publish event
            await EventBus.publish_call_started(phone_number_id, "phone_number_unassigned")
            
            return True
            
        except Exception as e:
            logger.error(f"Error unassigning number: {e}")
            return False
    
    @staticmethod
    async def get_number(phone_number_id: str) -> Optional[Dict[str, Any]]:
        """Get phone number details."""
        try:
            query = """
                SELECT id, tenant_id, provider, provider_number_id, e164_number,
                       friendly_name, country_code, region, timezone, capabilities,
                       status, routing_mode, business_hours_id, recording_policy,
                       spam_protection_enabled, emergency_calling_enabled, metadata,
                       created_at, updated_at
                FROM phone_numbers
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting number: {e}")
            return None
    
    @staticmethod
    async def get_number_by_e164(tenant_id: str, e164_number: str) -> Optional[Dict[str, Any]]:
        """Get phone number by E164."""
        try:
            query = """
                SELECT id, tenant_id, provider, provider_number_id, e164_number,
                       friendly_name, country_code, region, timezone, capabilities,
                       status, routing_mode, business_hours_id, recording_policy,
                       spam_protection_enabled, emergency_calling_enabled, metadata,
                       created_at, updated_at
                FROM phone_numbers
                WHERE tenant_id = $1 AND e164_number = $2
            """
            
            rows = await database.query(query, [UUID(tenant_id), e164_number])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting number by E164: {e}")
            return None
    
    @staticmethod
    async def list_numbers(tenant_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List phone numbers for tenant."""
        try:
            if status:
                query = """
                    SELECT id, tenant_id, provider, e164_number, friendly_name,
                           country_code, region, timezone, status, routing_mode,
                           recording_policy, created_at, updated_at
                    FROM phone_numbers
                    WHERE tenant_id = $1 AND status = $2
                    ORDER BY created_at DESC
                """
                rows = await database.query(query, [UUID(tenant_id), status])
            else:
                query = """
                    SELECT id, tenant_id, provider, e164_number, friendly_name,
                           country_code, region, timezone, status, routing_mode,
                           recording_policy, created_at, updated_at
                    FROM phone_numbers
                    WHERE tenant_id = $1
                    ORDER BY created_at DESC
                """
                rows = await database.query(query, [UUID(tenant_id)])
            
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error listing numbers: {e}")
            return []
    
    @staticmethod
    async def update_recording_policy(
        phone_number_id: str,
        recording_policy: str
    ) -> bool:
        """Update recording policy for number."""
        try:
            query = """
                UPDATE phone_numbers
                SET recording_policy = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [recording_policy, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating recording policy: {e}")
            return False
    
    @staticmethod
    async def update_business_hours(
        phone_number_id: str,
        business_hours_id: str
    ) -> bool:
        """Update business hours for number."""
        try:
            query = """
                UPDATE phone_numbers
                SET business_hours_id = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [UUID(business_hours_id), UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating business hours: {e}")
            return False
    
    @staticmethod
    def _validate_e164(number: str) -> bool:
        """Validate E164 phone number format."""
        try:
            pattern = r'^\+?[1-9]\d{1,14}$'
            return bool(re.match(pattern, number))
        except Exception as e:
            logger.error(f"Error validating E164: {e}")
            return False
    
    @staticmethod
    async def _log_audit(
        phone_number_id: str,
        tenant_id: str,
        action: str,
        actor_type: str,
        actor_id: Optional[str],
        details: Optional[Dict] = None
    ) -> bool:
        """Log audit event."""
        try:
            query = """
                INSERT INTO phone_number_audit_logs 
                (phone_number_id, tenant_id, action, actor_type, actor_id, details, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'success')
            """
            
            await database.query(
                query,
                [UUID(phone_number_id) if phone_number_id else None,
                 UUID(tenant_id), action, actor_type, actor_id, details]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging audit: {e}")
            return False
