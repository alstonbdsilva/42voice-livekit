"""
Calendar Routes.
API endpoints for calendar integration.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from api.utils.api_response import ApiResponse
from api.middlewares.auth import get_current_user
from api.modules.calendar.calendar_service import CalendarService

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_routes")

router = APIRouter()


# --- Request Models ---

class ConnectCalendarRequest(BaseModel):
    provider: str = Field(..., pattern="^(google|outlook|calendly)$")
    access_token: str = Field(..., min_length=1)
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class CreateCalendarConnectionRequest(BaseModel):
    oauth_connection_id: str = Field(..., min_length=1)
    provider: str = Field(..., pattern="^(google|outlook|calendly)$")
    calendar_id: str = Field(..., min_length=1)
    calendar_name: str = Field(..., min_length=1)
    timezone: Optional[str] = None
    is_primary: bool = Field(default=False)


class AssignCalendarToAgentRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    calendar_connection_id: str = Field(..., min_length=1)
    is_primary: bool = Field(default=False)
    booking_enabled: bool = Field(default=True)
    meeting_duration_minutes: int = Field(default=30, ge=1)
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)
    booking_window_days: int = Field(default=90, ge=1)
    minimum_notice_minutes: int = Field(default=0, ge=0)
    maximum_advance_booking_days: int = Field(default=365, ge=1)
    timezone: Optional[str] = None
    auto_confirm: bool = Field(default=True)
    auto_cancel: bool = Field(default=False)
    auto_reschedule: bool = Field(default=False)
    maximum_meetings_per_day: int = Field(default=10, ge=1)


class GetAvailableSlotsRequest(BaseModel):
    agent_calendar_connection_id: str = Field(..., min_length=1)
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)


class CreateBookingRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    agent_calendar_connection_id: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    customer_email: str = Field(..., min_length=1)
    customer_phone: Optional[str] = None
    start_time: datetime = Field(...)
    end_time: datetime = Field(...)
    timezone: str = Field(..., min_length=1)


# --- Endpoints ---

@router.post("/calendars/oauth/connect")
async def connect_calendar(
    req_body: ConnectCalendarRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Connect calendar provider."""
    try:
        user_id = current_user.get("id")
        client_id = current_user.get("client_id")
        
        if not user_id or not client_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        connection = await CalendarService.create_oauth_connection(
            provider=req_body.provider,
            tenant_id=client_id,
            user_id=user_id,
            access_token=req_body.access_token,
            refresh_token=req_body.refresh_token,
            expires_at=req_body.expires_at
        )
        
        if not connection:
            return ApiResponse.error(
                status_code=400,
                message="Failed to connect calendar",
                code="CONNECTION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Calendar connected successfully",
            data=connection
        )
        
    except Exception as e:
        logger.error(f"Error connecting calendar: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calendars/oauth/disconnect/{oauth_connection_id}")
async def disconnect_calendar(
    oauth_connection_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Disconnect calendar provider."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await CalendarService.disconnect_oauth(oauth_connection_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to disconnect calendar",
                code="DISCONNECTION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Calendar disconnected successfully"
        )
        
    except Exception as e:
        logger.error(f"Error disconnecting calendar: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calendars/connections")
async def create_calendar_connection(
    req_body: CreateCalendarConnectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create calendar connection."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        connection = await CalendarService.create_calendar_connection(
            oauth_connection_id=req_body.oauth_connection_id,
            provider=req_body.provider,
            calendar_id=req_body.calendar_id,
            calendar_name=req_body.calendar_name,
            timezone=req_body.timezone,
            is_primary=req_body.is_primary
        )
        
        if not connection:
            return ApiResponse.error(
                status_code=400,
                message="Failed to create calendar connection",
                code="CREATION_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Calendar connection created successfully",
            data=connection
        )
        
    except Exception as e:
        logger.error(f"Error creating calendar connection: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/agents/{agent_id}/calendars")
async def assign_calendar_to_agent(
    agent_id: str,
    req_body: AssignCalendarToAgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Assign calendar to agent."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        assignment = await CalendarService.assign_calendar_to_agent(
            agent_id=agent_id,
            calendar_connection_id=req_body.calendar_connection_id,
            is_primary=req_body.is_primary,
            booking_enabled=req_body.booking_enabled,
            meeting_duration_minutes=req_body.meeting_duration_minutes,
            buffer_before_minutes=req_body.buffer_before_minutes,
            buffer_after_minutes=req_body.buffer_after_minutes,
            booking_window_days=req_body.booking_window_days,
            minimum_notice_minutes=req_body.minimum_notice_minutes,
            maximum_advance_booking_days=req_body.maximum_advance_booking_days,
            timezone=req_body.timezone,
            auto_confirm=req_body.auto_confirm,
            auto_cancel=req_body.auto_cancel,
            auto_reschedule=req_body.auto_reschedule,
            maximum_meetings_per_day=req_body.maximum_meetings_per_day
        )
        
        if not assignment:
            return ApiResponse.error(
                status_code=400,
                message="Failed to assign calendar to agent",
                code="ASSIGNMENT_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Calendar assigned to agent successfully",
            data=assignment
        )
        
    except Exception as e:
        logger.error(f"Error assigning calendar to agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.get("/agents/{agent_id}/calendars")
async def get_agent_calendars(
    agent_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get calendars for agent."""
    try:
        calendars = await CalendarService.get_agent_calendars(agent_id)
        
        return ApiResponse.success(
            status_code=200,
            message="Agent calendars retrieved successfully",
            data={"calendars": calendars}
        )
        
    except Exception as e:
        logger.error(f"Error getting agent calendars: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.delete("/agents/{agent_id}/calendars/{calendar_connection_id}")
async def remove_calendar_from_agent(
    agent_id: str,
    calendar_connection_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove calendar from agent."""
    try:
        user_id = current_user.get("id")
        
        if not user_id:
            return ApiResponse.error(
                status_code=401,
                message="Unauthorized",
                code="UNAUTHORIZED"
            )
        
        success = await CalendarService.remove_calendar_from_agent(agent_id, calendar_connection_id)
        
        if not success:
            return ApiResponse.error(
                status_code=400,
                message="Failed to remove calendar from agent",
                code="REMOVAL_FAILED"
            )
        
        return ApiResponse.success(
            status_code=200,
            message="Calendar removed from agent successfully"
        )
        
    except Exception as e:
        logger.error(f"Error removing calendar from agent: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calendars/available-slots")
async def get_available_slots(
    req_body: GetAvailableSlotsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get available slots for agent calendar."""
    try:
        slots = await CalendarService.get_available_slots(
            req_body.agent_calendar_connection_id,
            req_body.start_date,
            req_body.end_date
        )
        
        return ApiResponse.success(
            status_code=200,
            message="Available slots retrieved successfully",
            data={"slots": slots}
        )
        
    except Exception as e:
        logger.error(f"Error getting available slots: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )


@router.post("/calendars/bookings")
async def create_booking(
    req_body: CreateBookingRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create calendar booking."""
    try:
        booking = await CalendarService.create_booking(
            session_id=req_body.session_id,
            agent_calendar_connection_id=req_body.agent_calendar_connection_id,
            customer_name=req_body.customer_name,
            customer_email=req_body.customer_email,
            customer_phone=req_body.customer_phone,
            start_time=req_body.start_time,
            end_time=req_body.end_time,
            timezone=req_body.timezone
        )
        
        if not booking:
            return ApiResponse.error(
                status_code=400,
                message="Failed to create booking",
                code="BOOKING_FAILED"
            )
        
        return ApiResponse.success(
            status_code=201,
            message="Booking created successfully",
            data=booking
        )
        
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        return ApiResponse.error(
            status_code=500,
            message="Internal server error",
            code="INTERNAL_ERROR"
        )
