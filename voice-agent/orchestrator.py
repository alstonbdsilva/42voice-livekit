"""
Orchestrator Agent.
Handles intent detection and dynamic routing to specialized agents.
"""

import logging
from typing import Dict, Any, Optional
from livekit.agents import llm
from session_manager import SessionManager
from agents.booking_agent import BookingAgent
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrator for intent detection and agent routing."""
    
    def __init__(
        self,
        session_manager: SessionManager,
        booking_agent: BookingAgent,
        sales_agent: SalesAgent,
        support_agent: SupportAgent
    ):
        self.session_manager = session_manager
        self.booking_agent = booking_agent
        self.sales_agent = sales_agent
        self.support_agent = support_agent
        self.agent_name = "orchestrator"
        
        self.intent_mapping = {
            "booking": "booking_agent",
            "sales": "sales_agent",
            "support": "support_agent",
            "general": "orchestrator"
        }
    
    @llm.function_tool(description="Request a handoff to a specialized agent like booking_agent, sales_agent, or support_agent.")
    async def request_agent_handoff(
        self,
        session_id: str,
        target_agent: str
    ) -> str:
        """Request a handoff to a specific agent."""
        try:
            if target_agent not in self.intent_mapping.values():
                return f"Invalid agent: {target_agent}"
            
            self.session_manager.set_current_agent(session_id, target_agent)
            
            handoff_messages = {
                "booking_agent": "I'll connect you with our Booking Agent who can help you with appointments and reservations.",
                "sales_agent": "I'll connect you with our Sales Agent who can assist you with product information and recommendations.",
                "support_agent": "I'll connect you with our Support Agent who can help you with technical issues and account management."
            }
            
            handoff_msg = handoff_messages.get(target_agent, f"Transferring to {target_agent}.")
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=handoff_msg,
                agent=self.agent_name
            )
            
            return f"SYSTEM EVENT: Handoff successful. You must now act as the {target_agent}. Respond to the user confirming the transfer: {handoff_msg}"
            
        except Exception as e:
            logger.error(f"Error requesting handoff: {e}")
            return "Error processing handoff."
    
    @llm.function_tool(description="Return control to the orchestrator agent.")
    async def return_to_orchestrator(self, session_id: str) -> str:
        """Return control to the orchestrator."""
        try:
            self.session_manager.set_current_agent(session_id, "orchestrator")
            return_msg = "I'm back to help you. How can I assist you today?"
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=return_msg,
                agent=self.agent_name
            )
            return f"SYSTEM EVENT: Returned to orchestrator. Acknowledge to the user: {return_msg}"
        except Exception as e:
            logger.error(f"Error returning to orchestrator: {e}")
            return "Error returning to orchestrator."

    # --- Booking Agent Wrappers ---
    @llm.function_tool(description="Confirm a booking with the user and save it to the system.")
    async def handle_booking_confirmation(self, session_id: str, date: str, time: str, service: str) -> str:
        return await self.booking_agent.handle_booking_confirmation(session_id, date, time, service)
        
    @llm.function_tool(description="Cancel an existing booking using its reference number.")
    async def handle_booking_cancellation(self, session_id: str, booking_reference: str) -> str:
        return await self.booking_agent.handle_booking_cancellation(session_id, booking_reference)

    # --- Sales Agent Wrappers ---
    @llm.function_tool(description="Provide product recommendations based on user needs.")
    async def provide_product_recommendation(self, session_id: str, user_needs: str) -> str:
        return await self.sales_agent.provide_product_recommendation(session_id, user_needs)
        
    @llm.function_tool(description="Retrieve pricing information for a specific product or service.")
    async def handle_pricing_inquiry(self, session_id: str, product_or_service: str) -> str:
        return await self.sales_agent.handle_pricing_inquiry(session_id, product_or_service)
        
    @llm.function_tool(description="Escalate the conversation to a human sales representative.")
    async def escalate_to_human(self, session_id: str, reason: str) -> str:
        return await self.sales_agent.escalate_to_human(session_id, reason)

    # --- Support Agent Wrappers ---
    @llm.function_tool(description="Provide troubleshooting steps for a technical issue.")
    async def troubleshoot_issue(self, session_id: str, issue_description: str) -> str:
        return await self.support_agent.troubleshoot_issue(session_id, issue_description)
        
    @llm.function_tool(description="Handle billing-related inquiries.")
    async def handle_billing_inquiry(self, session_id: str, inquiry: str) -> str:
        return await self.support_agent.handle_billing_inquiry(session_id, inquiry)
        
    @llm.function_tool(description="Escalate an issue to a human support representative.")
    async def escalate_issue(self, session_id: str, category: str, description: str, urgency: str) -> str:
        return await self.support_agent.escalate_issue(session_id, category, description, urgency)
        
    @llm.function_tool(description="Confirm that an issue has been successfully resolved.")
    async def confirm_resolution(self, session_id: str, resolution_summary: str) -> str:
        return await self.support_agent.confirm_resolution(session_id, resolution_summary)
