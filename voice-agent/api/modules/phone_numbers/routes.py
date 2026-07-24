"""
Phone Numbers Routes.
API endpoints for phone number and agent assignment management.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.services import PhoneNumberService, PhoneNumberAgentService
from api.modules.phone_numbers.agent_status_service import AgentStatusService
from api.modules.phone_numbers import agent_status_routes
from api.modules.phone_numbers import business_hours_routes
from api.modules.phone_numbers import call_lifecycle_routes
from api.modules.phone_numbers import agent_health_routes
from api.modules.phone_numbers import capability_routes
from api.modules.phone_numbers import intent_routes
from api.modules.phone_numbers import intent_routing_routes

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.routes")

router = APIRouter()
phone_service = PhoneNumberService()
agent_service = PhoneNumberAgentService()

# Include sub-routers
router.include_router(agent_status_routes.router)
router.include_router(business_hours_routes.router)
router.include_router(call_lifecycle_routes.router)
router.include_router(agent_health_routes.router)
router.include_router(capability_routes.router)
router.include_router(intent_routes.router)
router.include_router(intent_routing_routes.router)


# --- Request Models ---

class CreatePhoneNumberRequest(BaseModel):
    number: str = Field(..., min_length=5)
    provider: str = Field(..., min_length=1)
    callType: Optional[str] = Field(default="inbound")
    friendlyName: Optional[str] = None
    providerId: Optional[str] = None


class AssignAgentRequest(BaseModel):
    agentId: str = Field(..., min_length=1)
    priority: int = Field(default=0, ge=0)
    routingStrategy: str = Field(default="priority")
    isPrimary: bool = Field(default=False)
    maxConcurrentCalls: Optional[int] = Field(default=5, ge=1)
    businessHoursTimezone: Optional[str] = None
    afterHoursAgentId: Optional[str] = None


class UpdateRoutingStrategyRequest(BaseModel):
    routingStrategy: str = Field(..., min_length=1)


# --- Phone Number Endpoints ---

@router.post("")
async def create_phone_number(
    req_body: CreatePhoneNumberRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new phone number."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        phone_number = await phone_service.create_phone_number(
            number=req_body.number,
            provider=req_body.provider,
            user_id=user_id,
            client_id=client_id,
            call_type=req_body.callType,
            friendly_name=req_body.friendlyName,
            provider_id=req_body.providerId
        )
        
        if not phone_number:
            return ApiResponse.error(
                status_code=400,
                message="Failed to create phone number",
                code="PHONE_CREATION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Phone number created successfully",
            data=phone_number
        )
        
    except Exception as e:
        logger.error(f"Error creating phone number: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("")
async def list_phone_numbers(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List all phone numbers for the current user."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        # Get phone numbers based on user context
        if client_id:
            phone_numbers = await phone_service.get_client_phone_numbers(client_id)
        else:
            phone_numbers = await phone_service.get_user_phone_numbers(user_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Phone numbers retrieved successfully",
            data={"phoneNumbers": phone_numbers}
        )
        
    except Exception as e:
        logger.error(f"Error listing phone numbers: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/{phone_number_id}")
async def get_phone_number(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get phone number details."""
    try:
        phone_number = await phone_service.get_phone_number(phone_number_id)
        
        if not phone_number:
            return ApiResponse.error(
                status_code=404,
                message="Phone number not found",
                code="PHONE_NOT_FOUND"
            )
        
        # Validate ownership
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if phone_number["user_id"] != user_id and phone_number["client_id"] != client_id:
            return ApiResponse.error(
                status_code=403,
                message="Forbidden",
                code="FORBIDDEN"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Phone number retrieved successfully",
            data=phone_number
        )
        
    except Exception as e:
        logger.error(f"Error getting phone number: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


# --- Agent Assignment Endpoints ---

@router.get("/{phone_number_id}/agents")
async def get_phone_agents(
    phone_number_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all agents assigned to a phone number."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        agents = await agent_service.get_phone_agents(phone_number_id, user_id, client_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Agents retrieved successfully",
            data={"agents": agents}
        )
        
    except Exception as e:
        logger.error(f"Error getting phone agents: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/{phone_number_id}/agents")
async def assign_agent(
    phone_number_id: str,
    req_body: AssignAgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Assign an agent to a phone number with availability and capacity management."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        assignment = await agent_service.assign_agent(
            phone_number_id=phone_number_id,
            agent_id=req_body.agentId,
            user_id=user_id,
            client_id=client_id,
            priority=req_body.priority,
            routing_strategy=req_body.routingStrategy,
            is_primary=req_body.isPrimary,
            max_concurrent_calls=req_body.maxConcurrentCalls,
            business_hours_timezone=req_body.businessHoursTimezone,
            after_hours_agent_id=req_body.afterHoursAgentId
        )
        
        if not assignment:
            return ApiResponse.error(
                status_code=400,
                message="Failed to assign agent",
                code="ASSIGNMENT_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Agent assigned successfully",
            data=assignment
        )
        
    except Exception as e:
        logger.error(f"Error assigning agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/{phone_number_id}/agents/{agent_id}")
async def remove_agent(
    phone_number_id: str,
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove an agent from a phone number."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await agent_service.remove_agent(
            phone_number_id=phone_number_id,
            agent_id=agent_id,
            user_id=user_id,
            client_id=client_id
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to remove agent",
                code="REMOVAL_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Agent removed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error removing agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.patch("/{phone_number_id}/routing")
async def update_routing_strategy(
    phone_number_id: str,
    req_body: UpdateRoutingStrategyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update the routing strategy for a phone number."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await agent_service.update_routing_strategy(
            phone_number_id=phone_number_id,
            routing_strategy=req_body.routingStrategy,
            user_id=user_id,
            client_id=client_id
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to update routing strategy",
                code="UPDATE_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Routing strategy updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error updating routing strategy: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


# --- Agent Phone Numbers Endpoint ---

@router.get("/agents/{agent_id}/phone-numbers")
async def get_agent_phones(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all phone numbers assigned to an agent."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        phones = await agent_service.get_agent_phones(agent_id, user_id, client_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Phone numbers retrieved successfully",
            data={"phoneNumbers": phones}
        )
        
    except Exception as e:
        logger.error(f"Error getting agent phones: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
