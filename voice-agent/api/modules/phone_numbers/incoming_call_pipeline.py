"""
Incoming Call Pipeline.
Processes inbound calls through routing engine.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.phone_numbers.phone_numbers_service import PhoneNumbersService
from api.modules.phone_numbers.business_hours_service import BusinessHoursService
from api.modules.phone_numbers.spam_detection_service import SpamDetectionService
from api.modules.phone_numbers.event_bus import EventBus

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.incoming_call_pipeline")


class IncomingCallPipeline:
    """Pipeline for processing incoming calls."""
    
    @staticmethod
    async def process_incoming_call(
        from_number: str,
        to_number: str,
        call_id: str,
        provider: str,
        webhook_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process incoming call through pipeline.
        
        Flow:
        1. Phone Number Lookup
        2. Tenant Resolution
        3. Business Hours Check
        4. Spam Detection
        5. Routing Engine
        6. Workflow Execution
        """
        try:
            # Step 1: Phone Number Lookup
            phone_number = await PhoneNumbersService.get_number_by_e164(None, to_number)
            
            if not phone_number:
                logger.warning(f"Phone number not found: {to_number}")
                return None
            
            phone_number_id = str(phone_number.get("id"))
            tenant_id = str(phone_number.get("tenant_id"))
            
            # Step 2: Tenant Resolution (already done via phone number lookup)
            
            # Step 3: Business Hours Check
            business_hours_id = phone_number.get("business_hours_id")
            if business_hours_id:
                is_business_hours = await BusinessHoursService.is_business_hours(
                    str(business_hours_id)
                )
                
                if not is_business_hours:
                    logger.info(f"Call outside business hours: {phone_number_id}")
                    # Route to after-hours workflow
                    return await IncomingCallPipeline._route_after_hours(
                        phone_number_id,
                        tenant_id,
                        from_number,
                        to_number,
                        call_id
                    )
            
            # Step 4: Spam Detection
            if phone_number.get("spam_protection_enabled"):
                spam_result = await SpamDetectionService.check_spam(from_number, tenant_id)
                
                if spam_result.get("is_spam"):
                    logger.warning(f"Spam detected: {from_number}")
                    # Publish event
                    await EventBus.publish_call_started(phone_number_id, "spam_detected")
                    
                    # Log audit
                    await PhoneNumbersService._log_audit(
                        phone_number_id,
                        tenant_id,
                        "spam_detected",
                        "system",
                        None,
                        {"from_number": from_number, "spam_score": spam_result.get("spam_score")}
                    )
                    
                    return None
            
            # Step 5: Routing Engine
            routing_result = await IncomingCallPipeline._route_call(
                phone_number_id,
                tenant_id,
                from_number,
                to_number,
                call_id,
                phone_number
            )
            
            # Publish event
            await EventBus.publish_call_started(phone_number_id, "incoming_call_received")
            
            # Log audit
            await PhoneNumbersService._log_audit(
                phone_number_id,
                tenant_id,
                "call_initiated",
                "webhook",
                None,
                {"from_number": from_number, "call_id": call_id}
            )
            
            return routing_result
            
        except Exception as e:
            logger.error(f"Error processing incoming call: {e}")
            return None
    
    @staticmethod
    async def _route_call(
        phone_number_id: str,
        tenant_id: str,
        from_number: str,
        to_number: str,
        call_id: str,
        phone_number: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Route call through routing engine."""
        try:
            # Get assignments for phone number
            query = """
                SELECT assignment_type, workflow_id, agent_group_id, router_agent_id,
                       default_agent_id, priority
                FROM phone_number_assignments
                WHERE phone_number_id = $1 AND is_active = TRUE
                ORDER BY priority DESC
            """
            
            assignments = await database.query(query, [UUID(phone_number_id)])
            
            if not assignments:
                logger.warning(f"No assignments for phone number: {phone_number_id}")
                return None
            
            # Route based on assignment type
            for assignment in assignments:
                assignment_type = assignment.get("assignment_type")
                
                if assignment_type == "workflow":
                    # Route to workflow
                    workflow_id = assignment.get("workflow_id")
                    return {
                        "routing_type": "workflow",
                        "workflow_id": str(workflow_id),
                        "call_id": call_id,
                        "from_number": from_number,
                        "to_number": to_number
                    }
                
                elif assignment_type == "agent_group":
                    # Route to agent group
                    agent_group_id = assignment.get("agent_group_id")
                    return {
                        "routing_type": "agent_group",
                        "agent_group_id": str(agent_group_id),
                        "call_id": call_id,
                        "from_number": from_number,
                        "to_number": to_number
                    }
                
                elif assignment_type == "router_agent":
                    # Route to router agent
                    router_agent_id = assignment.get("router_agent_id")
                    return {
                        "routing_type": "router_agent",
                        "router_agent_id": str(router_agent_id),
                        "call_id": call_id,
                        "from_number": from_number,
                        "to_number": to_number
                    }
                
                elif assignment_type == "default_agent":
                    # Route to default agent
                    default_agent_id = assignment.get("default_agent_id")
                    return {
                        "routing_type": "default_agent",
                        "agent_id": str(default_agent_id),
                        "call_id": call_id,
                        "from_number": from_number,
                        "to_number": to_number
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error routing call: {e}")
            return None
    
    @staticmethod
    async def _route_after_hours(
        phone_number_id: str,
        tenant_id: str,
        from_number: str,
        to_number: str,
        call_id: str
    ) -> Optional[Dict[str, Any]]:
        """Route call to after-hours workflow."""
        try:
            # Get after-hours workflow assignment
            query = """
                SELECT workflow_id FROM phone_number_assignments
                WHERE phone_number_id = $1
                AND assignment_type = 'workflow'
                AND is_active = TRUE
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(phone_number_id)])
            
            if rows:
                return {
                    "routing_type": "after_hours_workflow",
                    "workflow_id": str(rows[0].get("workflow_id")),
                    "call_id": call_id,
                    "from_number": from_number,
                    "to_number": to_number
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error routing after-hours call: {e}")
            return None
