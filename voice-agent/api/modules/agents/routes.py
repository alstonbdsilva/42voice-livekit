"""
Agents Routers.
Defines endpoints for retrieving agent profiles, performance metrics, and updating status fields.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.agents.services import AgentService
from api.middlewares.auth import get_current_user

router = APIRouter()
agent_service = AgentService()

# --- Request Models ---

class UpdateAgentRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|paused|testing)$")
    name: Optional[str] = None
    useCase: Optional[str] = None
    activityDescription: Optional[str] = None
    callType: Optional[str] = None
    resellerIds: Optional[List[str]] = None
    clientIds: Optional[List[str]] = None


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    callType: str = Field(default="inbound")
    useCase: Optional[str] = ""
    activityDescription: Optional[str] = ""
    resellerIds: Optional[List[str]] = []
    clientIds: Optional[List[str]] = []


# --- Route Endpoints ---
# All agent endpoints require authentication

@router.post("")
async def create(req_body: CreateAgentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_context = {
        "role": current_user["role"],
        "id": current_user["id"],
        "client_id": current_user.get("client_id"),
        "reseller_id": current_user.get("reseller_id")
    }
    agent = await agent_service.create_agent(req_body.model_dump(), user_context)
    if not agent:
        return ApiResponse.error(
            status_code=500,
            message="Failed to create agent",
            code="AGENT_CREATION_FAILED"
        )
    return ApiResponse.success(
        status_code=201,
        message="Agent created successfully",
        data=agent
    )

@router.get("")
async def get_all(current_user: Dict[str, Any] = Depends(get_current_user)):
    # Build filter context from user claims
    filter_data = {
        "role": current_user["role"],
        "userId": current_user["id"],
        "clientId": current_user["client_id"],
        "resellerId": current_user["reseller_id"]
    }
    agents = await agent_service.get_all_agents(filter_data)
    return ApiResponse.success(
        status_code=200,
        message="Agents retrieved successfully",
        data=agents
    )


@router.get("/{agent_id}")
async def get_one(agent_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    agent = await agent_service.get_agent_by_id(agent_id)
    if not agent:
        return ApiResponse.error(
            status_code=404,
            message="Agent not found",
            code="AGENT_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="Agent retrieved successfully",
        data=agent
    )


@router.patch("/{agent_id}")
async def update(agent_id: str, req_body: UpdateAgentRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    agent = await agent_service.get_agent_by_id(agent_id)
    if not agent:
        return ApiResponse.error(
            status_code=404,
            message="Agent not found",
            code="AGENT_NOT_FOUND"
        )

    if req_body.name is not None or req_body.useCase is not None or req_body.activityDescription is not None or req_body.callType is not None:
        agent = await agent_service.update_agent_details(agent_id, req_body.model_dump(exclude_unset=True))

    if req_body.status:
        agent = await agent_service.update_agent_status(agent_id, req_body.status)

    if req_body.resellerIds is not None or req_body.clientIds is not None:
        agent = await agent_service.update_agent_assignments(agent_id, req_body.resellerIds, req_body.clientIds)

    return ApiResponse.success(
        status_code=200,
        message="Agent updated successfully",
        data=agent
    )
