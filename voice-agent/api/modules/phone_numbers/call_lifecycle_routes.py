"""
Call Lifecycle Routes.
API endpoints for managing call state transitions.
Called by LiveKit SIP, outbound campaigns, queues, and IVR services.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.call_lifecycle_service import CallLifecycleService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.call_lifecycle_routes")

router = APIRouter()


# --- Request Models ---

class CallStartedRequest(BaseModel):
    agentId: str = Field(..., min_length=1)


class CallAnsweredRequest(BaseModel):
    agentId: str = Field(..., min_length=1)


class CallCompletedRequest(BaseModel):
    agentId: str = Field(..., min_length=1)
    durationSeconds: int = Field(..., ge=0)


class CallFailedRequest(BaseModel):
    agentId: str = Field(..., min_length=1)


class CallMissedRequest(BaseModel):
    agentId: str = Field(..., min_length=1)


# --- Endpoints ---

@router.post("/calls/started")
async def call_started(
    req_body: CallStartedRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record call started event."""
    try:
        success = await CallLifecycleService.on_call_started(req_body.agentId)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record call started",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call started recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording call started: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calls/answered")
async def call_answered(
    req_body: CallAnsweredRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record call answered event."""
    try:
        success = await CallLifecycleService.on_call_answered(req_body.agentId)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record call answered",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call answered recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording call answered: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calls/completed")
async def call_completed(
    req_body: CallCompletedRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record call completed event."""
    try:
        success = await CallLifecycleService.on_call_completed(
            req_body.agentId,
            req_body.durationSeconds
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record call completed",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call completed recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording call completed: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calls/failed")
async def call_failed(
    req_body: CallFailedRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record call failed event."""
    try:
        success = await CallLifecycleService.on_call_failed(req_body.agentId)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record call failed",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call failed recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording call failed: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calls/missed")
async def call_missed(
    req_body: CallMissedRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record call missed event."""
    try:
        success = await CallLifecycleService.on_call_missed(req_body.agentId)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record call missed",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Call missed recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording call missed: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get comprehensive agent metrics."""
    try:
        metrics = await CallLifecycleService.get_agent_metrics(agent_id)
        
        if not metrics:
            return ApiResponse.error(
                status_code=404,
                message="Agent metrics not found",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Agent metrics retrieved successfully",
            data=metrics
        )
        
    except Exception as e:
        logger.error(f"Error getting agent metrics: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
