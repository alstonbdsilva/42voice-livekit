"""
Support Agent.
Handles customer support queries and troubleshooting.
"""

import logging
from typing import Dict, Any, Optional
from services.openai_llm import OpenAILLM
from session_manager import SessionManager

logger = logging.getLogger(__name__)


class SupportAgent:
    """Agent for handling customer support conversations."""
    
    def __init__(self, llm: OpenAILLM, session_manager: SessionManager):
        self.llm = llm
        self.session_manager = session_manager
        self.agent_name = "support_agent"
        
        # System prompt for support agent
        self.system_prompt = """You are a Customer Support Agent. Your role is to help users with:
- Technical issues and troubleshooting
- Account management
- Billing inquiries
- General questions and concerns
- Feedback and complaints

Be empathetic, patient, and solution-oriented. Acknowledge the user's frustration and work toward resolving their issue.
If you cannot resolve an issue, escalate it appropriately with clear documentation.
Always follow up to ensure the issue is resolved."""
    
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
            
            # Extract and update support context if detected
            await self._extract_support_context(session_id, user_message, response)
            
            logger.info(f"Support agent processed message for session: {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error in support agent: {e}")
            return "I apologize, but I encountered an error processing your request. Please try again."
    
    async def _extract_support_context(
        self,
        session_id: str,
        user_message: str,
        agent_response: str
    ):
        """
        Extract support-related information and update context.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            agent_response: Agent's response
        """
        try:
            # Use LLM to extract structured support information
            extraction_prompt = f"""Extract support information from this conversation:
User: {user_message}
Agent: {agent_response}

Extract these fields if present:
- issue_category (technical/billing/account/general)
- urgency_level (low/medium/high/critical)
- issue_description
- resolution_status (open/in_progress/resolved)
- follow_up_required

Return as JSON or empty dict if no support info found."""
            
            extracted = await self.llm.generate(
                prompt=extraction_prompt,
                temperature=0.1
            )
            
            # Update context with extracted info (simplified)
            if extracted and extracted != "{}":
                self.session_manager.update_context(session_id, {"support_info": extracted})
                
        except Exception as e:
            logger.error(f"Error extracting support context: {e}")
    
    async def troubleshoot_issue(
        self,
        session_id: str,
        issue_description: str
    ) -> str:
        """
        Provide troubleshooting steps for an issue.
        
        Args:
            session_id: Session identifier
            issue_description: Description of the issue
            
        Returns:
            Troubleshooting steps
        """
        try:
            troubleshooting_prompt = f"""Provide troubleshooting steps for this issue: {issue_description}
Include:
1. Step-by-step solutions
2. Common causes
3. When to escalate
4. Prevention tips"""
            
            troubleshooting = await self.llm.generate(
                prompt=troubleshooting_prompt,
                system_prompt=self.system_prompt
            )
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=troubleshooting,
                agent=self.agent_name
            )
            
            return troubleshooting
            
        except Exception as e:
            logger.error(f"Error providing troubleshooting: {e}")
            return "I apologize, but I couldn't generate troubleshooting steps at this time."
    
    async def handle_billing_inquiry(
        self,
        session_id: str,
        inquiry: str
    ) -> str:
        """
        Handle billing-related inquiries.
        
        Args:
            session_id: Session identifier
            inquiry: Billing inquiry description
            
        Returns:
            Billing information
        """
        try:
            billing_prompt = f"""Address this billing inquiry: {inquiry}
Provide:
- Clear explanation
- Resolution options
- Timeline if applicable
- Next steps"""
            
            billing_response = await self.llm.generate(
                prompt=billing_prompt,
                system_prompt=self.system_prompt
            )
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=billing_response,
                agent=self.agent_name
            )
            
            return billing_response
            
        except Exception as e:
            logger.error(f"Error handling billing inquiry: {e}")
            return "I apologize, but I couldn't process your billing inquiry at this time."
    
    async def escalate_issue(
        self,
        session_id: str,
        issue_details: Dict[str, Any]
    ) -> str:
        """
        Escalate an issue to a human support representative.
        
        Args:
            session_id: Session identifier
            issue_details: Dictionary with issue details
            
        Returns:
            Escalation message
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "escalation_requested": True,
                "escalation_details": issue_details,
                "escalation_agent": self.agent_name
            })
            
            escalation_msg = f"""I understand this issue requires additional assistance. I'm escalating this to our support team.

Issue Summary:
- Category: {issue_details.get('category', 'N/A')}
- Description: {issue_details.get('description', 'N/A')}
- Urgency: {issue_details.get('urgency', 'medium')}

A support representative will review your case and follow up within 24 hours.
Is there anything else you'd like me to add to this ticket?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=escalation_msg,
                agent=self.agent_name
            )
            
            return escalation_msg
            
        except Exception as e:
            logger.error(f"Error handling issue escalation: {e}")
            return "I apologize, but there was an error escalating your issue."
    
    async def confirm_resolution(
        self,
        session_id: str,
        resolution_summary: str
    ) -> str:
        """
        Confirm issue resolution with the user.
        
        Args:
            session_id: Session identifier
            resolution_summary: Summary of the resolution
            
        Returns:
            Confirmation message
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "resolution_status": "resolved",
                "resolution_summary": resolution_summary
            })
            
            confirmation_msg = f"""Great! I'm glad we could resolve your issue.

Resolution Summary: {resolution_summary}

Is there anything else I can help you with today?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=confirmation_msg,
                agent=self.agent_name
            )
            
            return confirmation_msg
            
        except Exception as e:
            logger.error(f"Error confirming resolution: {e}")
            return "I apologize, but there was an error confirming the resolution."
