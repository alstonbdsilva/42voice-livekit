import logging
import uuid
import boto3
from fastapi import APIRouter, Depends, Request, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from config import get_settings
from api.utils.api_response import ApiResponse
from api.modules.agents.services import AgentService
from api.middlewares.auth import get_current_user

logger = logging.getLogger("voice-agent.api.agents.routes")

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
    voiceName: Optional[str] = None
    voiceGender: Optional[str] = None
    guardrails: Optional[Dict[str, Any]] = None
    customGuardrails: Optional[str] = None
    knowledgeItems: Optional[List[Dict[str, Any]]] = None


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    callType: str = Field(default="inbound")
    useCase: Optional[str] = ""
    activityDescription: Optional[str] = ""
    resellerIds: Optional[List[str]] = []
    clientIds: Optional[List[str]] = []
    voiceName: Optional[str] = "aria"
    voiceGender: Optional[str] = "female"
    guardrails: Optional[Dict[str, Any]] = {}
    customGuardrails: Optional[str] = ""
    knowledgeItems: Optional[List[Dict[str, Any]]] = []


# --- Route Endpoints ---
# All agent endpoints require authentication

@router.post("/upload")
async def upload_agent_file(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Upload a knowledge base file to S3 and return the S3 details.
    """
    settings = get_settings()
    try:
        # Get S3 client
        endpoint_url = f"https://s3.{settings.aws_region}.amazonaws.com" if settings.aws_region else None
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=endpoint_url
        )
        
        # Generate unique key in S3
        unique_id = uuid.uuid4().hex
        s3_key = f"knowledge_base/{unique_id}_{file.filename}"
        
        # Upload
        s3_client.upload_fileobj(
            file.file,
            settings.s3_bucket_name,
            s3_key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"}
        )
        
        s3_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        
        return ApiResponse.success(
            status_code=200,
            message="File uploaded successfully",
            data={
                "s3Key": s3_key,
                "s3Url": s3_url,
                "filename": file.filename,
                "contentType": file.content_type
            }
        )
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}")
        return ApiResponse.error(
            status_code=500,
            message=f"Failed to upload file to S3: {str(e)}",
            code="S3_UPLOAD_FAILED"
        )


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
