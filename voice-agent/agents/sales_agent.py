"""
Sales Agent.
Handles sales-related queries and product information.
"""

import logging
from typing import Dict, Any, Optional
from livekit.agents import llm
from session_manager import SessionManager

ai_callable = getattr(llm, "ai_callable", llm.function_tool)

logger = logging.getLogger(__name__)


class SalesAgent:
    """Agent for handling sales-related conversations."""
    
    def __init__(self, session_manager: SessionManager):
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
    
    @ai_callable(description="Provide product recommendations based on user needs.")
    async def provide_product_recommendation(
        self,
        session_id: str,
        user_needs: str
    ) -> str:
        """
        Provide product recommendations based on user needs.
        """
        try:
            # Analyze user needs and provide appropriate recommendation
            needs_lower = user_needs.lower()
            
            # Product catalog with recommendations
            product_catalog = {
                "basic": {
                    "name": "Basic Plan",
                    "price": "$29/month",
                    "features": ["Core features", "Email support", "5GB storage"],
                    "best_for": "Individual users with basic needs"
                },
                "professional": {
                    "name": "Professional Plan",
                    "price": "$79/month",
                    "features": ["All Basic features", "Priority support", "50GB storage", "Advanced analytics"],
                    "best_for": "Small teams and professionals"
                },
                "enterprise": {
                    "name": "Enterprise Plan",
                    "price": "Custom pricing",
                    "features": ["All Professional features", "24/7 phone support", "Unlimited storage", "Custom integrations", "SLA guarantee"],
                    "best_for": "Large organizations with complex needs"
                }
            }
            
            # Determine best fit based on needs
            recommended_product = "professional"  # default
            
            if any(keyword in needs_lower for keyword in ["individual", "personal", "basic", "simple", "starter"]):
                recommended_product = "basic"
            elif any(keyword in needs_lower for keyword in ["team", "business", "company", "organization", "enterprise", "large"]):
                recommended_product = "enterprise"
            
            product = product_catalog[recommended_product]
            
            # Update context with recommendation
            self.session_manager.update_context(session_id, {
                "recommended_product": recommended_product,
                "user_needs": user_needs
            })
            
            recommendation_msg = f"""Based on your needs, I recommend our {product['name']}.

**Pricing:** {product['price']}

**Key Features:**
{chr(10).join(f"- {feature}" for feature in product['features'])}

**Why this is the best fit:** {product['best_for']}

Would you like me to provide more details about this plan or discuss other options?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=recommendation_msg,
                agent=self.agent_name
            )
            
            return recommendation_msg
            
        except Exception as e:
            logger.error(f"Error providing recommendation: {e}")
            return "I apologize, but I encountered an error while processing your recommendation request."
    
    @ai_callable(description="Retrieve pricing information for a specific product or service.")
    async def handle_pricing_inquiry(
        self,
        session_id: str,
        product_or_service: str
    ) -> str:
        """
        Handle pricing inquiries.
        """
        try:
            product_lower = product_or_service.lower()
            
            # Pricing information
            pricing_data = {
                "basic": {
                    "name": "Basic Plan",
                    "monthly": "$29/month",
                    "annual": "$290/year (save 17%)",
                    "features": ["Core features", "Email support", "5GB storage"],
                    "add_ons": ["Additional storage: $5/GB/month", "Priority support: +$10/month"]
                },
                "professional": {
                    "name": "Professional Plan",
                    "monthly": "$79/month",
                    "annual": "$790/year (save 17%)",
                    "features": ["All Basic features", "Priority support", "50GB storage", "Advanced analytics"],
                    "add_ons": ["Additional storage: $3/GB/month", "Custom integrations: +$25/month"]
                },
                "enterprise": {
                    "name": "Enterprise Plan",
                    "monthly": "Custom pricing",
                    "annual": "Custom pricing",
                    "features": ["All Professional features", "24/7 phone support", "Unlimited storage", "Custom integrations", "SLA guarantee"],
                    "add_ons": ["Dedicated account manager", "On-premise deployment", "Custom training"]
                }
            }
            
            # Determine which product they're asking about
            product_key = None
            if "basic" in product_lower:
                product_key = "basic"
            elif "professional" in product_lower or "pro" in product_lower:
                product_key = "professional"
            elif "enterprise" in product_lower:
                product_key = "enterprise"
            else:
                # If not specific, provide overview
                overview_msg = """Here's our pricing overview:

**Basic Plan** - $29/month ($290/year)
- Core features, Email support, 5GB storage

**Professional Plan** - $79/month ($790/year)
- All Basic features, Priority support, 50GB storage, Advanced analytics

**Enterprise Plan** - Custom pricing
- All Professional features, 24/7 phone support, Unlimited storage, Custom integrations, SLA guarantee

All annual plans save 17%. Would you like detailed information about a specific plan?"""
                
                self.session_manager.add_message(
                    session_id,
                    role="assistant",
                    content=overview_msg,
                    agent=self.agent_name
                )
                
                return overview_msg
            
            product = pricing_data[product_key]
            
            # Update context
            self.session_manager.update_context(session_id, {
                "pricing_inquiry": product_key,
                "pricing_details": product
            })
            
            pricing_msg = f"""**{product['name']} Pricing:**

**Monthly:** {product['monthly']}
**Annual:** {product['annual']}

**Included Features:**
{chr(10).join(f"- {feature}" for feature in product['features'])}

**Available Add-ons:**
{chr(10).join(f"- {addon}" for addon in product['add_ons'])}

**Payment Options:** Credit card, PayPal, bank transfer (for annual plans)
**Free Trial:** 14-day free trial available for all plans

Would you like to proceed with a subscription or do you have questions about specific features?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=pricing_msg,
                agent=self.agent_name
            )
            
            return pricing_msg
            
        except Exception as e:
            logger.error(f"Error handling pricing inquiry: {e}")
            return "I apologize, but I encountered an error while retrieving pricing information."
    
    @ai_callable(description="Escalate the conversation to a human sales representative.")
    async def escalate_to_human(
        self,
        session_id: str,
        reason: str
    ) -> str:
        """
        Escalate to a human sales representative.
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "escalation_requested": True,
                "escalation_reason": reason,
                "escalation_agent": self.agent_name
            })
            
            escalation_msg = f"""I understand you'd like to speak with a human representative regarding: {reason}. I'm connecting you with our sales team now. They'll be able to provide more personalized assistance. Is there anything specific you'd like me to note before the transfer?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=escalation_msg,
                agent=self.agent_name
            )
            
            return escalation_msg
            
        except Exception as e:
            logger.error(f"Error handling escalation: {e}")
            return "Error: Failed to process escalation."
