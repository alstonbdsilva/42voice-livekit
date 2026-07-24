"""
Agent Status Routes.
API endpoints for managing agent availability and status.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.agent_status_service import AgentStatusService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.agent_status_routes")

router = APIRouter()


# --- Request Models ---

class SetAvailabilityRequest(BaseModel):
    availability: str = Field(..., pattern="^(available|busy|offline|paused|maintenance)$")


class UpdateMaxCallsRequest(BaseModel):
    maxConcurrentCalls: int = Field(..., ge=1)


# --- Endpoints ---

@router.get("/agents/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get agent status."""
    try:
        status = await AgentStatusService.get_agent_status(agent_id)
        
        if not status:
            return ApiResponse.error(
                status_code=404,
                message="Agent status not found",
                code="STATUS_NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Agent status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.patch("/agents/{agent_id}/availability")
async def set_availability(
    agent_id: str,
    req_body: SetAvailabilityRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Set agent availability status."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        availability_map = {
            "available": AgentStatusService.set_available,
            "busy": AgentStatusService.set_busy,
            "offline": AgentStatusService.set_offline,
            "paused": AgentStatusService.set_paused,
            "maintenance": AgentStatusService.set_maintenance
        }
        
        setter = availability_map.get(req_body.availability)
        if not setter:
            return ApiResponse.error(
                status_code=400,
                message="Invalid availability status",
                code="INVALID_STATUS"
            )
        
        success = await setter(agent_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to update availability",
                code="UPDATE_FAILED"
            )
        
        status = await AgentStatusService.get_agent_status(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Availability updated successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Error setting availability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.patch("/agents/{agent_id}/max-calls")
async def update_max_calls(
    agent_id: str,
    req_body: UpdateMaxCallsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update max concurrent calls for agent."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await AgentStatusService.update_max_concurrent_calls(
            agent_id,
            req_body.maxConcurrentCalls
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to update max concurrent calls",
                code="UPDATE_FAILED"
            )
        
        status = await AgentStatusService.get_agent_status(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Max concurrent calls updated successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Error updating max calls: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
