"""
Outbound Calling Service.
Handles outbound call initiation and management.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.phone_numbers.phone_numbers_service import PhoneNumbersService
from api.modules.phone_numbers.phone_provider import PhoneProvider
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.outbound_calling_service")


class OutboundCallingService:
    """Service for outbound calling."""
    
    @staticmethod
    async def initiate_call(
        tenant_id: str,
        from_number_id: str,
        to_number: str,
        call_type: str = "manual",
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Initiate outbound call.
        
        Call types: manual, workflow, campaign, scheduled, api, retry
        """
        try:
            # Get phone number
            from_number = await PhoneNumbersService.get_number(from_number_id)
            if not from_number or str(from_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {from_number_id}")
                return None
            
            # Validate to_number
            if not PhoneNumbersService._validate_e164(to_number):
                logger.error(f"Invalid E164 format: {to_number}")
                return None
            
            # Get provider
            provider_name = from_number.get("provider")
            provider = PhoneNumbersService._providers.get(provider_name)
            
            if not provider:
                logger.error(f"Provider not found: {provider_name}")
                return None
            
            # Initiate call
            call_result = await provider.initiate_call(
                from_number.get("e164_number"),
                to_number,
                callback_url
            )
            
            if not call_result:
                logger.error(f"Failed to initiate call with {provider_name}")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    from_number_id,
                    tenant_id,
                    "call_failed",
                    "system",
                    None,
                    {"to_number": to_number, "call_type": call_type}
                )
                
                return None
            
            # Store call record
            call_id = call_result.get("call_id")
            
            query = """
                INSERT INTO phone_calls 
                (phone_number_id, call_id, from_number, to_number, call_type, direction, status, metadata)
                VALUES ($1, $2, $3, $4, $5, 'outbound', 'initiated', $6)
                RETURNING id, call_id, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(from_number_id), call_id, from_number.get("e164_number"),
                 to_number, call_type, metadata]
            )
            
            if rows:
                # Publish event
                await EventBus.publish_call_started(from_number_id, "outgoing_call_started")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    from_number_id,
                    tenant_id,
                    "call_initiated",
                    "system",
                    None,
                    {"to_number": to_number, "call_type": call_type, "call_id": call_id}
                )
                
                return rows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error initiating call: {e}")
            return None
    
    @staticmethod
    async def hangup_call(
        tenant_id: str,
        phone_number_id: str,
        call_id: str
    ) -> bool:
        """Hangup active call."""
        try:
            # Get phone number
            phone_number = await PhoneNumbersService.get_number(phone_number_id)
            if not phone_number or str(phone_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {phone_number_id}")
                return False
            
            # Get provider
            provider_name = phone_number.get("provider")
            provider = PhoneNumbersService._providers.get(provider_name)
            
            if not provider:
                logger.error(f"Provider not found: {provider_name}")
                return False
            
            # Hangup call
            success = await provider.hangup_call(call_id)
            
            if success:
                # Update call status
                query = """
                    UPDATE phone_calls
                    SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE call_id = $1
                """
                
                await database.query(query, [call_id])
                
                # Publish event
                await EventBus.publish_call_started(phone_number_id, "outgoing_call_completed")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    phone_number_id,
                    tenant_id,
                    "call_completed",
                    "system",
                    None,
                    {"call_id": call_id}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            return False
    
    @staticmethod
    async def get_call_status(
        tenant_id: str,
        phone_number_id: str,
        call_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get call status."""
        try:
            # Get phone number
            phone_number = await PhoneNumbersService.get_number(phone_number_id)
            if not phone_number or str(phone_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {phone_number_id}")
                return None
            
            # Get provider
            provider_name = phone_number.get("provider")
            provider = PhoneNumbersService._providers.get(provider_name)
            
            if not provider:
                logger.error(f"Provider not found: {provider_name}")
                return None
            
            # Get call status
            status = await provider.get_call_status(call_id)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting call status: {e}")
            return None
    
    @staticmethod
    async def start_recording(
        tenant_id: str,
        phone_number_id: str,
        call_id: str
    ) -> bool:
        """Start recording call."""
        try:
            # Get phone number
            phone_number = await PhoneNumbersService.get_number(phone_number_id)
            if not phone_number or str(phone_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {phone_number_id}")
                return False
            
            # Get provider
            provider_name = phone_number.get("provider")
            provider = PhoneNumbersService._providers.get(provider_name)
            
            if not provider:
                logger.error(f"Provider not found: {provider_name}")
                return False
            
            # Start recording
            success = await provider.start_recording(call_id)
            
            if success:
                # Publish event
                await EventBus.publish_call_started(phone_number_id, "recording_started")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    phone_number_id,
                    tenant_id,
                    "recording_started",
                    "system",
                    None,
                    {"call_id": call_id}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return False
    
    @staticmethod
    async def stop_recording(
        tenant_id: str,
        phone_number_id: str,
        call_id: str
    ) -> bool:
        """Stop recording call."""
        try:
            # Get phone number
            phone_number = await PhoneNumbersService.get_number(phone_number_id)
            if not phone_number or str(phone_number.get("tenant_id")) != tenant_id:
                logger.error(f"Phone number not found or unauthorized: {phone_number_id}")
                return False
            
            # Get provider
            provider_name = phone_number.get("provider")
            provider = PhoneNumbersService._providers.get(provider_name)
            
            if not provider:
                logger.error(f"Provider not found: {provider_name}")
                return False
            
            # Stop recording
            success = await provider.stop_recording(call_id)
            
            if success:
                # Publish event
                await EventBus.publish_call_started(phone_number_id, "recording_stopped")
                
                # Log audit
                await PhoneNumbersService._log_audit(
                    phone_number_id,
                    tenant_id,
                    "recording_stopped",
                    "system",
                    None,
                    {"call_id": call_id}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return False
