"""
Idempotency Service.
Prevents duplicate bookings and operations.
"""

import logging
import hashlib
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.idempotency_service")


class IdempotencyService:
    """Service for idempotent operations."""
    
    IDEMPOTENCY_KEY_TIMEOUT_HOURS = 24
    
    @staticmethod
    def generate_idempotency_key(
        agent_id: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Generate idempotency key for booking."""
        try:
            key_data = f"{agent_id}:{customer_email}:{start_time.isoformat()}:{end_time.isoformat()}"
            return hashlib.sha256(key_data.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating idempotency key: {e}")
            return ""
    
    @staticmethod
    async def check_idempotency(
        idempotency_key: str,
        operation_type: str
    ) -> Optional[Dict[str, Any]]:
        """Check if operation has been processed before."""
        try:
            query = """
                SELECT id, operation_type, result, created_at
                FROM idempotency_keys
                WHERE idempotency_key = $1
                AND operation_type = $2
                AND created_at > CURRENT_TIMESTAMP - INTERVAL '%d hours'
            """ % IdempotencyService.IDEMPOTENCY_KEY_TIMEOUT_HOURS
            
            rows = await database.query(query, [idempotency_key, operation_type])
            
            if rows:
                return rows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking idempotency: {e}")
            return None
    
    @staticmethod
    async def record_operation(
        idempotency_key: str,
        operation_type: str,
        result: Dict[str, Any]
    ) -> bool:
        """Record operation result for idempotency."""
        try:
            query = """
                INSERT INTO idempotency_keys 
                (idempotency_key, operation_type, result)
                VALUES ($1, $2, $3)
                ON CONFLICT (idempotency_key, operation_type) DO UPDATE
                SET result = $3, updated_at = CURRENT_TIMESTAMP
            """
            
            await database.query(query, [idempotency_key, operation_type, result])
            return True
            
        except Exception as e:
            logger.error(f"Error recording operation: {e}")
            return False
    
    @staticmethod
    async def check_duplicate_booking(
        agent_id: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """Check if booking already exists."""
        try:
            query = """
                SELECT id FROM calendar_bookings
                WHERE agent_calendar_connection_id IN (
                    SELECT id FROM agent_calendar_connections
                    WHERE agent_id = $1
                )
                AND customer_email = $2
                AND start_time = $3
                AND end_time = $4
                AND status IN ('confirmed', 'pending')
            """
            
            rows = await database.query(
                query,
                [UUID(agent_id), customer_email, start_time, end_time]
            )
            
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate booking: {e}")
            return False
    
    @staticmethod
    async def check_duplicate_webhook(
        calendar_connection_id: str,
        webhook_id: str
    ) -> bool:
        """Check if webhook has been processed."""
        try:
            query = """
                SELECT id FROM calendar_webhooks
                WHERE calendar_connection_id = $1
                AND webhook_id = $2
            """
            
            rows = await database.query(
                query,
                [UUID(calendar_connection_id), webhook_id]
            )
            
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error checking duplicate webhook: {e}")
            return False
    
    @staticmethod
    async def cleanup_old_idempotency_keys() -> int:
        """Clean up old idempotency keys."""
        try:
            query = """
                DELETE FROM idempotency_keys
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%d hours'
            """ % IdempotencyService.IDEMPOTENCY_KEY_TIMEOUT_HOURS
            
            result = await database.query(query)
            return result.rowcount if hasattr(result, 'rowcount') else 0
            
        except Exception as e:
            logger.error(f"Error cleaning up idempotency keys: {e}")
            return 0
