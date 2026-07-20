"""
Transcripts Routers.
Defines endpoints for retrieving dialogue transcripts by conversation ID.
"""

from fastapi import APIRouter, Depends, Request
from typing import Optional, Dict, Any

from api.utils.api_response import ApiResponse
from api.modules.transcripts.services import TranscriptsService
from api.middlewares.auth import get_current_user

router = APIRouter()
transcripts_service = TranscriptsService()

# --- Route Endpoints ---
# All transcript endpoints require authentication

@router.get("/{conversation_id}")
async def get_one(conversation_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch transcript details corresponding to a conversation ID."""
    transcript = await transcripts_service.get_transcript_by_conversation_id(conversation_id)
    if not transcript:
        return ApiResponse.error(
            status_code=404,
            message="Transcript not found",
            code="TRANSCRIPT_NOT_FOUND"
        )
    return ApiResponse.success(
        status_code=200,
        message="Transcript retrieved successfully",
        data=transcript
    )
