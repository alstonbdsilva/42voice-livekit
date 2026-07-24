"""
Enhanced Calendar Service.
Integrates all calendar features with slot locking, conflict detection, and health monitoring.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.calendar.calendar_service import CalendarService
from api.modules.calendar.availability_engine import AvailabilityEngine
from api.modules.calendar.slot_reservation_service import SlotReservationService
from api.modules.calendar.calendar_selection_service import CalendarSelectionService
from api.modules.calendar.conflict_detection_service import ConflictDetectionService
from api.modules.calendar.calendar_health_service import CalendarHealthService
from api.modules.calendar.calendar_audit_service import CalendarAuditService
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_service_enhanced")


class EnhancedCalendarService:
    """Enhanced calendar service with all production features."""
    
    @staticmethod
    async def book_meeting_safe(
        session_id: str,
        agent_id: str,
        customer_name: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        customer_phone: Optional[str] = None,
        manual_calendar_id: Optional[str] = None,
        workflow_context: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Book a meeting safely with slot locking and conflict detection.
        
        Flow:
        1. Select calendar based on strategy
        2. Reserve slot (lock)
        3. Verify free/busy again
        4. Detect conflicts
        5. Create booking
        6. Create calendar event
        7. Confirm reservation
        8. Publish events
        """
        try:
            # Step 1: Select calendar
            calendar = await CalendarSelectionService.select_calendar(
                agent_id,
                manual_selection=manual_calendar_id,
                workflow_context=workflow_context
            )
            
            if not calendar:
                logger.error(f"No calendar available for agent {agent_id}")
                return None
            
            agent_calendar_connection_id = str(calendar.get("id"))
            
            # Step 2: Reserve slot
            reservation = await SlotReservationService.reserve_slot(
                agent_calendar_connection_id,
                start_time,
                end_time,
                customer_email
            )
            
            if not reservation:
                logger.warning(f"Slot already reserved: {start_time} - {end_time}")
                return None
            
            reservation_id = str(reservation.get("id"))
            
            # Publish slot reserved event
            await EventBus.publish_slot_reserved(session_id, reservation_id)
            await CalendarAuditService.log_slot_reserved(agent_calendar_connection_id, customer_email)
            
            # Step 3: Verify free/busy again
            provider = CalendarService._providers.get(calendar.get("provider"))
            if not provider:
                await SlotReservationService.release_reservation(reservation_id)
                return None
            
            # Get OAuth connection
            oauth_query = """
                SELECT access_token FROM oauth_connections
                WHERE id = (
                    SELECT oauth_connection_id FROM calendar_connections
                    WHERE id = $1
                )
            """
            
            oauth_rows = await database.query(oauth_query, [UUID(calendar.get("calendar_connection_id"))])
            if not oauth_rows:
                await SlotReservationService.release_reservation(reservation_id)
                return None
            
            access_token = oauth_rows[0].get("access_token")
            
            # Verify slot still available
            is_available = await provider.get_free_busy(
                access_token,
                calendar.get("calendar_id"),
                start_time,
                end_time
            )
            
            if is_available.get("busy_periods"):
                await SlotReservationService.release_reservation(reservation_id)
                logger.warning(f"Slot became busy: {start_time} - {end_time}")
                return None
            
            # Step 4: Create booking
            booking = await CalendarService.create_booking(
                session_id,
                agent_calendar_connection_id,
                customer_name,
                customer_email,
                start_time,
                end_time,
                timezone,
                customer_phone
            )
            
            if not booking:
                await SlotReservationService.release_reservation(reservation_id)
                await CalendarAuditService.log_booking_failed(
                    agent_calendar_connection_id,
                    customer_email,
                    "Failed to create booking"
                )
                return None
            
            booking_id = str(booking.get("id"))
            
            # Step 5: Detect conflicts
            conflicts = await ConflictDetectionService.detect_conflicts(
                booking_id,
                agent_calendar_connection_id,
                start_time,
                end_time
            )
            
            if conflicts:
                # Publish conflict event
                for conflict in conflicts:
                    await EventBus.publish_booking_conflict_detected(
                        session_id,
                        conflict.get("conflict_type")
                    )
                    await CalendarAuditService.log_conflict_detected(
                        booking_id,
                        conflict.get("conflict_type"),
                        conflict.get("details", {})
                    )
                
                # Cancel booking on critical conflicts
                if any(c.get("conflict_type") in ["overlapping_meeting", "duplicate_request"] for c in conflicts):
                    await CalendarService.update_booking_status(booking_id, "cancelled")
                    await SlotReservationService.release_reservation(reservation_id)
                    return None
            
            # Step 6: Create calendar event
            event = await CalendarService.create_calendar_event(
                agent_calendar_connection_id,
                booking_id,
                f"Meeting with {customer_name}",
                start_time,
                end_time,
                attendees=[customer_email]
            )
            
            if not event:
                await CalendarService.update_booking_status(booking_id, "cancelled")
                await SlotReservationService.release_reservation(reservation_id)
                await CalendarAuditService.log_booking_failed(
                    agent_calendar_connection_id,
                    customer_email,
                    "Failed to create calendar event"
                )
                return None
            
            # Step 7: Confirm reservation
            await SlotReservationService.confirm_reservation(reservation_id)
            await CalendarService.update_booking_status(booking_id, "confirmed")
            
            # Step 8: Publish events
            await EventBus.publish_meeting_booked(session_id, booking_id)
            await CalendarAuditService.log_booking_created(
                booking_id,
                agent_calendar_connection_id,
                customer_email
            )
            
            return booking
            
        except Exception as e:
            logger.error(f"Error booking meeting safely: {e}")
            return None
    
    @staticmethod
    async def get_available_slots_safe(
        agent_id: str,
        start_date: datetime,
        end_date: datetime,
        manual_calendar_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available slots safely.
        
        Uses availability engine with all constraints.
        """
        try:
            # Select calendar
            calendar = await CalendarSelectionService.select_calendar(
                agent_id,
                manual_selection=manual_calendar_id
            )
            
            if not calendar:
                return []
            
            agent_calendar_connection_id = str(calendar.get("id"))
            
            # Get provider
            provider = CalendarService._providers.get(calendar.get("provider"))
            if not provider:
                return []
            
            # Get OAuth connection
            oauth_query = """
                SELECT access_token FROM oauth_connections
                WHERE id = (
                    SELECT oauth_connection_id FROM calendar_connections
                    WHERE id = $1
                )
            """
            
            oauth_rows = await database.query(oauth_query, [UUID(calendar.get("calendar_connection_id"))])
            if not oauth_rows:
                return []
            
            access_token = oauth_rows[0].get("access_token")
            
            # Generate slots using availability engine
            slots = await AvailabilityEngine.generate_slots(
                agent_calendar_connection_id,
                start_date,
                end_date,
                provider,
                access_token,
                calendar.get("calendar_id")
            )
            
            # Publish event
            await EventBus.publish_availability_generated(agent_id, len(slots))
            
            return slots
            
        except Exception as e:
            logger.error(f"Error getting available slots safely: {e}")
            return []
    
    @staticmethod
    async def get_calendar_health(calendar_connection_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive calendar health status."""
        try:
            health = await CalendarHealthService.get_health(calendar_connection_id)
            return health
        except Exception as e:
            logger.error(f"Error getting calendar health: {e}")
            return None
    
    @staticmethod
    async def get_audit_trail(
        calendar_connection_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for calendar operations."""
        try:
            logs = await CalendarAuditService.get_audit_logs(
                calendar_connection_id=calendar_connection_id,
                booking_id=booking_id,
                limit=limit
            )
            return logs
        except Exception as e:
            logger.error(f"Error getting audit trail: {e}")
            return []
