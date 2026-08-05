import logging
import uuid
import boto3
import httpx
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from config import get_settings
from api.utils.api_response import ApiResponse
from api.modules.agents.services import AgentService
from api.middlewares.auth import get_current_user

logger = logging.getLogger("voice-agent.api.agents.routes")

router = APIRouter()
agent_service = AgentService()

class PreviewVoiceRequest(BaseModel):
    voiceId: str
    text: Optional[str] = "Hello! I am your AI voice assistant. How can I help you today?"
    modelId: Optional[str] = "eleven_multilingual_v2"
    stability: Optional[float] = 0.5
    similarityBoost: Optional[float] = 0.75


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
    toolIds: Optional[List[str]] = None


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
    toolIds: Optional[List[str]] = []


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

    # Filter only configuration detail fields for update_agent_details
    detail_fields = {"name", "useCase", "activityDescription", "callType", "voiceName", "voiceGender", "guardrails", "customGuardrails", "knowledgeItems", "toolIds"}
    update_data = req_body.model_dump(exclude_unset=True)
    details_to_update = {k: v for k, v in update_data.items() if k in detail_fields}
    print("DEBUG DETAILS TO UPDATE:", details_to_update)

    if details_to_update:
        agent = await agent_service.update_agent_details(agent_id, details_to_update)

    if req_body.status:
        agent = await agent_service.update_agent_status(agent_id, req_body.status)

    if req_body.resellerIds is not None or req_body.clientIds is not None:
        agent = await agent_service.update_agent_assignments(agent_id, req_body.resellerIds, req_body.clientIds)

    return ApiResponse.success(
        status_code=200,
        message="Agent updated successfully",
        data=agent
    )


@router.get("/elevenlabs/voices")
async def get_elevenlabs_voices(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Fetch ElevenLabs voices dynamically if API key configured, combined with standard voices.
    """
    settings = get_settings()
    api_key = getattr(settings, "elevenlabs_api_key", None)
    
    voices_list = []
    has_api_key = bool(api_key and api_key != "YOUR_ELEVENLABS_API_KEY")
    if has_api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers: dict[str, str] = {"xi-api-key": str(api_key)}
                res = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers=headers
                )
                if res.status_code == 200:
                    data = res.json()
                    for v in data.get("voices", []):
                        labels = v.get("labels", {})
                        voices_list.append({
                            "voice_id": v.get("voice_id"),
                            "name": v.get("name"),
                            "gender": labels.get("gender", "female" if "female" in v.get("name", "").lower() else "male"),
                            "category": v.get("category", "premade"),
                            "accent": labels.get("accent", "american"),
                            "description": labels.get("description") or labels.get("use_case") or f"{labels.get('accent', 'American')} {labels.get('gender', 'voice')}",
                            "preview_url": v.get("preview_url"),
                            "is_custom": v.get("category") not in ["premade", "high_quality"]
                        })
                else:
                    logger.warning(f"ElevenLabs API return non-200 status {res.status_code}: {res.text}")
                    has_api_key = False
        except Exception as e:
            logger.warning(f"Could not fetch dynamic ElevenLabs voices: {e}")

    return ApiResponse.success(
        status_code=200,
        message="ElevenLabs voices retrieved successfully",
        data={"voices": voices_list, "hasApiKey": has_api_key}
    )


@router.post("/elevenlabs/preview")
async def preview_elevenlabs_voice(
    req: PreviewVoiceRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generate live audio TTS preview using ElevenLabs API.
    """
    settings = get_settings()
    api_key = getattr(settings, "elevenlabs_api_key", None)
    
    if not api_key or api_key == "YOUR_ELEVENLABS_API_KEY":
        return ApiResponse.error(
            status_code=400,
            message="ELEVENLABS_API_KEY is not configured on the backend server.",
            code="ELEVENLABS_KEY_MISSING"
        )
    
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{req.voiceId}"
        headers: dict[str, str] = {
            "xi-api-key": str(api_key),
            "Content-Type": "application/json"
        }
        payload = {
            "text": req.text or "Hello! I am your AI voice assistant. How can I help you today?",
            "model_id": req.modelId or "eleven_multilingual_v2",
            "voice_settings": {
                "stability": req.stability if req.stability is not None else 0.5,
                "similarity_boost": req.similarityBoost if req.similarityBoost is not None else 0.75
            }
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(f"ElevenLabs TTS preview error {resp.status_code}: {resp.text}")
                return ApiResponse.error(
                    status_code=resp.status_code,
                    message=f"ElevenLabs API error: {resp.text}",
                    code="ELEVENLABS_API_ERROR"
                )
            
            return Response(content=resp.content, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Failed to generate ElevenLabs voice preview: {e}")
        return ApiResponse.error(
            status_code=500,
            message=f"Failed to generate voice preview: {str(e)}",
            code="PREVIEW_GENERATION_FAILED"
        )

