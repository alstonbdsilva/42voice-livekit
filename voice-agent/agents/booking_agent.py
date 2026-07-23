"""
Booking Agent.
Handles booking-related queries and operations.
Integrates with Calendly for real bookings.
"""

import logging
import sys
import os
from typing import Dict, Any, Optional
from livekit.agents import llm
from session_manager import SessionManager

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import database
from api.utils.calendly import CalendlyClient
from api.modules.integrations.routes import CalendlyAuthService
from config import get_settings

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
    
    @ai_callable(description="Confirm a booking with the user and save it to the system using Calendly integration.")
    async def handle_booking_confirmation(
        self,
        session_id: str,
        date: str,
        time: str,
        service: str,
        user_email: str,
        user_name: str,
        timezone: str = "UTC"
    ) -> str:
        """
        Handle booking confirmation via Calendly API.
        """
        try:
            # Get user context from session
            context = self.session_manager.get_context(session_id)
            user_id = context.get("user_id")
            client_id = context.get("client_id")
            
            if not user_id:
                return "I apologize, but I cannot process your booking without user authentication."
            
            # Initialize database pool if needed
            if database.pool is None:
                settings = get_settings()
                await database.init_pool()
            
            # Get active Calendly token
            access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
            if not access_token:
                return "I apologize, but Calendly is not connected to your account. Please connect Calendly first."
            
            # Get event type URI
            if client_id:
                integration_rows = await database.query(
                    "SELECT event_type_url FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
                    [client_id]
                )
            else:
                integration_rows = await database.query(
                    "SELECT event_type_url FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
                    [user_id]
                )
            
            if not integration_rows or not integration_rows[0].get("event_type_url"):
                return "I apologize, but no event type is configured for your Calendly account."
            
            event_type_url = integration_rows[0]["event_type_url"]
            
            # Resolve event type URI
            client = CalendlyClient(access_token)
            event_type_uri = await client.resolve_event_type_uri(event_type_url)
            
            if not event_type_uri:
                return "I apologize, but I could not find a valid event type for booking."
            
            # Create booking via Calendly API
            start_time = f"{date}T{time}:00"
            invitee_response = await client.create_invitee(
                event_type_uri,
                start_time,
                user_email,
                user_name,
                timezone
            )
            
            if not invitee_response:
                return "I apologize, but there was an error creating your booking. The time slot may not be available."
            
            invitee_data = invitee_response.get("resource", {})
            invitee_uri = invitee_data.get("uri")
            
            # Store booking in database
            if client_id:
                integration_rows = await database.query(
                    "SELECT id FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
                    [client_id]
                )
            else:
                integration_rows = await database.query(
                    "SELECT id FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
                    [user_id]
                )
            
            if integration_rows:
                integration_id = integration_rows[0]["id"]
                await database.query(
                    """INSERT INTO calendar_bookings 
                       (integration_id, invitee_uri, event_type_uri, invitee_email, invitee_name, start_time, timezone, status)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')""",
                    [
                        integration_id,
                        invitee_uri,
                        event_type_uri,
                        user_email,
                        user_name,
                        start_time,
                        timezone
                    ]
                )
            
            # Update session context
            self.session_manager.update_context(session_id, {
                "booking_details": {
                    "date": date,
                    "time": time,
                    "service": service,
                    "invitee_uri": invitee_uri,
                    "reference": invitee_uri.split("/")[-1]
                },
                "booking_status": "confirmed"
            })
            
            confirmation_msg = f"""Your booking has been confirmed!
Details:
- Date: {date}
- Time: {time}
- Service: {service}
- Confirmation: {invitee_uri.split('/')[-1]}

A confirmation email has been sent to {user_email}. Is there anything else I can help you with?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=confirmation_msg,
                agent=self.agent_name
            )
            
            return confirmation_msg
            
        except Exception as e:
            logger.error(f"Error handling booking confirmation: {e}")
            return "I apologize, but there was an error confirming your booking. Please try again later."
    
    @ai_callable(description="Cancel an existing booking using its reference number.")
    async def handle_booking_cancellation(
        self,
        session_id: str,
        booking_reference: str,
        reason: str = ""
    ) -> str:
        """
        Handle booking cancellation via Calendly API.
        """
        try:
            # Get user context from session
            context = self.session_manager.get_context(session_id)
            user_id = context.get("user_id")
            client_id = context.get("client_id")
            
            if not user_id:
                return "I apologize, but I cannot process your cancellation without user authentication."
            
            # Initialize database pool if needed
            if database.pool is None:
                settings = get_settings()
                await database.init_pool()
            
            # Get active Calendly token
            access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
            if not access_token:
                return "I apologize, but Calendly is not connected to your account."
            
            # Find booking by reference
            booking_rows = await database.query(
                "SELECT invitee_uri FROM calendar_bookings WHERE invitee_uri LIKE $1",
                [f"%{booking_reference}%"]
            )
            
            if not booking_rows:
                return f"I could not find a booking with reference {booking_reference}."
            
            invitee_uri = booking_rows[0]["invitee_uri"]
            
            # Cancel via Calendly API
            client = CalendlyClient(access_token)
            success = await client.cancel_booking(invitee_uri, reason)
            
            if not success:
                return "I apologize, but there was an error cancelling your booking."
            
            # Update database
            await database.query(
                """UPDATE calendar_bookings SET status = 'cancelled', cancellation_reason = $1, updated_at = CURRENT_TIMESTAMP 
                   WHERE invitee_uri = $2""",
                [reason, invitee_uri]
            )
            
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
