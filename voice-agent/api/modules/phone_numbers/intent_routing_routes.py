"""
Intent Routing Routes.
API endpoints for intent-based routing orchestration.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.intent_routing_service import IntentRoutingService
from api.modules.phone_numbers.router_agent_service import RouterAgentService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.intent_routing_routes")

router = APIRouter()


# --- Request Models ---

class SetRoutingModeRequest(BaseModel):
    routingMode: str = Field(..., pattern="^(direct|intent)$")


class SetRouterAgentRequest(BaseModel):
    agentId: str = Field(..., min_length=1)


class HandleIntentDetectionRequest(BaseModel):
    sessionId: str = Field(..., min_length=1)
    routerAgentId: str = Field(..., min_length=1)
    detectedIntent: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    conversationHistory: Optional[Dict] = None
    sessionState: Optional[Dict] = None
    extractedEntities: Optional[Dict] = None
    userContext: Optional[Dict] = None


# --- Endpoints ---

@router.patch("/phone-numbers/{phone_number_id}/routing-mode")
async def set_routing_mode(
    phone_number_id: str,
    req_body: SetRoutingModeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Set routing mode for a phone number."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await IntentRoutingService.set_routing_mode(
            phone_number_id,
            req_body.routingMode
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to set routing mode",
                code="UPDATE_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Routing mode updated successfully",
            data={"routingMode": req_body.routingMode}
        )
        
    except Exception as e:
        logger.error(f"Error setting routing mode: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/phone-numbers/{phone_number_id}/routing-mode")
async def get_routing_mode(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get routing mode for a phone number."""
    try:
        routing_mode = await IntentRoutingService.get_routing_mode(phone_number_id)
        
        if not routing_mode:
            return ApiResponse.error(
                status_code=404,
                message="Phone number not found",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Routing mode retrieved successfully",
            data={"routingMode": routing_mode}
        )
        
    except Exception as e:
        logger.error(f"Error getting routing mode: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/phone-numbers/{phone_number_id}/router-agent")
async def set_router_agent(
    phone_number_id: str,
    req_body: SetRouterAgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Set router agent for a phone number."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        router_agent = await RouterAgentService.set_router_agent(
            phone_number_id,
            req_body.agentId
        )
        
        if not router_agent:
            return ApiResponse.error(
                status_code=400,
                message="Failed to set router agent",
                code="UPDATE_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Router agent set successfully",
            data=router_agent
        )
        
    except Exception as e:
        logger.error(f"Error setting router agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/phone-numbers/{phone_number_id}/router-agent")
async def get_router_agent(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get router agent for a phone number."""
    try:
        router_agent = await RouterAgentService.get_router_agent(phone_number_id)
        
        if not router_agent:
            return ApiResponse.error(
                status_code=404,
                message="Router agent not found",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Router agent retrieved successfully",
            data=router_agent
        )
        
    except Exception as e:
        logger.error(f"Error getting router agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/phone-numbers/{phone_number_id}/router-agent")
async def remove_router_agent(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove router agent from a phone number."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await RouterAgentService.remove_router_agent(phone_number_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to remove router agent",
                code="REMOVAL_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Router agent removed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error removing router agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/routing/handle-intent")
async def handle_intent_detection(
    req_body: HandleIntentDetectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Handle intent detection and route to appropriate agent.
    Called by router agent after detecting intent.
    """
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        result = await IntentRoutingService.handle_intent_detection(
            phone_number_id="",  # Not needed for this operation
            session_id=req_body.sessionId,
            router_agent_id=req_body.routerAgentId,
            detected_intent=req_body.detectedIntent,
            confidence=req_body.confidence,
            user_id=user_id,
            client_id=client_id,
            conversation_history=req_body.conversationHistory,
            session_state=req_body.sessionState,
            extracted_entities=req_body.extractedEntities,
            user_context=req_body.userContext
        )
        
        if not result:
            return ApiResponse.error(
                status_code=400,
                message="Failed to handle intent detection",
                code="HANDLING_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Intent handled successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error handling intent detection: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/routing/route-call")
async def route_call(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Route a call based on phone number's routing mode.
    Returns either direct agent or router agent.
    """
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        result = await IntentRoutingService.route_call(
            phone_number_id,
            user_id,
            client_id
        )
        
        if not result:
            return ApiResponse.error(
                status_code=400,
                message="Failed to route call",
                code="ROUTING_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call routed successfully",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error routing call: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
