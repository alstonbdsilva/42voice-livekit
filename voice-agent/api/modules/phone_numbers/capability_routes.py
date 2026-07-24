"""
Capability Routes.
API endpoints for managing capabilities and agent capabilities.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.capability_service import CapabilityService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.capability_routes")

router = APIRouter()


# --- Request Models ---

class CreateCapabilityRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None


class AssignCapabilityRequest(BaseModel):
    agentId: str = Field(..., min_length=1)
    capabilityId: str = Field(..., min_length=1)
    priority: int = Field(default=0, ge=0)


class RemoveCapabilityRequest(BaseModel):
    agentId: str = Field(..., min_length=1)
    capabilityId: str = Field(..., min_length=1)


# --- Endpoints ---

@router.post("/capabilities")
async def create_capability(
    req_body: CreateCapabilityRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new capability."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        capability = await CapabilityService.create_capability(
            name=req_body.name,
            user_id=user_id,
            client_id=client_id,
            description=req_body.description
        )
        
        if not capability:
            return ApiResponse.error(
                status_code=400,
                message="Failed to create capability",
                code="CREATION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Capability created successfully",
            data=capability
        )
        
    except Exception as e:
        logger.error(f"Error creating capability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/capabilities")
async def list_capabilities(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all capabilities."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        if client_id:
            capabilities = await CapabilityService.get_client_capabilities(client_id)
        else:
            capabilities = await CapabilityService.get_user_capabilities(user_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Capabilities retrieved successfully",
            data={"capabilities": capabilities}
        )
        
    except Exception as e:
        logger.error(f"Error listing capabilities: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/capabilities/{capability_id}")
async def get_capability(
    capability_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get capability details."""
    try:
        capability = await CapabilityService.get_capability(capability_id)
        
        if not capability:
            return ApiResponse.error(
                status_code=404,
                message="Capability not found",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Capability retrieved successfully",
            data=capability
        )
        
    except Exception as e:
        logger.error(f"Error getting capability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/agents/{agent_id}/capabilities")
async def assign_capability(
    agent_id: str,
    req_body: AssignCapabilityRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Assign a capability to an agent."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        assignment = await CapabilityService.assign_capability_to_agent(
            agent_id=req_body.agentId,
            capability_id=req_body.capabilityId,
            priority=req_body.priority
        )
        
        if not assignment:
            return ApiResponse.error(
                status_code=400,
                message="Failed to assign capability",
                code="ASSIGNMENT_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Capability assigned successfully",
            data=assignment
        )
        
    except Exception as e:
        logger.error(f"Error assigning capability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/agents/{agent_id}/capabilities")
async def get_agent_capabilities(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all capabilities for an agent."""
    try:
        capabilities = await CapabilityService.get_agent_capabilities(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Agent capabilities retrieved successfully",
            data={"capabilities": capabilities}
        )
        
    except Exception as e:
        logger.error(f"Error getting agent capabilities: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/agents/{agent_id}/capabilities/{capability_id}")
async def remove_capability(
    agent_id: str,
    capability_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove a capability from an agent."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await CapabilityService.remove_capability_from_agent(agent_id, capability_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to remove capability",
                code="REMOVAL_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Capability removed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error removing capability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
