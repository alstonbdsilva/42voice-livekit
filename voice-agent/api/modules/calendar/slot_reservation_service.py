"""
Slot Reservation Service.
Prevents double booking with slot locking.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.slot_reservation_service")


class SlotReservationService:
    """Service for managing slot reservations."""
    
    RESERVATION_DURATION_MINUTES = 15  # Slots expire after 15 minutes
    
    @staticmethod
    async def reserve_slot(
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime,
        customer_email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Reserve a slot to prevent double booking.
        
        Returns reservation ID if successful, None if slot already reserved.
        """
        try:
            # Check if slot is already reserved
            check_query = """
                SELECT id FROM slot_reservations
                WHERE agent_calendar_connection_id = $1
                AND status IN ('reserved', 'confirmed')
                AND start_time < $3
                AND end_time > $2
            """
            
            check_rows = await database.query(
                check_query,
                [UUID(agent_calendar_connection_id), start_time, end_time]
            )
            
            if check_rows:
                logger.warning(f"Slot already reserved: {agent_calendar_connection_id}")
                return None
            
            # Create reservation
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=SlotReservationService.RESERVATION_DURATION_MINUTES)
            
            query = """
                INSERT INTO slot_reservations 
                (agent_calendar_connection_id, start_time, end_time, customer_email, expires_at, status)
                VALUES ($1, $2, $3, $4, $5, 'reserved')
                RETURNING id, agent_calendar_connection_id, start_time, end_time, status, expires_at, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(agent_calendar_connection_id), start_time, end_time, customer_email, expires_at]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error reserving slot: {e}")
            return None
    
    @staticmethod
    async def confirm_reservation(reservation_id: str) -> bool:
        """Confirm a slot reservation."""
        try:
            query = """
                UPDATE slot_reservations
                SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(query, [UUID(reservation_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error confirming reservation: {e}")
            return False
    
    @staticmethod
    async def release_reservation(reservation_id: str) -> bool:
        """Release a slot reservation."""
        try:
            query = """
                UPDATE slot_reservations
                SET status = 'released', updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(query, [UUID(reservation_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error releasing reservation: {e}")
            return False
    
    @staticmethod
    async def expire_old_reservations() -> int:
        """Expire old slot reservations."""
        try:
            query = """
                UPDATE slot_reservations
                SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'reserved' AND expires_at < CURRENT_TIMESTAMP
            """
            
            result = await database.query(query)
            return result.rowcount if hasattr(result, 'rowcount') else 0
            
        except Exception as e:
            logger.error(f"Error expiring reservations: {e}")
            return 0
    
    @staticmethod
    async def verify_slot_available(
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """Verify slot is still available."""
        try:
            query = """
                SELECT id FROM slot_reservations
                WHERE agent_calendar_connection_id = $1
                AND status IN ('reserved', 'confirmed')
                AND start_time < $3
                AND end_time > $2
            """
            
            rows = await database.query(
                query,
                [UUID(agent_calendar_connection_id), start_time, end_time]
            )
            
            return len(rows) == 0
            
        except Exception as e:
            logger.error(f"Error verifying slot: {e}")
            return False
