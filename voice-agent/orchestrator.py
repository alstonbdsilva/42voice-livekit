"""
Orchestrator Agent.
Handles intent detection and dynamic routing to specialized agents.
"""

import logging
from typing import Dict, Any, Optional
from services.openai_llm import OpenAILLM
from session_manager import SessionManager
from agents.booking_agent import BookingAgent
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrator for intent detection and agent routing."""
    
    def __init__(
        self,
        llm: OpenAILLM,
        session_manager: SessionManager,
        booking_agent: BookingAgent,
        sales_agent: SalesAgent,
        support_agent: SupportAgent
    ):
        self.llm = llm
        self.session_manager = session_manager
        self.booking_agent = booking_agent
        self.sales_agent = sales_agent
        self.support_agent = support_agent
        self.agent_name = "orchestrator"
        
        # Available intents and their corresponding agents
        self.intent_mapping = {
            "booking": "booking_agent",
            "sales": "sales_agent",
            "support": "support_agent",
            "general": "orchestrator"
        }
        
        # System prompt for orchestrator
        self.system_prompt = """You are an Orchestrator Agent. Your role is to:
1. Understand the user's intent
2. Route the conversation to the appropriate specialized agent
3. Handle general inquiries and greetings
4. Manage agent handoffs when needed

Available specialized agents:
- Booking Agent: For appointments, reservations, scheduling
- Sales Agent: For product information, pricing, recommendations
- Support Agent: For technical issues, billing, account management

Be friendly and efficient. Always explain when you're transferring to another agent."""
    
    async def process_message(
        self,
        session_id: str,
        user_message: str
    ) -> str:
        """
        Process a user message, detect intent, and route to appropriate agent.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            
        Returns:
            Agent response
        """
        try:
            # Get current agent
            current_agent = self.session_manager.get_current_agent(session_id)
            
            # If already with a specialized agent, continue with that agent
            if current_agent and current_agent != "orchestrator":
                return await self._route_to_agent(session_id, user_message, current_agent)
            
            # Detect intent
            intent = await self._detect_intent(user_message, session_id)
            
            # Route to appropriate agent
            agent_name = self.intent_mapping.get(intent, "orchestrator")
            
            # Update current agent in session
            self.session_manager.set_current_agent(session_id, agent_name)
            
            # If routing to specialized agent, delegate
            if agent_name != "orchestrator":
                handoff_message = self._generate_handoff_message(intent)
                self.session_manager.add_message(
                    session_id,
                    role="assistant",
                    content=handoff_message,
                    agent=self.agent_name
                )
                
                # Route to the specialized agent
                return await self._route_to_agent(session_id, user_message, agent_name)
            
            # Handle general inquiries here
            return await self._handle_general_inquiry(session_id, user_message)
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            return "I apologize, but I encountered an error. Please try again."
    
    async def _detect_intent(
        self,
        user_message: str,
        session_id: str
    ) -> str:
        """
        Detect the user's intent from their message.
        
        Args:
            user_message: User's message
            session_id: Session identifier
            
        Returns:
            Detected intent
        """
        try:
            # Get conversation history for context
            history = self.session_manager.get_conversation_history(session_id, limit=5)
            
            # Build intent detection prompt
            intent_prompt = f"""Classify the user's intent into one of these categories:
- booking: appointments, reservations, scheduling, booking
- sales: products, pricing, recommendations, purchasing
- support: technical issues, billing, account management, help
- general: greetings, general questions, unclear intent

User message: {user_message}

Conversation context:
{self._format_history(history)}

Respond with only the intent name (lowercase)."""
            
            intent = await self.llm.generate(
                prompt=intent_prompt,
                system_prompt="You are an intent classifier. Respond with only the intent name.",
                temperature=0.1
            )
            
            # Clean and validate intent
            intent = intent.strip().lower()
            if intent not in self.intent_mapping:
                logger.warning(f"Unknown intent detected: {intent}, defaulting to general")
                return "general"
            
            logger.info(f"Intent detected: {intent} for session: {session_id}")
            return intent
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return "general"
    
    async def _route_to_agent(
        self,
        session_id: str,
        user_message: str,
        agent_name: str
    ) -> str:
        """
        Route message to a specific agent.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            agent_name: Target agent name
            
        Returns:
            Agent response
        """
        try:
            if agent_name == "booking_agent":
                return await self.booking_agent.process_message(session_id, user_message)
            elif agent_name == "sales_agent":
                return await self.sales_agent.process_message(session_id, user_message)
            elif agent_name == "support_agent":
                return await self.support_agent.process_message(session_id, user_message)
            else:
                return await self._handle_general_inquiry(session_id, user_message)
                
        except Exception as e:
            logger.error(f"Error routing to agent {agent_name}: {e}")
            return "I apologize, but there was an error processing your request."
    
    async def _handle_general_inquiry(
        self,
        session_id: str,
        user_message: str
    ) -> str:
        """
        Handle general inquiries directly.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            
        Returns:
            Response
        """
        try:
            # Get conversation history
            history = self.session_manager.get_conversation_history(session_id)
            
            # Build messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            for msg in history[-10:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            messages.append({"role": "user", "content": user_message})
            
            # Generate response
            response = await self.llm.generate_with_history(messages)
            
            # Add to session
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
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling general inquiry: {e}")
            return "I apologize, but I couldn't process your request."
    
    def _generate_handoff_message(self, intent: str) -> str:
        """
        Generate a handoff message when transferring to a specialized agent.
        
        Args:
            intent: Detected intent
            
        Returns:
            Handoff message
        """
        handoff_messages = {
            "booking": "I'll connect you with our Booking Agent who can help you with appointments and reservations.",
            "sales": "I'll connect you with our Sales Agent who can assist you with product information and recommendations.",
            "support": "I'll connect you with our Support Agent who can help you with technical issues and account management."
        }
        
        return handoff_messages.get(intent, "Let me help you with that.")
    
    def _format_history(self, history: list) -> str:
        """
        Format conversation history for prompt.
        
        Args:
            history: Conversation history list
            
        Returns:
            Formatted history string
        """
        if not history:
            return "No previous conversation."
        
        formatted = []
        for msg in history:
            formatted.append(f"{msg['role']}: {msg['content']}")
        
        return "\n".join(formatted)
    
    async def request_agent_handoff(
        self,
        session_id: str,
        target_agent: str
    ) -> str:
        """
        Request a handoff to a specific agent.
        
        Args:
            session_id: Session identifier
            target_agent: Target agent name
            
        Returns:
            Handoff confirmation
        """
        try:
            if target_agent not in self.intent_mapping.values():
                return f"Invalid agent: {target_agent}"
            
            # Update current agent
            self.session_manager.set_current_agent(session_id, target_agent)
            
            # Generate handoff message
            intent = next(k for k, v in self.intent_mapping.items() if v == target_agent)
            handoff_msg = self._generate_handoff_message(intent)
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=handoff_msg,
                agent=self.agent_name
            )
            
            logger.info(f"Handoff requested to {target_agent} for session: {session_id}")
            return handoff_msg
            
        except Exception as e:
            logger.error(f"Error requesting handoff: {e}")
            return "I apologize, but there was an error with the handoff."
    
    async def return_to_orchestrator(self, session_id: str) -> str:
        """
        Return control to the orchestrator.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Return message
        """
        try:
            self.session_manager.set_current_agent(session_id, "orchestrator")
            
            return_msg = "I'm back to help you. How can I assist you today?"
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=return_msg,
                agent=self.agent_name
            )
            
            logger.info(f"Returned to orchestrator for session: {session_id}")
            return return_msg
            
        except Exception as e:
            logger.error(f"Error returning to orchestrator: {e}")
            return "I apologize, but there was an error."
