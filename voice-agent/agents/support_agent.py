"""
Support Agent.
Handles customer support queries and troubleshooting.
"""

import logging
from typing import Dict, Any, Optional
from livekit.agents import llm
from session_manager import SessionManager

if not hasattr(llm, 'ai_callable'):
    llm.ai_callable = llm.function_tool

logger = logging.getLogger(__name__)


class SupportAgent:
    """Agent for handling customer support conversations."""
    
    def __init__(self, session_manager: SessionManager):
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
    
    @llm.ai_callable(description="Provide troubleshooting steps for a technical issue.")
    async def troubleshoot_issue(
        self,
        session_id: str,
        issue_description: str
    ) -> str:
        """
        Provide troubleshooting steps for an issue.
        """
        try:
            issue_lower = issue_description.lower()
            
            # Troubleshooting knowledge base
            troubleshooting_guide = {
                "login": {
                    "title": "Login Issues",
                    "steps": [
                        "Verify you're using the correct email address",
                        "Check that caps lock is not enabled",
                        "Reset your password using the 'Forgot Password' link",
                        "Clear your browser cache and cookies",
                        "Try a different browser or incognito mode",
                        "Ensure your account is not locked (check for email notifications)"
                    ],
                    "common_causes": ["Incorrect credentials", "Account lockout", "Browser issues", "Expired session"],
                    "when_to_escalate": "If you've tried all steps and still cannot login after 15 minutes"
                },
                "connection": {
                    "title": "Connection/Network Issues",
                    "steps": [
                        "Check your internet connection",
                        "Restart your router/modem",
                        "Disable VPN if enabled",
                        "Check firewall settings",
                        "Try accessing from a different network",
                        "Verify our service status page for outages"
                    ],
                    "common_causes": ["Internet outage", "VPN interference", "Firewall blocking", "Service outage"],
                    "when_to_escalate": "If the issue persists across different networks"
                },
                "performance": {
                    "title": "Performance/Slow Loading",
                    "steps": [
                        "Close other browser tabs and applications",
                        "Clear browser cache",
                        "Disable browser extensions",
                        "Check your internet speed",
                        "Try a different browser",
                        "Reduce the number of concurrent operations"
                    ],
                    "common_causes": ["High memory usage", "Slow internet", "Browser extensions", "Server load"],
                    "when_to_escalate": "If performance issues persist after optimization"
                },
                "data": {
                    "title": "Data/Sync Issues",
                    "steps": [
                        "Check your last sync timestamp",
                        "Ensure you have stable internet connection",
                        "Refresh the page or restart the application",
                        "Check if data is visible on other devices",
                        "Verify your account storage limits",
                        "Contact support if data appears lost"
                    ],
                    "common_causes": ["Sync delay", "Network interruption", "Storage limit reached", "Account issue"],
                    "when_to_escalate": "If data is missing or corrupted"
                }
            }
            
            # Determine issue category
            issue_category = None
            if any(keyword in issue_lower for keyword in ["login", "sign in", "password", "auth", "access"]):
                issue_category = "login"
            elif any(keyword in issue_lower for keyword in ["connect", "network", "internet", "offline", "timeout"]):
                issue_category = "connection"
            elif any(keyword in issue_lower for keyword in ["slow", "lag", "performance", "loading", "freeze"]):
                issue_category = "performance"
            elif any(keyword in issue_lower for keyword in ["sync", "data", "save", "upload", "missing"]):
                issue_category = "data"
            
            if not issue_category:
                # Generic troubleshooting
                generic_msg = f"""I understand you're experiencing: {issue_description}

Let me help you troubleshoot this. Here are some general steps:

1. **Restart** - Try restarting the application or refreshing the page
2. **Check connection** - Ensure you have a stable internet connection
3. **Clear cache** - Clear your browser cache and cookies
4. **Try different browser** - Test in a different browser or incognito mode
5. **Check status** - Visit our status page to see if there are any known outages

If these steps don't resolve your issue, please provide more details about:
- When the issue started
- What you were doing when it occurred
- Any error messages you're seeing

Would you like me to escalate this to a technical specialist?"""
                
                self.session_manager.add_message(
                    session_id,
                    role="assistant",
                    content=generic_msg,
                    agent=self.agent_name
                )
                
                return generic_msg
            
            guide = troubleshooting_guide[issue_category]
            
            # Update context
            self.session_manager.update_context(session_id, {
                "issue_category": issue_category,
                "issue_description": issue_description
            })
            
            troubleshooting_msg = f"""**{guide['title']} - Troubleshooting Guide**

**Step-by-Step Solutions:**
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(guide['steps']))}

**Common Causes:**
{chr(10).join(f"- {cause}" for cause in guide['common_causes'])}

**When to Escalate:** {guide['when_to_escalate']}

**Prevention Tips:**
- Keep your browser and application updated
- Use a stable internet connection
- Regularly clear your cache
- Enable two-factor authentication for security

Please try these steps and let me know if the issue is resolved or if you need further assistance."""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=troubleshooting_msg,
                agent=self.agent_name
            )
            
            return troubleshooting_msg
            
        except Exception as e:
            logger.error(f"Error providing troubleshooting: {e}")
            return "I apologize, but I encountered an error while retrieving troubleshooting information."
    
    @llm.ai_callable(description="Handle billing-related inquiries.")
    async def handle_billing_inquiry(
        self,
        session_id: str,
        inquiry: str
    ) -> str:
        """
        Handle billing-related inquiries.
        """
        try:
            inquiry_lower = inquiry.lower()
            
            # Billing information and policies
            billing_info = {
                "invoice": {
                    "title": "Invoice Questions",
                    "info": "Invoices are generated on the 1st of each month and sent to your registered email. You can also download invoices from your account dashboard under 'Billing > Invoices'.",
                    "actions": ["Check your email for the invoice", "Login to your dashboard to download", "Contact billing if invoice is missing"]
                },
                "payment": {
                    "title": "Payment Methods",
                    "info": "We accept credit cards (Visa, MasterCard, American Express), PayPal, and bank transfers for annual plans. Payments are processed automatically on your billing date.",
                    "actions": ["Update payment method in dashboard", "Add backup payment method", "Set up auto-pay for convenience"]
                },
                "refund": {
                    "title": "Refund Policy",
                    "info": "Refunds are available within 30 days of purchase for monthly plans and 14 days for annual plans. Refund requests are processed within 5-7 business days.",
                    "actions": ["Submit refund request through dashboard", "Contact billing support for assistance", "Provide reason for refund"]
                },
                "charge": {
                    "title": "Unexpected Charges",
                    "info": "If you see unexpected charges, check for: add-on services, overage fees, or prorated charges from plan changes. Review your billing history in the dashboard.",
                    "actions": ["Review billing history in dashboard", "Check for add-on services", "Verify plan change dates"]
                },
                "upgrade": {
                    "title": "Plan Changes",
                    "info": "Upgrades are prorated and take effect immediately. Downgrades take effect at the next billing cycle. No fees for plan changes.",
                    "actions": ["Change plan in dashboard", "Contact support for assistance", "Review feature comparison before changing"]
                }
            }
            
            # Determine inquiry category
            inquiry_category = None
            if any(keyword in inquiry_lower for keyword in ["invoice", "receipt", "bill", "statement"]):
                inquiry_category = "invoice"
            elif any(keyword in inquiry_lower for keyword in ["payment", "credit card", "paypal", "bank", "pay"]):
                inquiry_category = "payment"
            elif any(keyword in inquiry_lower for keyword in ["refund", "money back", "return"]):
                inquiry_category = "refund"
            elif any(keyword in inquiry_lower for keyword in ["charge", "fee", "cost", "unexpected", "overcharge"]):
                inquiry_category = "charge"
            elif any(keyword in inquiry_lower for keyword in ["upgrade", "downgrade", "change plan", "switch"]):
                inquiry_category = "upgrade"
            
            if not inquiry_category:
                # Generic billing response
                generic_msg = f"""I understand you have a billing inquiry: {inquiry}

Here's some general billing information:

**Invoice Delivery:** Invoices are sent on the 1st of each month to your registered email
**Payment Methods:** Credit cards, PayPal, bank transfers (annual plans)
**Refund Policy:** 30 days for monthly plans, 14 days for annual plans
**Plan Changes:** Upgrades immediate, downgrades next billing cycle

To help you better, could you specify if your inquiry is about:
- Invoices or receipts
- Payment methods or failed payments
- Refund requests
- Unexpected charges
- Plan upgrades or downgrades

Or I can connect you with our billing team for direct assistance."""
                
                self.session_manager.add_message(
                    session_id,
                    role="assistant",
                    content=generic_msg,
                    agent=self.agent_name
                )
                
                return generic_msg
            
            info = billing_info[inquiry_category]
            
            # Update context
            self.session_manager.update_context(session_id, {
                "billing_inquiry": inquiry_category,
                "inquiry_details": inquiry
            })
            
            billing_msg = f"""**{info['title']}**

{info['info']}

**Recommended Actions:**
{chr(10).join(f"- {action}" for action in info['actions'])}

**Additional Resources:**
- Access your billing dashboard: account settings > billing
- Download past invoices from the invoices section
- Contact billing@support.com for complex issues
- Billing support hours: 9 AM - 6 PM EST, Mon-Fri

Is there anything specific about this billing matter I can help you with, or would you like me to escalate this to our billing team?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=billing_msg,
                agent=self.agent_name
            )
            
            return billing_msg
            
        except Exception as e:
            logger.error(f"Error handling billing inquiry: {e}")
            return "I apologize, but I encountered an error while processing your billing inquiry."
    
    @llm.ai_callable(description="Escalate an issue to a human support representative.")
    async def escalate_issue(
        self,
        session_id: str,
        category: str,
        description: str,
        urgency: str
    ) -> str:
        """
        Escalate an issue to a human support representative.
        """
        try:
            issue_details = {
                "category": category,
                "description": description,
                "urgency": urgency
            }
            # Update context
            self.session_manager.update_context(session_id, {
                "escalation_requested": True,
                "escalation_details": issue_details,
                "escalation_agent": self.agent_name
            })
            
            escalation_msg = f"""I understand this issue requires additional assistance. I'm escalating this to our support team.
Issue Summary:
- Category: {category}
- Description: {description}
- Urgency: {urgency}
A support representative will review your case and follow up within 24 hours. Is there anything else you'd like me to add to this ticket?"""
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=escalation_msg,
                agent=self.agent_name
            )
            
            return escalation_msg
            
        except Exception as e:
            logger.error(f"Error handling issue escalation: {e}")
            return "Error: Failed to process escalation."
    
    @llm.ai_callable(description="Confirm that an issue has been successfully resolved.")
    async def confirm_resolution(
        self,
        session_id: str,
        resolution_summary: str
    ) -> str:
        """
        Confirm issue resolution with the user.
        """
        try:
            # Update context
            self.session_manager.update_context(session_id, {
                "resolution_status": "resolved",
                "resolution_summary": resolution_summary
            })
            
            confirmation_msg = f"Great! I'm glad we could resolve your issue. Resolution Summary: {resolution_summary}. Is there anything else I can help you with today?"
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=confirmation_msg,
                agent=self.agent_name
            )
            
            return confirmation_msg
            
        except Exception as e:
            logger.error(f"Error confirming resolution: {e}")
            return "Error: Failed to confirm resolution."
