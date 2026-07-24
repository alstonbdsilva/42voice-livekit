"""
Telephony Health Service.
Monitors carrier, provider, and infrastructure health.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.telephony_health_service")


class TelephonyHealthService:
    """Service for monitoring telephony health."""
    
    @staticmethod
    async def initialize_health(
        phone_number_id: Optional[str] = None,
        sip_trunk_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Initialize health record."""
        try:
            query = """
                INSERT INTO telephony_health 
                (phone_number_id, sip_trunk_id, carrier_health, provider_health,
                 sip_registration_status, webhook_health, recording_health)
                VALUES ($1, $2, 'unknown', 'unknown', 'unknown', 'unknown', 'unknown')
                ON CONFLICT (phone_number_id, sip_trunk_id) DO NOTHING
                RETURNING id, phone_number_id, sip_trunk_id, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(phone_number_id) if phone_number_id else None,
                 UUID(sip_trunk_id) if sip_trunk_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing health: {e}")
            return None
    
    @staticmethod
    async def update_carrier_health(
        phone_number_id: str,
        status: str
    ) -> bool:
        """Update carrier health status."""
        try:
            query = """
                UPDATE telephony_health
                SET carrier_health = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [status, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating carrier health: {e}")
            return False
    
    @staticmethod
    async def update_provider_health(
        phone_number_id: str,
        status: str,
        latency_ms: int = 0
    ) -> bool:
        """Update provider health status."""
        try:
            query = """
                UPDATE telephony_health
                SET provider_health = $1, provider_latency_ms = $2, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $3
            """
            
            await database.query(query, [status, latency_ms, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating provider health: {e}")
            return False
    
    @staticmethod
    async def update_sip_registration(
        sip_trunk_id: str,
        status: str
    ) -> bool:
        """Update SIP registration status."""
        try:
            query = """
                UPDATE telephony_health
                SET sip_registration_status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE sip_trunk_id = $2
            """
            
            await database.query(query, [status, UUID(sip_trunk_id)])
            
            # Also update SIP trunk
            trunk_query = """
                UPDATE sip_trunks
                SET health_status = $1, last_registration = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(trunk_query, [status, UUID(sip_trunk_id)])
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating SIP registration: {e}")
            return False
    
    @staticmethod
    async def update_webhook_health(
        phone_number_id: str,
        status: str
    ) -> bool:
        """Update webhook health status."""
        try:
            query = """
                UPDATE telephony_health
                SET webhook_health = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [status, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating webhook health: {e}")
            return False
    
    @staticmethod
    async def update_recording_health(
        phone_number_id: str,
        status: str
    ) -> bool:
        """Update recording health status."""
        try:
            query = """
                UPDATE telephony_health
                SET recording_health = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [status, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating recording health: {e}")
            return False
    
    @staticmethod
    async def update_call_success_rate(
        phone_number_id: str,
        success_rate: float
    ) -> bool:
        """Update call success rate."""
        try:
            query = """
                UPDATE telephony_health
                SET call_success_rate = $1, updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $2
            """
            
            await database.query(query, [success_rate, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating call success rate: {e}")
            return False
    
    @staticmethod
    async def update_network_metrics(
        phone_number_id: str,
        packet_loss: float,
        jitter_ms: int,
        mos_score: float
    ) -> bool:
        """Update network metrics."""
        try:
            query = """
                UPDATE telephony_health
                SET packet_loss_percent = $1, jitter_ms = $2, mos_score = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE phone_number_id = $4
            """
            
            await database.query(query, [packet_loss, jitter_ms, mos_score, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating network metrics: {e}")
            return False
    
    @staticmethod
    async def get_health(phone_number_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get health status."""
        try:
            if phone_number_id:
                query = """
                    SELECT phone_number_id, sip_trunk_id, carrier_health, provider_health,
                           sip_registration_status, webhook_health, recording_health,
                           call_success_rate, provider_latency_ms, packet_loss_percent,
                           jitter_ms, mos_score, last_check, created_at, updated_at
                    FROM telephony_health
                    WHERE phone_number_id = $1
                """
                
                rows = await database.query(query, [UUID(phone_number_id)])
                return rows[0] if rows else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting health: {e}")
            return None
    
    @staticmethod
    async def get_unhealthy_resources() -> list:
        """Get unhealthy resources."""
        try:
            query = """
                SELECT phone_number_id, sip_trunk_id, carrier_health, provider_health,
                       sip_registration_status, webhook_health, recording_health
                FROM telephony_health
                WHERE carrier_health IN ('degraded', 'unhealthy')
                OR provider_health IN ('degraded', 'unhealthy')
                OR sip_registration_status IN ('failed', 'expired')
                OR webhook_health IN ('degraded', 'unhealthy')
                OR recording_health IN ('degraded', 'unhealthy')
                ORDER BY updated_at DESC
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting unhealthy resources: {e}")
            return []
