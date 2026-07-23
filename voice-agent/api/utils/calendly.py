import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from config import get_settings

logger = logging.getLogger("voice-agent.api.utils.calendly")

class CalendlyClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.calendly.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    async def exchange_code_for_tokens(code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange OAuth authorization code for Access and Refresh tokens.
        POST https://auth.calendly.com/oauth/token
        """
        settings = get_settings()
        
        if not code:
            logger.error("Authorization code is empty")
            return None
        
        # Validate all required credentials are configured
        if not settings.calendly_client_id:
            logger.error("CALENDLY_CLIENT_ID is not configured")
            return None
        
        if not settings.calendly_client_secret:
            logger.error("CALENDLY_CLIENT_SECRET is not configured")
            return None
        
        if not settings.calendly_redirect_uri:
            logger.error("CALENDLY_REDIRECT_URI is not configured")
            return None
        
        # Ensure credentials are not mock values
        if "mock" in settings.calendly_client_id.lower():
            logger.error(f"CALENDLY_CLIENT_ID is a mock value: {settings.calendly_client_id}")
            return None
        
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.calendly_client_id,
            "client_secret": settings.calendly_client_secret,
            "code": code,
            "redirect_uri": settings.calendly_redirect_uri
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post("https://auth.calendly.com/oauth/token", data=payload)
                if resp.status_code != 200:
                    error_detail = resp.json().get("error_description", resp.text)
                    logger.error(f"Calendly OAuth token exchange failed ({resp.status_code}): {error_detail}")
                    return None
                data = resp.json()
                
                # Validate response contains required fields
                if "access_token" not in data:
                    logger.error("OAuth response missing access_token")
                    return None
                
                return data
            except httpx.TimeoutException:
                logger.error("Calendly OAuth token exchange timed out")
                return None
            except Exception as e:
                logger.error(f"Error in exchange_code_for_tokens: {e}")
                return None

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Exchange stored Refresh token for a new Access and Refresh token set.
        POST https://auth.calendly.com/oauth/token
        """
        settings = get_settings()
        
        if not refresh_token:
            logger.error("Refresh token is empty")
            return None
        
        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.calendly_client_id,
            "client_secret": settings.calendly_client_secret,
            "refresh_token": refresh_token
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post("https://auth.calendly.com/oauth/token", data=payload)
                if resp.status_code != 200:
                    error_detail = resp.json().get("error_description", resp.text)
                    logger.error(f"Calendly OAuth token refresh failed ({resp.status_code}): {error_detail}")
                    return None
                data = resp.json()
                
                # Validate response
                if "access_token" not in data:
                    logger.error("Token refresh response missing access_token")
                    return None
                
                return data
            except httpx.TimeoutException:
                logger.error("Calendly token refresh timed out")
                return None
            except Exception as e:
                logger.error(f"Error in refresh_access_token: {e}")
                return None
        
    async def get_user_uri(self) -> Optional[str]:
        """Fetch the authenticated user's URI."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/users/me", headers=self.headers)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch Calendly user profile ({resp.status_code}): {resp.text}")
                    return None
                data = resp.json()
                user_uri = data.get("resource", {}).get("uri")
                if not user_uri:
                    logger.error("User profile response missing URI")
                    return None
                return user_uri
            except httpx.TimeoutException:
                logger.error("Calendly get_user_uri request timed out")
                return None
            except Exception as e:
                logger.error(f"Calendly API get_user_uri error: {e}")
                return None

    async def get_event_types(self, user_uri: str) -> list:
        """Fetch all event types associated with the user."""
        if not user_uri:
            logger.error("user_uri is required for get_event_types")
            return []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/event_types",
                    params={"user": user_uri},
                    headers=self.headers
                )
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch Calendly event types ({resp.status_code}): {resp.text}")
                    return []
                data = resp.json()
                event_types = data.get("collection", [])
                if not event_types:
                    logger.warning("No event types found for user")
                return event_types
            except httpx.TimeoutException:
                logger.error("Calendly get_event_types request timed out")
                return []
            except Exception as e:
                logger.error(f"Calendly API get_event_types error: {e}")
                return []

    async def resolve_event_type_uri(self, event_type_url_or_slug: str) -> Optional[str]:
        """Resolve a friendly event type URL or slug to a Calendly API URI."""
        user_uri = await self.get_user_uri()
        if not user_uri:
            return None
        
        event_types = await self.get_event_types(user_uri)
        if not event_types:
            return None
        
        # Check if input is already a URI
        if event_type_url_or_slug.startswith("https://api.calendly.com"):
            return event_type_url_or_slug
        
        # Search by scheduling_url or slug
        for et in event_types:
            if event_type_url_or_slug in et.get("scheduling_url", ""):
                return et.get("uri")
            if event_type_url_or_slug == et.get("slug"):
                return et.get("uri")
        
        # If no match, return first event type URI as fallback
        if event_types:
            return event_types[0].get("uri")
        
        return None

    async def create_invitee(self, event_type_uri: str, start_time: str, email: str, name: str, timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        """Create a scheduled event invitee (acts as scheduling the appointment)."""
        if not event_type_uri or not start_time or not email or not name:
            logger.error("Missing required parameters for create_invitee")
            return None
        
        payload = {
            "event_type": event_type_uri,
            "start_time": start_time,
            "invitee": {
                "email": email,
                "name": name,
                "timezone": timezone
            }
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/scheduled_events/invitees",
                    json=payload,
                    headers=self.headers
                )
                if resp.status_code not in [200, 201]:
                    error_detail = resp.json().get("error_description", resp.text)
                    logger.error(f"Failed to create Calendly invitee ({resp.status_code}): {error_detail}")
                    return None
                return resp.json()
            except httpx.TimeoutException:
                logger.error("Calendly create_invitee request timed out")
                return None
            except Exception as e:
                logger.error(f"Calendly API create_invitee error: {e}")
                return None

    async def get_availability(self, event_type_uri: str, start_date: str, end_date: str, timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        """
        Fetch available time slots for an event type.
        GET /event_type_calendars/{event_type_id}/availability_schedules
        """
        if not event_type_uri or not start_date or not end_date:
            logger.error("Missing required parameters for get_availability")
            return None
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Extract event type ID from URI
                event_type_id = event_type_uri.split("/")[-1]
                resp = await client.get(
                    f"{self.base_url}/event_type_calendars/{event_type_id}/availability_schedules",
                    params={
                        "start_date": start_date,
                        "end_date": end_date,
                        "timezone": timezone
                    },
                    headers=self.headers
                )
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch Calendly availability ({resp.status_code}): {resp.text}")
                    return None
                return resp.json()
            except httpx.TimeoutException:
                logger.error("Calendly get_availability request timed out")
                return None
            except Exception as e:
                logger.error(f"Calendly API get_availability error: {e}")
                return None

    async def cancel_booking(self, invitee_uri: str, reason: str = "") -> bool:
        """
        Cancel an existing booking (invitee).
        DELETE /scheduled_events/invitees/{invitee_id}
        """
        if not invitee_uri:
            logger.error("invitee_uri is required for cancel_booking")
            return False
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Extract invitee ID from URI
                invitee_id = invitee_uri.split("/")[-1]
                payload = {}
                if reason:
                    payload["cancellation_reason"] = reason
                
                resp = await client.delete(
                    f"{self.base_url}/scheduled_events/invitees/{invitee_id}",
                    json=payload if payload else None,
                    headers=self.headers
                )
                if resp.status_code not in [200, 204]:
                    error_detail = resp.json().get("error_description", resp.text) if resp.text else "Unknown error"
                    logger.error(f"Failed to cancel Calendly booking ({resp.status_code}): {error_detail}")
                    return False
                logger.info(f"Successfully cancelled booking: {invitee_uri}")
                return True
            except httpx.TimeoutException:
                logger.error("Calendly cancel_booking request timed out")
                return False
            except Exception as e:
                logger.error(f"Calendly API cancel_booking error: {e}")
                return False

    async def reschedule_booking(self, invitee_uri: str, new_start_time: str, timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        """
        Reschedule an existing booking (invitee).
        PATCH /scheduled_events/invitees/{invitee_id}
        """
        if not invitee_uri or not new_start_time:
            logger.error("invitee_uri and new_start_time are required for reschedule_booking")
            return None
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Extract invitee ID from URI
                invitee_id = invitee_uri.split("/")[-1]
                payload = {
                    "start_time": new_start_time
                }
                
                resp = await client.patch(
                    f"{self.base_url}/scheduled_events/invitees/{invitee_id}",
                    json=payload,
                    headers=self.headers
                )
                if resp.status_code != 200:
                    error_detail = resp.json().get("error_description", resp.text) if resp.text else "Unknown error"
                    logger.error(f"Failed to reschedule Calendly booking ({resp.status_code}): {error_detail}")
                    return None
                logger.info(f"Successfully rescheduled booking: {invitee_uri}")
                return resp.json()
            except httpx.TimeoutException:
                logger.error("Calendly reschedule_booking request timed out")
                return None
            except Exception as e:
                logger.error(f"Calendly API reschedule_booking error: {e}")
                return None
