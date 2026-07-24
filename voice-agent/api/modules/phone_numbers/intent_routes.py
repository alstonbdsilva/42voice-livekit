"""
Intent Routes.
API endpoints for managing intent-to-capability mappings.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.intent_service import IntentService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.intent_routes")

router = APIRouter()


# --- Request Models ---

class MapIntentRequest(BaseModel):
    intentName: str = Field(..., min_length=1)
    capabilityId: str = Field(..., min_length=1)
    confidenceThreshold: float = Field(default=0.7, ge=0, le=1)


class UpdateIntentMappingRequest(BaseModel):
    confidenceThreshold: Optional[float] = Field(None, ge=0, le=1)


# --- Endpoints ---

@router.post("/intents/map")
async def map_intent(
    req_body: MapIntentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Map an intent to a capability."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        mapping = await IntentService.map_intent_to_capability(
            intent_name=req_body.intentName,
            capability_id=req_body.capabilityId,
            user_id=user_id,
            client_id=client_id,
            confidence_threshold=req_body.confidenceThreshold
        )
        
        if not mapping:
            return ApiResponse.error(
                status_code=400,
                message="Failed to map intent",
                code="MAPPING_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Intent mapped successfully",
            data=mapping
        )
        
    except Exception as e:
        logger.error(f"Error mapping intent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/intents/mappings")
async def list_intent_mappings(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all intent mappings."""
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
            mappings = await IntentService.get_client_intent_mappings(client_id)
        else:
            mappings = await IntentService.get_user_intent_mappings(user_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Intent mappings retrieved successfully",
            data={"mappings": mappings}
        )
        
    except Exception as e:
        logger.error(f"Error listing intent mappings: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/intents/{intent_name}/capability")
async def get_capability_for_intent(
    intent_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get capability for a detected intent."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        capability = await IntentService.get_capability_for_intent(
            intent_name,
            user_id,
            client_id
        )
        
        if not capability:
            return ApiResponse.error(
                status_code=404,
                message="No capability found for intent",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Capability retrieved successfully",
            data=capability
        )
        
    except Exception as e:
        logger.error(f"Error getting capability for intent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/capabilities/{capability_id}/intents")
async def get_intents_for_capability(
    capability_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all intents mapped to a capability."""
    try:
        intents = await IntentService.get_intents_for_capability(capability_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Intents retrieved successfully",
            data={"intents": intents}
        )
        
    except Exception as e:
        logger.error(f"Error getting intents for capability: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/intents/{intent_name}/capabilities/{capability_id}")
async def remove_intent_mapping(
    intent_name: str,
    capability_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove an intent-to-capability mapping."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await IntentService.remove_intent_mapping(
            intent_name,
            capability_id,
            user_id,
            client_id
        )
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to remove intent mapping",
                code="REMOVAL_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Intent mapping removed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error removing intent mapping: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
