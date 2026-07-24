"""
Agent Health Routes.
API endpoints for agent heartbeat and health monitoring.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.agent_health_service import AgentHealthService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.agent_health_routes")

router = APIRouter()


# --- Endpoints ---

@router.post("/agents/{agent_id}/heartbeat")
async def record_heartbeat(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record agent heartbeat."""
    try:
        success = await AgentHealthService.record_heartbeat(agent_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to record heartbeat",
                code="RECORD_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Heartbeat recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error recording heartbeat: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/agents/{agent_id}/health")
async def get_health_status(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get agent health status."""
    try:
        health = await AgentHealthService.get_health_status(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Health status retrieved successfully",
            data={"healthStatus": health}
        )
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/agents/{agent_id}/health/check")
async def validate_health(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Validate agent health."""
    try:
        is_healthy = await AgentHealthService.validate_health(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Health validation completed",
            data={"isHealthy": is_healthy}
        )
        
    except Exception as e:
        logger.error(f"Error validating health: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/health/check-expired-heartbeats")
async def check_expired_heartbeats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check for agents with expired heartbeats."""
    try:
        unhealthy_agents = await AgentHealthService.check_expired_heartbeats()
        
        return ApiResponse.success(
            status_code=200,
            message="Heartbeat check completed",
            data={"unhealthyAgents": unhealthy_agents, "count": len(unhealthy_agents)}
        )
        
    except Exception as e:
        logger.error(f"Error checking expired heartbeats: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/health/unhealthy-agents")
async def get_unhealthy_agents(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all unhealthy agents."""
    try:
        agents = await AgentHealthService.get_unhealthy_agents()
        
        return ApiResponse.success(
            status_code=200,
            message="Unhealthy agents retrieved successfully",
            data={"agents": agents, "count": len(agents)}
        )
        
    except Exception as e:
        logger.error(f"Error getting unhealthy agents: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
