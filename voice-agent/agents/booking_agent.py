"""
Booking Agent.
Handles booking-related queries and operations.
"""

import logging
from typing import Dict, Any, Optional
from services.openai_llm import OpenAILLM
from session_manager import SessionManager

logger = logging.getLogger(__name__)


class BookingAgent:
    """Agent for handling booking-related conversations."""
    
    def __init__(self, llm: OpenAILLM, session_manager: SessionManager):
        self.llm = llm
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
    
    async def process_message(
        self,
        session_id: str,
        user_message: str
    ) -> str:
        """
        Process a user message and generate a response.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            
        Returns:
            Agent response
        """
        try:
            # Get conversation history
            history = self.session_manager.get_conversation_history(session_id)
            
            # Get session context
            context = self.session_manager.get_context(session_id)
            
            # Build messages for LLM
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for msg in history[-10:]:  # Last 10 messages
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Generate response
            response = await self.llm.generate_with_history(messages)
            
            # Add messages to session
            self.session_manager.add_message(
                session_id,
                role="user",
                content=user_message,
                agent=self.agent_name
            )
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=response,
                agent=self.agent_name
            )
            
            # Extract and update booking context if detected
            await self._extract_booking_context(session_id, user_message, response)
            
            logger.info(f"Booking agent processed message for session: {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error in booking agent: {e}")
            return "I apologize, but I encountered an error processing your booking request. Please try again."
    
    async def _extract_booking_context(
        self,
        session_id: str,
        user_message: str,
        agent_response: str
    ):
        """
        Extract booking-related information and update context.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            agent_response: Agent's response
        """
        try:
            # Use LLM to extract structured booking information
            extraction_prompt = f"""Extract booking information from this conversation:
User: {user_message}
Agent: {agent_response}

Extract these fields if present:
- booking_date
- booking_time
- service_type
- customer_name
- customer_phone
- booking_status

Return as JSON or empty dict if no booking info found."""
            
            extracted = await self.llm.generate(
                prompt=extraction_prompt,
                temperature=0.1
            )
            
            # Update context with extracted info (simplified)
            if extracted and extracted != "{}":
                self.session_manager.update_context(session_id, {"booking_info": extracted})
                
        except Exception as e:
            logger.error(f"Error extracting booking context: {e}")
    
    async def handle_booking_confirmation(
        self,
        session_id: str,
        booking_details: Dict[str, Any]
    ) -> str:
        """
        Handle booking confirmation.
        
        Args:
            session_id: Session identifier
            booking_details: Booking details dictionary
            
        Returns:
            Confirmation message
        """
        try:
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
- Reference: {booking_details.get('reference', 'BK' + session_id[:8])}

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
    
    async def handle_booking_cancellation(
        self,
        session_id: str,
        booking_reference: str
    ) -> str:
        """
        Handle booking cancellation.
        
        Args:
            session_id: Session identifier
            booking_reference: Booking reference number
            
        Returns:
            Cancellation message
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
