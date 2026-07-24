"""
Calendar Workflow Actions.
Integration with workflow engine for calendar operations.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from api.modules.calendar.calendar_service import CalendarService
from api.modules.phone_numbers.event_bus import EventBus, EventType

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_workflow_actions")


class CalendarWorkflowActions:
    """Calendar actions for workflow engine."""
    
    @staticmethod
    async def lookup_availability(
        execution_id: str,
        agent_calendar_connection_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Lookup calendar availability."""
        try:
            slots = await CalendarService.get_available_slots(
                agent_calendar_connection_id,
                start_date,
                end_date
            )
            
            await EventBus.publish_call_started(execution_id, "availability_checked")
            
            return {
                "status": "completed",
                "context_updates": {
                    "available_slots": slots,
                    "slots_count": len(slots)
                },
                "event": {
                    "type": "availability_checked",
                    "slots_count": len(slots)
                }
            }
            
        except Exception as e:
            logger.error(f"Error looking up availability: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def book_meeting(
        execution_id: str,
        session_id: str,
        agent_calendar_connection_id: str,
        customer_name: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        customer_phone: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Book a meeting."""
        try:
            # Create booking
            booking = await CalendarService.create_booking(
                session_id=session_id,
                agent_calendar_connection_id=agent_calendar_connection_id,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                start_time=start_time,
                end_time=end_time,
                timezone=timezone
            )
            
            if not booking:
                return {
                    "status": "failed",
                    "error": "Failed to create booking"
                }
            
            # Create calendar event
            event_title = title or f"Meeting with {customer_name}"
            event = await CalendarService.create_calendar_event(
                agent_calendar_connection_id=agent_calendar_connection_id,
                booking_id=str(booking["id"]),
                title=event_title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                attendees=[customer_email]
            )
            
            if not event:
                return {
                    "status": "failed",
                    "error": "Failed to create calendar event"
                }
            
            # Publish event
            await EventBus.publish_call_started(execution_id, "meeting_booked")
            
            return {
                "status": "completed",
                "context_updates": {
                    "booking_id": str(booking["id"]),
                    "event_id": str(event.get("id")),
                    "booking_confirmed": True
                },
                "event": {
                    "type": "meeting_booked",
                    "booking_id": str(booking["id"]),
                    "event_id": str(event.get("id"))
                }
            }
            
        except Exception as e:
            logger.error(f"Error booking meeting: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def update_meeting(
        execution_id: str,
        booking_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Update a meeting."""
        try:
            # Get booking
            booking = await CalendarService.get_booking(booking_id)
            if not booking:
                return {
                    "status": "failed",
                    "error": "Booking not found"
                }
            
            # Update booking status if provided
            if "status" in kwargs:
                await CalendarService.update_booking_status(booking_id, kwargs["status"])
            
            # Publish event
            await EventBus.publish_call_started(execution_id, "meeting_updated")
            
            return {
                "status": "completed",
                "context_updates": {
                    "booking_updated": True
                },
                "event": {
                    "type": "meeting_updated",
                    "booking_id": booking_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating meeting: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def cancel_meeting(
        execution_id: str,
        booking_id: str
    ) -> Dict[str, Any]:
        """Cancel a meeting."""
        try:
            # Update booking status
            success = await CalendarService.update_booking_status(booking_id, "cancelled")
            
            if not success:
                return {
                    "status": "failed",
                    "error": "Failed to cancel booking"
                }
            
            # Publish event
            await EventBus.publish_call_started(execution_id, "meeting_cancelled")
            
            return {
                "status": "completed",
                "context_updates": {
                    "booking_cancelled": True
                },
                "event": {
                    "type": "meeting_cancelled",
                    "booking_id": booking_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error cancelling meeting: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    async def reschedule_meeting(
        execution_id: str,
        booking_id: str,
        new_start_time: datetime,
        new_end_time: datetime
    ) -> Dict[str, Any]:
        """Reschedule a meeting."""
        try:
            # Get booking
            booking = await CalendarService.get_booking(booking_id)
            if not booking:
                return {
                    "status": "failed",
                    "error": "Booking not found"
                }
            
            # Update booking status
            await CalendarService.update_booking_status(booking_id, "rescheduled")
            
            # Publish event
            await EventBus.publish_call_started(execution_id, "meeting_rescheduled")
            
            return {
                "status": "completed",
                "context_updates": {
                    "booking_rescheduled": True,
                    "new_start_time": new_start_time.isoformat(),
                    "new_end_time": new_end_time.isoformat()
                },
                "event": {
                    "type": "meeting_rescheduled",
                    "booking_id": booking_id,
                    "new_start_time": new_start_time.isoformat(),
                    "new_end_time": new_end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error rescheduling meeting: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
