import httpx
import logging
from typing import Optional, Dict, Any
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
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.calendly_client_id,
            "client_secret": settings.calendly_client_secret,
            "code": code,
            "redirect_uri": settings.calendly_redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post("https://auth.calendly.com/oauth/token", data=payload)
                if resp.status_code != 200:
                    logger.error(f"Calendly OAuth token exchange failed: {resp.text}")
                    return None
                return resp.json()
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
        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.calendly_client_id,
            "client_secret": settings.calendly_client_secret,
            "refresh_token": refresh_token
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post("https://auth.calendly.com/oauth/token", data=payload)
                if resp.status_code != 200:
                    logger.error(f"Calendly OAuth token refresh failed: {resp.text}")
                    return None
                return resp.json()
            except Exception as e:
                logger.error(f"Error in refresh_access_token: {e}")
                return None
        
    async def get_user_uri(self) -> Optional[str]:
        """Fetch the authenticated user's URI."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/users/me", headers=self.headers)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch Calendly user profile: {resp.text}")
                    return None
                data = resp.json()
                return data.get("resource", {}).get("uri")
            except Exception as e:
                logger.error(f"Calendly API get_user_uri error: {e}")
                return None

    async def get_event_types(self, user_uri: str) -> list:
        """Fetch all event types associated with the user."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/event_types",
                    params={"user": user_uri},
                    headers=self.headers
                )
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch Calendly event types: {resp.text}")
                    return []
                data = resp.json()
                return data.get("collection", [])
            except Exception as e:
                logger.error(f"Calendly API get_event_types error: {e}")
                return []

    async def resolve_event_type_uri(self, event_type_url_or_slug: str) -> Optional[str]:
        """Resolve a friendly event type URL or slug to a Calendly API URI."""
        user_uri = await self.get_user_uri()
        if not user_uri:
            return None
            
        event_types = await self.get_event_types(user_uri)
        clean_slug = event_type_url_or_slug.rstrip("/").split("/")[-1].lower()
        
        for et in event_types:
            if et.get("slug", "").lower() == clean_slug or et.get("scheduling_url", "").lower().endswith(clean_slug):
                return et.get("uri")
                
        # If no match, check if it's already a full URI
        if event_type_url_or_slug.startswith("https://api.calendly.com/event_types/"):
            return event_type_url_or_slug
            
        # Default fallback to first event type
        if event_types:
            return event_types[0].get("uri")
            
        return None

    async def create_invitee(self, event_type_uri: str, start_time: str, email: str, name: str, timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        """Create a scheduled event invitee (acts as scheduling the appointment)."""
        payload = {
            "event_type": event_type_uri,
            "start_time": start_time,
            "invitee": {
                "email": email,
                "name": name,
                "timezone": timezone
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/scheduled_events/invitees",
                    json=payload,
                    headers=self.headers
                )
                if resp.status_code != 201:
                    logger.error(f"Failed to create Calendly invitee: {resp.text}")
                    return None
                return resp.json()
            except Exception as e:
                logger.error(f"Calendly API create_invitee error: {e}")
                return None
