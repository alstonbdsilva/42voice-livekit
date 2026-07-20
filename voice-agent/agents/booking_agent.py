"""
Booking Agent.
Handles booking-related queries and operations.
"""

import logging
from typing import Dict, Any, Optional
from livekit.agents import llm
from session_manager import SessionManager

ai_callable = getattr(llm, "ai_callable", llm.function_tool)

logger = logging.getLogger(__name__)


class BookingAgent:
    """Agent for handling booking-related conversations."""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.agent_name = "booking_agent"
        
        # System prompt for booking agent
        self.system_prompt = """You are a Booking Agent for a service company. Your role is to help users with:
- Making new bookings
- Checking existing bookings
- Modifying or canceling bookings
- Providing booking information

Be helpful, polite, and efficient. Ask for necessary details like date, time, service type, and contact information when making bookings.
Always confirm booking details before finalizing."""
    
    @ai_callable(description="Confirm a booking with the user and save it to the system.")
    async def handle_booking_confirmation(
        self,
        session_id: str,
        date: str,
        time: str,
        service: str
    ) -> str:
        """
        Handle booking confirmation.
        """
        try:
            booking_details = {
                "date": date,
                "time": time,
                "service": service,
                "reference": "BK" + session_id[:8]
            }
            
            # Update context with booking details
            self.session_manager.update_context(session_id, {
                "booking_details": booking_details,
                "booking_status": "confirmed"
            })
            
            confirmation_msg = f"""Your booking has been confirmed!
Details:
- Date: {booking_details.get('date', 'N/A')}
- Time: {booking_details.get('time', 'N/A')}
- Service: {booking_details.get('service', 'N/A')}
- Reference: {booking_details.get('reference')}

You will receive a confirmation shortly. Is there anything else I can help you with?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=confirmation_msg,
                agent=self.agent_name
            )
            
            return confirmation_msg
            
        except Exception as e:
            logger.error(f"Error handling booking confirmation: {e}")
            return "I apologize, but there was an error confirming your booking."
    
    @ai_callable(description="Cancel an existing booking using its reference number.")
    async def handle_booking_cancellation(
        self,
        session_id: str,
        booking_reference: str
    ) -> str:
        """
        Handle booking cancellation.
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "booking_status": "cancelled",
                "cancelled_reference": booking_reference
            })
            
            cancellation_msg = f"""Your booking {booking_reference} has been cancelled.
Would you like to reschedule or book a new appointment?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=cancellation_msg,
                agent=self.agent_name
            )
            
            return cancellation_msg
            
        except Exception as e:
            logger.error(f"Error handling booking cancellation: {e}")
            return "I apologize, but there was an error cancelling your booking."
