"""
Intent Routing Service.
Orchestrates intent-based capability routing.
Handles router agent selection, intent detection, and agent handoff.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database
from api.services.agent_routing_service import AgentRoutingService
from api.modules.phone_numbers.intent_service import IntentService
from api.modules.phone_numbers.router_agent_service import RouterAgentService
from api.modules.phone_numbers.conversation_handoff_service import ConversationHandoffService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.intent_routing_service")


class IntentRoutingService:
    """Service for intent-based capability routing."""
    
    @staticmethod
    async def get_routing_mode(phone_number_id: str) -> Optional[str]:
        """Get routing mode for a phone number."""
        try:
            query = "SELECT routing_mode FROM phone_numbers WHERE id = $1"
            rows = await database.query(query, [UUID(phone_number_id)])
            return rows[0]["routing_mode"] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting routing mode: {e}")
            return None
    
    @staticmethod
    async def set_routing_mode(
        phone_number_id: str,
        routing_mode: str
    ) -> bool:
        """Set routing mode for a phone number."""
        try:
            if routing_mode not in ["direct", "intent"]:
                logger.error(f"Invalid routing mode: {routing_mode}")
                return False
            
            query = """
                UPDATE phone_numbers 
                SET routing_mode = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """
            
            await database.query(query, [routing_mode, UUID(phone_number_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error setting routing mode: {e}")
            return False
    
    @staticmethod
    async def route_call(
        phone_number_id: str,
        user_id: str,
        client_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Route a call based on the phone number's routing mode.
        
        For DIRECT mode: Use existing direct agent routing
        For INTENT mode: Return router agent for intent detection
        """
        try:
            routing_mode = await IntentRoutingService.get_routing_mode(phone_number_id)
            
            if routing_mode == "intent":
                # Return router agent for intent-based routing
                router_agent = await RouterAgentService.get_router_agent(phone_number_id)
                if router_agent:
                    return {
                        "routing_mode": "intent",
                        "router_agent": router_agent,
                        "phone_number_id": phone_number_id
                    }
                else:
                    logger.warning(f"No router agent configured for phone {phone_number_id}")
                    return None
            
            else:
                # Default to direct agent routing
                agent = await AgentRoutingService.select_agent(phone_number_id)
                if agent:
                    return {
                        "routing_mode": "direct",
                        "agent": agent,
                        "phone_number_id": phone_number_id
                    }
                else:
                    logger.warning(f"No agents available for phone {phone_number_id}")
                    return None
            
        except Exception as e:
            logger.error(f"Error routing call: {e}")
            return None
    
    @staticmethod
    async def handle_intent_detection(
        phone_number_id: str,
        session_id: str,
        router_agent_id: str,
        detected_intent: str,
        confidence: float,
        user_id: str,
        client_id: Optional[str] = None,
        conversation_history: Optional[Dict] = None,
        session_state: Optional[Dict] = None,
        extracted_entities: Optional[Dict] = None,
        user_context: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle intent detection and route to appropriate agent.
        
        Flow:
        1. Get workflow for detected intent
        2. Execute workflow to get capability
        3. Get agents/groups with that capability
        4. Select agent based on routing strategy
        5. Create handoff record with full context
        6. Return selected agent or fallback to router agent
        """
        try:
            from api.modules.phone_numbers.workflow_service import WorkflowService
            from api.modules.phone_numbers.agent_group_service import AgentGroupService
            
            # Get workflow for intent
            workflow_mapping = await WorkflowService.get_workflow_for_intent(
                detected_intent,
                user_id,
                client_id
            )
            
            if not workflow_mapping:
                logger.info(f"No workflow found for intent {detected_intent}, continuing with router agent")
                return {
                    "action": "continue_with_router",
                    "reason": "no_workflow_found",
                    "detected_intent": detected_intent,
                    "confidence": confidence
                }
            
            # Check confidence threshold
            if confidence < workflow_mapping.get("confidence_threshold", 0.7):
                logger.info(f"Confidence {confidence} below threshold {workflow_mapping['confidence_threshold']}, continuing with router agent")
                return {
                    "action": "continue_with_router",
                    "reason": "low_confidence",
                    "detected_intent": detected_intent,
                    "confidence": confidence,
                    "threshold": workflow_mapping["confidence_threshold"]
                }
            
            # Execute workflow to get entry capability
            workflow_result = await WorkflowService.execute_workflow(workflow_mapping["workflow_id"])
            
            if not workflow_result or not workflow_result.get("entry_capability_id"):
                logger.info(f"Workflow {workflow_mapping['workflow_id']} returned no capability")
                return {
                    "action": "continue_with_router",
                    "reason": "workflow_no_capability",
                    "detected_intent": detected_intent,
                    "workflow_id": str(workflow_mapping["workflow_id"])
                }
            
            capability_id = workflow_result["entry_capability_id"]
            
            # Get capability target (agent or group)
            from api.modules.phone_numbers.capability_service import CapabilityService
            capability_target = await CapabilityService.get_capability_target(capability_id)
            
            if not capability_target:
                logger.info(f"No target configured for capability {capability_id}")
                return {
                    "action": "continue_with_router",
                    "reason": "no_capability_target",
                    "detected_intent": detected_intent,
                    "capability_id": capability_id
                }
            
            # Select agent based on target type
            selected_agent = None
            
            if capability_target["target_type"] == "agent":
                # Direct agent target
                if capability_target["target_agent_id"]:
                    # Get agent details
                    query = "SELECT id, name, type, status FROM agents WHERE id = $1 AND status = 'active'"
                    rows = await database.query(query, [UUID(capability_target["target_agent_id"])])
                    if rows:
                        selected_agent = rows[0]
            
            elif capability_target["target_type"] == "group":
                # Agent group target - select best available agent
                if capability_target["target_group_id"]:
                    group_members = await AgentGroupService.get_group_members(capability_target["target_group_id"])
                    if group_members:
                        # Select first available agent from group
                        for member in group_members:
                            if await AgentRoutingService.validate_availability(str(member["agent_id"])):
                                if await AgentRoutingService.validate_capacity(str(member["agent_id"])):
                                    selected_agent = member
                                    break
            
            if not selected_agent:
                logger.info(f"No available agents for capability {capability_id}")
                return {
                    "action": "continue_with_router",
                    "reason": "no_agents_available",
                    "detected_intent": detected_intent,
                    "capability_id": capability_id
                }
            
            # Create handoff record
            from api.modules.phone_numbers.conversation_session_service import ConversationSessionService
            handoff = await ConversationSessionService.create_handoff(
                session_id=session_id,
                from_agent_id=router_agent_id,
                to_agent_id=str(selected_agent["id"]),
                workflow_id=str(workflow_mapping["workflow_id"]),
                capability_id=capability_id,
                detected_intent=detected_intent,
                confidence=confidence,
                reason="intent_detected"
            )
            
            if not handoff:
                logger.error("Failed to create handoff record")
                return {
                    "action": "continue_with_router",
                    "reason": "handoff_creation_failed",
                    "detected_intent": detected_intent
                }
            
            return {
                "action": "transfer_to_agent",
                "detected_intent": detected_intent,
                "workflow_id": str(workflow_mapping["workflow_id"]),
                "workflow_name": workflow_mapping.get("workflow_name"),
                "capability_id": capability_id,
                "capability_name": capability_target.get("capability_name"),
                "confidence": confidence,
                "agent": selected_agent,
                "handoff_id": str(handoff["id"]),
                "conversation_history": conversation_history,
                "session_state": session_state,
                "extracted_entities": extracted_entities,
                "user_context": user_context
            }
            
        except Exception as e:
            logger.error(f"Error handling intent detection: {e}")
            return {
                "action": "continue_with_router",
                "reason": "error",
                "error": str(e)
            }
    
    @staticmethod
    async def fallback_to_router(
        phone_number_id: str,
        session_id: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback to router agent when intent routing fails.
        """
        try:
            router_agent = await RouterAgentService.get_router_agent(phone_number_id)
            
            if not router_agent:
                logger.error(f"No router agent available for fallback on phone {phone_number_id}")
                return None
            
            return {
                "action": "continue_with_router",
                "reason": reason,
                "router_agent": router_agent,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error falling back to router: {e}")
            return None
