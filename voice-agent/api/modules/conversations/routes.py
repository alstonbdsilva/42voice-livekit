"""
Conversations Routers.
Exposes endpoints to retrieve call histories and log completed calls from the voice agent worker.
"""

from fastapi import APIRouter, Request, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.conversations.services import ConversationsService
from api.middlewares.auth import get_current_user

router = APIRouter()
conv_service = ConversationsService()

# --- Request Pydantic Schemas ---

class RecordingInfo(BaseModel):
    filename: str
    duration: int
    size: int
    s3_key: str


class TranscriptLine(BaseModel):
    speaker: str
    text: str


class TranscriptInfo(BaseModel):
    fullText: str
    lines: List[TranscriptLine]
    actionItems: List[str]


class RegisterCallRequest(BaseModel):
    agentName: str
    customerName: str
    customerContact: Optional[str] = None
    channel: str
    duration: int
    cost: float
    sentiment: str
    outcome: str
    summary: Optional[str] = None
    intent: Optional[str] = None
    leadScore: Optional[int] = 0
    sentimentScore: Optional[float] = 0.00
    humanHandoff: Optional[bool] = False
    escalationReason: Optional[str] = None
    userId: Optional[str] = None
    clientId: Optional[str] = None
    recording: Optional[RecordingInfo] = None
    transcript: Optional[TranscriptInfo] = None


# --- Route Endpoints ---

@router.post("/register")
async def register(req_body: RegisterCallRequest):
    """Public endpoint called by agent.py to register call details upon disconnection."""
    dto = req_body.dict()
    conv = await conv_service.register_call(dto)
    return ApiResponse.success(
        status_code=201,
        message="Conversation registered successfully",
        data=conv
    )


@router.get("")
async def get_all(
    agentId: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve list of conversation records."""
    convs = await conv_service.get_all_conversations(agent_id=agentId, limit=limit)
    return ApiResponse.success(
        status_code=200,
        message="Conversations retrieved successfully",
        data=convs
    )


@router.get("/{conversation_id}")
async def get_one(conversation_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch individual conversation details."""
    conv = await conv_service.get_conversation_by_id(conversation_id)
    if not conv:
        return ApiResponse.error(
            status_code=404,
            message="Conversation not found",
            code="CONVERSATION_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="Conversation retrieved successfully",
        data=conv
    )
