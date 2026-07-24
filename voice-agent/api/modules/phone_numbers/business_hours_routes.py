"""
Business Hours Routes.
API endpoints for managing business hours profiles.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.phone_numbers.business_hours_service import BusinessHoursService

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.business_hours_routes")

router = APIRouter()


# --- Request Models ---

class CreateBusinessHoursRequest(BaseModel):
    name: str = Field(..., min_length=1)
    timezone: str = Field(..., min_length=1)
    monday: Optional[Dict] = None
    tuesday: Optional[Dict] = None
    wednesday: Optional[Dict] = None
    thursday: Optional[Dict] = None
    friday: Optional[Dict] = None
    saturday: Optional[Dict] = None
    sunday: Optional[Dict] = None
    holidayCalendar: Optional[Dict] = None


class UpdateBusinessHoursRequest(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    monday: Optional[Dict] = None
    tuesday: Optional[Dict] = None
    wednesday: Optional[Dict] = None
    thursday: Optional[Dict] = None
    friday: Optional[Dict] = None
    saturday: Optional[Dict] = None
    sunday: Optional[Dict] = None
    holidayCalendar: Optional[Dict] = None


# --- Endpoints ---

@router.post("/business-hours")
async def create_business_hours(
    req_body: CreateBusinessHoursRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new business hours profile."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        profile = await BusinessHoursService.create_profile(
            name=req_body.name,
            timezone=req_body.timezone,
            user_id=user_id,
            client_id=client_id,
            monday=req_body.monday,
            tuesday=req_body.tuesday,
            wednesday=req_body.wednesday,
            thursday=req_body.thursday,
            friday=req_body.friday,
            saturday=req_body.saturday,
            sunday=req_body.sunday,
            holiday_calendar=req_body.holidayCalendar
        )
        
        if not profile:
            return ApiResponse.error(
                status_code=400,
                message="Failed to create business hours profile",
                code="CREATION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Business hours profile created successfully",
            data=profile
        )
        
    except Exception as e:
        logger.error(f"Error creating business hours: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/business-hours")
async def list_business_hours(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all business hours profiles."""
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
            profiles = await BusinessHoursService.get_client_profiles(client_id)
        else:
            profiles = await BusinessHoursService.get_user_profiles(user_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Business hours profiles retrieved successfully",
            data={"profiles": profiles}
        )
        
    except Exception as e:
        logger.error(f"Error listing business hours: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/business-hours/{profile_id}")
async def get_business_hours(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get business hours profile details."""
    try:
        profile = await BusinessHoursService.get_profile(profile_id)
        
        if not profile:
            return ApiResponse.error(
                status_code=404,
                message="Business hours profile not found",
                code="NOT_FOUND"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Business hours profile retrieved successfully",
            data=profile
        )
        
    except Exception as e:
        logger.error(f"Error getting business hours: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.patch("/business-hours/{profile_id}")
async def update_business_hours(
    profile_id: str,
    req_body: UpdateBusinessHoursRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update business hours profile."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        updates = {}
        if req_body.name:
            updates["name"] = req_body.name
        if req_body.timezone:
            updates["timezone"] = req_body.timezone
        if req_body.monday is not None:
            updates["monday"] = req_body.monday
        if req_body.tuesday is not None:
            updates["tuesday"] = req_body.tuesday
        if req_body.wednesday is not None:
            updates["wednesday"] = req_body.wednesday
        if req_body.thursday is not None:
            updates["thursday"] = req_body.thursday
        if req_body.friday is not None:
            updates["friday"] = req_body.friday
        if req_body.saturday is not None:
            updates["saturday"] = req_body.saturday
        if req_body.sunday is not None:
            updates["sunday"] = req_body.sunday
        if req_body.holidayCalendar is not None:
            updates["holiday_calendar"] = req_body.holidayCalendar
        
        profile = await BusinessHoursService.update_profile(profile_id, **updates)
        
        if not profile:
            return ApiResponse.error(
                status_code=400,
                message="Failed to update business hours profile",
                code="UPDATE_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Business hours profile updated successfully",
            data=profile
        )
        
    except Exception as e:
        logger.error(f"Error updating business hours: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/business-hours/{profile_id}")
async def delete_business_hours(
    profile_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a business hours profile."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await BusinessHoursService.delete_profile(profile_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to delete business hours profile",
                code="DELETE_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Business hours profile deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting business hours: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
