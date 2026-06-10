"""
Sales Agent.
Handles sales-related queries and product information.
"""

import logging
from typing import Dict, Any, Optional
from services.openai_llm import OpenAILLM
from session_manager import SessionManager

logger = logging.getLogger(__name__)


class SalesAgent:
    """Agent for handling sales-related conversations."""
    
    def __init__(self, llm: OpenAILLM, session_manager: SessionManager):
        self.llm = llm
        self.session_manager = session_manager
        self.agent_name = "sales_agent"
        
        # System prompt for sales agent
        self.system_prompt = """You are a Sales Agent for a company. Your role is to help users with:
- Product information and recommendations
- Pricing and packages
- Special offers and discounts
- Feature comparisons
- Purchase guidance

Be enthusiastic, helpful, and customer-focused. Highlight benefits and value propositions.
Always be honest about product capabilities and limitations.
Guide customers toward solutions that best fit their needs."""
    
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
            
            # Extract and update sales context if detected
            await self._extract_sales_context(session_id, user_message, response)
            
            logger.info(f"Sales agent processed message for session: {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error in sales agent: {e}")
            return "I apologize, but I encountered an error processing your request. Please try again."
    
    async def _extract_sales_context(
        self,
        session_id: str,
        user_message: str,
        agent_response: str
    ):
        """
        Extract sales-related information and update context.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            agent_response: Agent's response
        """
        try:
            # Use LLM to extract structured sales information
            extraction_prompt = f"""Extract sales information from this conversation:
User: {user_message}
Agent: {agent_response}

Extract these fields if present:
- product_interest
- budget_range
- purchase_timeline
- competitor_mentioned
- feature_preferences
- sales_stage (awareness/consideration/decision)

Return as JSON or empty dict if no sales info found."""
            
            extracted = await self.llm.generate(
                prompt=extraction_prompt,
                temperature=0.1
            )
            
            # Update context with extracted info (simplified)
            if extracted and extracted != "{}":
                self.session_manager.update_context(session_id, {"sales_info": extracted})
                
        except Exception as e:
            logger.error(f"Error extracting sales context: {e}")
    
    async def provide_product_recommendation(
        self,
        session_id: str,
        user_needs: str
    ) -> str:
        """
        Provide product recommendations based on user needs.
        
        Args:
            session_id: Session identifier
            user_needs: Description of user needs
            
        Returns:
            Recommendation message
        """
        try:
            recommendation_prompt = f"""Based on these user needs: {user_needs}
Provide a personalized product recommendation with:
1. Recommended product/service
2. Key benefits for this user
3. Pricing information
4. Why this is the best fit"""
            
            recommendation = await self.llm.generate(
                prompt=recommendation_prompt,
                system_prompt=self.system_prompt
            )
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=recommendation,
                agent=self.agent_name
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error providing recommendation: {e}")
            return "I apologize, but I couldn't generate a recommendation at this time."
    
    async def handle_pricing_inquiry(
        self,
        session_id: str,
        product_or_service: str
    ) -> str:
        """
        Handle pricing inquiries.
        
        Args:
            session_id: Session identifier
            product_or_service: Product or service name
            
        Returns:
            Pricing information
        """
        try:
            pricing_prompt = f"""Provide pricing information for: {product_or_service}
Include:
- Base pricing
- Available packages/tiers
- Any current promotions
- Payment options"""
            
            pricing_info = await self.llm.generate(
                prompt=pricing_prompt,
                system_prompt=self.system_prompt
            )
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=pricing_info,
                agent=self.agent_name
            )
            
            return pricing_info
            
        except Exception as e:
            logger.error(f"Error handling pricing inquiry: {e}")
            return "I apologize, but I couldn't retrieve pricing information at this time."
    
    async def escalate_to_human(
        self,
        session_id: str,
        reason: str
    ) -> str:
        """
        Escalate to a human sales representative.
        
        Args:
            session_id: Session identifier
            reason: Reason for escalation
            
        Returns:
            Escalation message
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "escalation_requested": True,
                "escalation_reason": reason,
                "escalation_agent": self.agent_name
            })
            
            escalation_msg = f"""I understand you'd like to speak with a human representative regarding: {reason}

I'm connecting you with our sales team now. They'll be able to provide more personalized assistance.
Is there anything specific you'd like me to note before the transfer?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=escalation_msg,
                agent=self.agent_name
            )
            
            return escalation_msg
            
        except Exception as e:
            logger.error(f"Error handling escalation: {e}")
            return "I apologize, but there was an error processing your request to speak with a representative."
