"""
Recordings Routers.
Defines endpoints for retrieving call recordings list and pre-signed S3 download URLs.
"""

from fastapi import APIRouter, Depends, Request
from typing import Optional, Dict, Any, List

from api.utils.api_response import ApiResponse
from api.modules.recordings.services import RecordingsService
from api.middlewares.auth import get_current_user

router = APIRouter()
recordings_service = RecordingsService()

# --- Route Endpoints ---
# All recording endpoints require authentication

@router.get("")
async def get_all(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve list of recording logs."""
    recs = await recordings_service.get_all_recordings()
    return ApiResponse.success(
        status_code=200,
        message="Recordings retrieved successfully",
        data=recs
    )


@router.get("/{recording_id}/signed-url")
async def get_signed_url(recording_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch pre-signed S3 download URL."""
    try:
        url_payload = await recordings_service.generate_signed_url(recording_id)
        return ApiResponse.success(
            status_code=200,
            message="Signed URL generated successfully",
            data=url_payload
        )
    except KeyError:
        return ApiResponse.error(
            status_code=404,
            message="Recording not found",
            code="RECORDING_NOT_FOUND"
        )
