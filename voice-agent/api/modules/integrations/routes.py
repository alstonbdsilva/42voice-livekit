import uuid
import jwt
import datetime
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from api import database
from api.middlewares.auth import get_current_user
from api.utils.api_response import ApiResponse
from api.utils.encryption import token_encryptor
from api.utils.calendly import CalendlyClient
from config import get_settings
import httpx
import json

logger = logging.getLogger("voice-agent.api.modules.integrations")
router = APIRouter()

# Service layer token manager
class CalendlyAuthService:
    @staticmethod
    def generate_state_token(user_id: str, client_id: Optional[str]) -> str:
        """Create a signed JWT state token for OAuth CSRF protection."""
        settings = get_settings()
        payload = {
            "user_id": user_id,
            "client_id": client_id,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
        }
        return jwt.encode(payload, settings.jwt_access_secret, algorithm="HS256")

    @staticmethod
    def verify_state_token(state: str) -> Dict[str, Any]:
        """Decode and verify the state token."""
        settings = get_settings()
        try:
            return jwt.decode(state, settings.jwt_access_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.error("OAuth state token has expired")
            raise HTTPException(status_code=400, detail="State token expired")
        except jwt.InvalidTokenError:
            logger.error("OAuth state token is invalid")
            raise HTTPException(status_code=400, detail="State token invalid")

    @staticmethod
    async def get_active_token(client_id: Optional[str], user_id: str) -> Optional[str]:
        """
        Retrieves a decrypted, validated access token.
        Triggers token refresh automatically if needed.
        """
        if client_id:
            rows = await database.query(
                "SELECT access_token, refresh_token, updated_at FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
                [uuid.UUID(client_id)]
            )
        else:
            rows = await database.query(
                "SELECT access_token, refresh_token, updated_at FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
                [uuid.UUID(user_id)]
            )

        if not rows:
            return None

        integration = rows[0]
        # Decrypt tokens
        encrypted_access = integration["access_token"]
        encrypted_refresh = integration["refresh_token"]
        updated_at = integration["updated_at"]

        try:
            access_token = token_encryptor.decrypt(encrypted_access)
        except Exception:
            logger.error("Failed to decrypt access token")
            return None

        # Calendly OAuth access tokens expire in 2 hours (7200 seconds)
        # Check if token is nearing expiration (e.g., older than 1 hour 45 minutes)
        age = datetime.datetime.now(datetime.timezone.utc) - updated_at.astimezone(datetime.timezone.utc)
        if age > datetime.timedelta(hours=1, minutes=45) and encrypted_refresh:
            try:
                refresh_token = token_encryptor.decrypt(encrypted_refresh)
                logger.info("Calendly access token expired. Attempting refresh...")
                new_tokens = await CalendlyClient.refresh_access_token(refresh_token)
                
                if new_tokens:
                    new_access = token_encryptor.encrypt(new_tokens["access_token"])
                    new_refresh = token_encryptor.encrypt(new_tokens["refresh_token"])
                    
                    if client_id:
                        await database.query(
                            "UPDATE calendar_integrations SET access_token = $1, refresh_token = $2, updated_at = CURRENT_TIMESTAMP WHERE client_id = $3 AND provider = 'calendly'",
                            [new_access, new_refresh, uuid.UUID(client_id)]
                        )
                    else:
                        await database.query(
                            "UPDATE calendar_integrations SET access_token = $1, refresh_token = $2, updated_at = CURRENT_TIMESTAMP WHERE user_id = $3 AND provider = 'calendly'",
                            [new_access, new_refresh, uuid.UUID(user_id)]
                        )
                    return new_tokens["access_token"]
            except Exception as e:
                logger.error(f"Failed to auto-refresh Calendly credentials: {e}")
                
        return access_token


class GoogleAuthService:
    @staticmethod
    def generate_state_token(user_id: str, client_id: Optional[str], provider: str = "google") -> str:
        """Create a signed JWT state token for OAuth CSRF protection."""
        settings = get_settings()
        payload = {
            "user_id": user_id,
            "client_id": client_id,
            "provider": provider,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
        }
        return jwt.encode(payload, settings.jwt_access_secret, algorithm="HS256")

    @staticmethod
    def verify_state_token(state: str) -> Dict[str, Any]:
        """Decode and verify the state token."""
        settings = get_settings()
        try:
            return jwt.decode(state, settings.jwt_access_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.error("OAuth state token has expired")
            raise HTTPException(status_code=400, detail="State token expired")
        except jwt.InvalidTokenError:
            logger.error("OAuth state token is invalid")
            raise HTTPException(status_code=400, detail="State token invalid")

    @staticmethod
    async def get_active_token(client_id: Optional[str], user_id: str, provider: str) -> Optional[str]:
        """Retrieves a decrypted, validated access token."""
        if client_id:
            rows = await database.query(
                "SELECT access_token, refresh_token, updated_at FROM calendar_integrations WHERE client_id = $1 AND provider = $2",
                [uuid.UUID(client_id), provider]
            )
        else:
            rows = await database.query(
                "SELECT access_token, refresh_token, updated_at FROM calendar_integrations WHERE user_id = $1 AND provider = $2",
                [uuid.UUID(user_id), provider]
            )

        if not rows:
            return None

        integration = rows[0]
        encrypted_access = integration["access_token"]
        encrypted_refresh = integration["refresh_token"]
        updated_at = integration["updated_at"]

        try:
            access_token = token_encryptor.decrypt(encrypted_access)
        except Exception:
            logger.error(f"Failed to decrypt {provider} access token")
            return None

        # Google OAuth access tokens expire in 1 hour (3600 seconds)
        age = datetime.datetime.now(datetime.timezone.utc) - updated_at.astimezone(datetime.timezone.utc)
        if age > datetime.timedelta(minutes=50) and encrypted_refresh:
            try:
                refresh_token = token_encryptor.decrypt(encrypted_refresh)
                logger.info(f"{provider} access token expired. Attempting refresh...")
                
                settings = get_settings()
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "client_id": settings.google_calendar_client_id,
                            "client_secret": settings.google_calendar_client_secret,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token"
                        }
                    )
                
                if response.status_code == 200:
                    tokens = response.json()
                    new_access = token_encryptor.encrypt(tokens["access_token"])
                    new_refresh = token_encryptor.encrypt(tokens.get("refresh_token", refresh_token))
                    
                    if client_id:
                        await database.query(
                            "UPDATE calendar_integrations SET access_token = $1, refresh_token = $2, updated_at = CURRENT_TIMESTAMP WHERE client_id = $3 AND provider = $4",
                            [new_access, new_refresh, uuid.UUID(client_id), provider]
                        )
                    else:
                        await database.query(
                            "UPDATE calendar_integrations SET access_token = $1, refresh_token = $2, updated_at = CURRENT_TIMESTAMP WHERE user_id = $3 AND provider = $4",
                            [new_access, new_refresh, uuid.UUID(user_id), provider]
                        )
                    return tokens["access_token"]
            except Exception as e:
                logger.error(f"Failed to auto-refresh {provider} credentials: {e}")
                
        return access_token


# --- API Routes ---

@router.get("/calendly/auth")
async def initiate_calendly_auth(user_id: str, client_id: Optional[str] = None):
    """
    Initiates Calendly OAuth flow.
    Generates a secure state parameter and redirects to Calendly authorization page.
    """
    settings = get_settings()
    
    # Validate all required Calendly credentials are configured
    if not settings.calendly_client_id:
        logger.error("CALENDLY_CLIENT_ID is not configured in environment variables")
        raise HTTPException(status_code=500, detail="Calendly OAuth is not configured: missing CALENDLY_CLIENT_ID")
    
    if not settings.calendly_client_secret:
        logger.error("CALENDLY_CLIENT_SECRET is not configured in environment variables")
        raise HTTPException(status_code=500, detail="Calendly OAuth is not configured: missing CALENDLY_CLIENT_SECRET")
    
    if not settings.calendly_redirect_uri:
        logger.error("CALENDLY_REDIRECT_URI is not configured in environment variables")
        raise HTTPException(status_code=500, detail="Calendly OAuth is not configured: missing CALENDLY_REDIRECT_URI")
    
    if not settings.calendly_encryption_key:
        logger.error("CALENDLY_ENCRYPTION_KEY is not configured in environment variables")
        raise HTTPException(status_code=500, detail="Calendly OAuth is not configured: missing CALENDLY_ENCRYPTION_KEY")
    
    # Ensure client_id is not a mock value
    if "mock" in settings.calendly_client_id.lower():
        logger.error(f"CALENDLY_CLIENT_ID appears to be a mock value: {settings.calendly_client_id}")
        raise HTTPException(status_code=500, detail="Calendly OAuth is not properly configured: CALENDLY_CLIENT_ID is a mock value")
    
    state = CalendlyAuthService.generate_state_token(user_id, client_id)
    auth_url = (
        f"https://auth.calendly.com/oauth/authorize"
        f"?client_id={settings.calendly_client_id}"
        f"&redirect_uri={settings.calendly_redirect_uri}"
        f"&response_type=code"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@router.get("/calendly/callback")
async def calendly_oauth_callback(code: str, state: str):
    """
    Callback endpoint handles code-token exchange and registers integration.
    Renders script to postMessage and close the popup window.
    """
    state_payload = CalendlyAuthService.verify_state_token(state)
    user_id = state_payload["user_id"]
    client_id = state_payload.get("client_id")
    
    # Exchange code for tokens
    tokens = await CalendlyClient.exchange_code_for_tokens(code)
    if not tokens:
        return HTMLResponse(
            status_code=400,
            content=get_error_html("Failed to exchange authorization code for Calendly access tokens.")
        )
        
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    
    # Retrieve Calendly User Info to verify and fetch booking URL slug
    client = CalendlyClient(access_token)
    user_uri = await client.get_user_uri()
    
    if not user_uri:
        return HTMLResponse(
            status_code=400,
            content=get_error_html("Failed to verify user profile with Calendly API.")
        )
        
    # Get active scheduling URL (first event type scheduling URL as slug)
    event_types = await client.get_event_types(user_uri)
    event_type_url = ""
    if event_types:
        event_type_url = event_types[0].get("scheduling_url", "")
        
    # Encrypt tokens securely
    encrypted_access = token_encryptor.encrypt(access_token)
    encrypted_refresh = token_encryptor.encrypt(refresh_token)
    
    client_uuid = uuid.UUID(client_id) if client_id else None
    user_uuid = uuid.UUID(user_id)
    
    # Insert or update configuration in PostgreSQL
    if client_uuid:
        await database.query(
            """INSERT INTO calendar_integrations (client_id, provider, access_token, refresh_token, event_type_url, is_active)
               VALUES ($1, 'calendly', $2, $3, $4, TRUE)
               ON CONFLICT (client_id, provider) 
               DO UPDATE SET access_token = $2, refresh_token = $3, event_type_url = $4, is_active = TRUE, updated_at = CURRENT_TIMESTAMP""",
            [client_uuid, encrypted_access, encrypted_refresh, event_type_url]
        )
    else:
        await database.query(
            """INSERT INTO calendar_integrations (user_id, provider, access_token, refresh_token, event_type_url, is_active)
               VALUES ($1, 'calendly', $2, $3, $4, TRUE)
               ON CONFLICT (user_id, provider) 
               DO UPDATE SET access_token = $2, refresh_token = $3, event_type_url = $4, is_active = TRUE, updated_at = CURRENT_TIMESTAMP""",
            [user_uuid, encrypted_access, encrypted_refresh, event_type_url]
        )
        
    # HTML response page communicating success back to the frontend window
    return HTMLResponse(content=f"""
        <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fafafa;">
            <div style="text-align: center; border: 1px solid #e4e4e7; background: white; padding: 2.5rem; border-radius: 16px; max-width: 380px;">
              <div style="width: 48px; height: 48px; border-radius: 50%; background: #ecfdf5; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                <svg style="width: 24px; height: 24px; color: #10b981;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 style="color: #18181b; margin: 0 0 0.5rem 0; font-size: 1.25rem; font-weight: 700;">Integration Successful!</h2>
              <p style="color: #71717a; margin: 0; font-size: 0.875rem; line-height: 1.5;">You have successfully connected Calendly. This window will close automatically.</p>
              <script>
                window.opener.postMessage({{ type: "CALENDLY_CONNECTED" }}, "*");
                setTimeout(() => window.close(), 1500);
              </script>
            </div>
          </body>
        </html>
    """)


@router.get("/calendly")
async def get_calendly_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetches connection status and masks tokens for safety."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Try fetching a fresh validated token (which auto-refreshes if needed)
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    
    if not access_token:
        return ApiResponse.success(status_code=200, message="No Calendly integration found", data={"connected": False})
        
    # Get active config details
    if client_id:
        rows = await database.query(
            "SELECT event_type_url, is_active FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
            [uuid.UUID(client_id)]
        )
    else:
        rows = await database.query(
            "SELECT event_type_url, is_active FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
            [uuid.UUID(user_id)]
        )
        
    integration = rows[0]
    masked_token = access_token[:4] + "..." + access_token[-4:] if len(access_token) > 8 else "Connected"
    
    return ApiResponse.success(
        status_code=200,
        message="Calendly integration retrieved",
        data={
            "connected": True,
            "eventTypeUrl": integration["event_type_url"],
            "isActive": integration["is_active"],
            "tokenMask": masked_token
        }
    )


@router.get("/calendly/event-types")
async def get_calendly_event_types(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch all event types for the connected Calendly account."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    client = CalendlyClient(access_token)
    user_uri = await client.get_user_uri()
    
    if not user_uri:
        raise HTTPException(status_code=400, detail="Failed to fetch user profile")
    
    event_types = await client.get_event_types(user_uri)
    
    return ApiResponse.success(
        status_code=200,
        message="Event types retrieved",
        data={"eventTypes": event_types}
    )


@router.get("/calendly/availability")
async def get_calendly_availability(
    event_type_uri: str,
    start_date: str,
    end_date: str,
    timezone: str = "UTC",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Fetch available time slots for a specific event type."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    client = CalendlyClient(access_token)
    availability = await client.get_availability(event_type_uri, start_date, end_date, timezone)
    
    if not availability:
        raise HTTPException(status_code=400, detail="Failed to fetch availability")
    
    return ApiResponse.success(
        status_code=200,
        message="Availability retrieved",
        data=availability
    )


class BookingRequest(BaseModel):
    event_type_uri: str
    start_time: str
    invitee_email: str
    invitee_name: str
    timezone: str = "UTC"


@router.post("/calendly/book")
async def create_calendly_booking(
    request: BookingRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new booking in Calendly."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    client = CalendlyClient(access_token)
    invitee_response = await client.create_invitee(
        request.event_type_uri,
        request.start_time,
        request.invitee_email,
        request.invitee_name,
        request.timezone
    )
    
    if not invitee_response:
        raise HTTPException(status_code=400, detail="Failed to create booking")
    
    invitee_data = invitee_response.get("resource", {})
    invitee_uri = invitee_data.get("uri")
    
    # Get integration ID for storing booking
    if client_id:
        integration_rows = await database.query(
            "SELECT id FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
            [uuid.UUID(client_id)]
        )
    else:
        integration_rows = await database.query(
            "SELECT id FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
            [uuid.UUID(user_id)]
        )
    
    if integration_rows:
        integration_id = integration_rows[0]["id"]
        
        # Store booking in database
        await database.query(
            """INSERT INTO calendar_bookings 
               (integration_id, invitee_uri, event_type_uri, invitee_email, invitee_name, start_time, timezone, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')""",
            [
                integration_id,
                invitee_uri,
                request.event_type_uri,
                request.invitee_email,
                request.invitee_name,
                request.start_time,
                request.timezone
            ]
        )
    
    return ApiResponse.success(
        status_code=201,
        message="Booking created successfully",
        data={
            "inviteeUri": invitee_uri,
            "inviteeData": invitee_data
        }
    )


class RescheduleRequest(BaseModel):
    invitee_uri: str
    new_start_time: str
    timezone: str = "UTC"


@router.patch("/calendly/reschedule")
async def reschedule_calendly_booking(
    request: RescheduleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reschedule an existing booking."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    client = CalendlyClient(access_token)
    result = await client.reschedule_booking(request.invitee_uri, request.new_start_time, request.timezone)
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to reschedule booking")
    
    # Update booking in database
    await database.query(
        """UPDATE calendar_bookings SET start_time = $1, updated_at = CURRENT_TIMESTAMP 
           WHERE invitee_uri = $2""",
        [request.new_start_time, request.invitee_uri]
    )
    
    return ApiResponse.success(
        status_code=200,
        message="Booking rescheduled successfully",
        data=result.get("resource", {})
    )


class CancelRequest(BaseModel):
    invitee_uri: str
    reason: str = ""


@router.delete("/calendly/cancel")
async def cancel_calendly_booking(
    request: CancelRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel an existing booking."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await CalendlyAuthService.get_active_token(client_id, user_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    client = CalendlyClient(access_token)
    success = await client.cancel_booking(request.invitee_uri, request.reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel booking")
    
    # Update booking status in database
    await database.query(
        """UPDATE calendar_bookings SET status = 'cancelled', cancellation_reason = $1, updated_at = CURRENT_TIMESTAMP 
           WHERE invitee_uri = $2""",
        [request.reason, request.invitee_uri]
    )
    
    return ApiResponse.success(
        status_code=200,
        message="Booking cancelled successfully",
        data={"cancelled": True}
    )


@router.post("/calendly/webhook")
async def handle_calendly_webhook(request: Request):
    """
    Handle incoming Calendly webhooks for invitee events.
    Supports: invitee.created, invitee.canceled, invitee.rescheduled
    Handles duplicate webhook delivery safely using idempotency.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_type = payload.get("event")
    data = payload.get("data", {})
    webhook_id = payload.get("id")  # Calendly provides unique webhook ID
    
    if not event_type or not data:
        raise HTTPException(status_code=400, detail="Missing event or data")
    
    try:
        # Check if webhook was already processed (idempotency)
        if webhook_id:
            existing_webhook = await database.query(
                "SELECT id FROM calendar_webhooks WHERE webhook_id = $1",
                [webhook_id]
            )
            if existing_webhook:
                logger.info(f"Webhook {webhook_id} already processed, skipping")
                return ApiResponse.success(
                    status_code=200,
                    message="Webhook already processed"
                )
        
        # Handle different webhook event types
        if event_type == "invitee.created":
            invitee_uri = data.get("uri")
            if invitee_uri:
                # Check if booking already exists
                existing = await database.query(
                    "SELECT id FROM calendar_bookings WHERE invitee_uri = $1",
                    [invitee_uri]
                )
                if not existing:
                    # Insert new booking from webhook
                    await database.query(
                        """INSERT INTO calendar_bookings 
                           (integration_id, invitee_uri, event_type_uri, invitee_email, invitee_name, start_time, timezone, status)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')""",
                        [
                            None,
                            invitee_uri,
                            data.get("event_type", {}).get("uri"),
                            data.get("email"),
                            data.get("name"),
                            data.get("start_time"),
                            data.get("timezone", "UTC")
                        ]
                    )
                    logger.info(f"Created booking from webhook: {invitee_uri}")
        
        elif event_type == "invitee.canceled":
            invitee_uri = data.get("uri")
            if invitee_uri:
                result = await database.query(
                    """UPDATE calendar_bookings SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP 
                       WHERE invitee_uri = $1""",
                    [invitee_uri]
                )
                logger.info(f"Cancelled booking from webhook: {invitee_uri}")
        
        elif event_type == "invitee.rescheduled":
            invitee_uri = data.get("uri")
            if invitee_uri:
                await database.query(
                    """UPDATE calendar_bookings SET start_time = $1, updated_at = CURRENT_TIMESTAMP 
                       WHERE invitee_uri = $2""",
                    [data.get("start_time"), invitee_uri]
                )
                logger.info(f"Rescheduled booking from webhook: {invitee_uri}")
        
        # Store webhook for audit trail and idempotency
        await database.query(
            """INSERT INTO calendar_webhooks (integration_id, webhook_id, event_type, payload, processed)
               VALUES ($1, $2, $3, $4, TRUE)""",
            [None, webhook_id, event_type, payload]
        )
        
        return ApiResponse.success(
            status_code=200,
            message="Webhook processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.delete("/calendly")
async def disconnect_calendly(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Disconnects the Calendly integration by removing the database record."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if client_id:
        await database.query(
            "DELETE FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
            [uuid.UUID(client_id)]
        )
    else:
        await database.query(
            "DELETE FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
            [uuid.UUID(user_id)]
        )
        
    return ApiResponse.success(
        status_code=200,
        message="Calendly integration disconnected successfully",
        data={"connected": False}
    )


@router.get("/google/auth")
async def initiate_google_auth(user_id: str, client_id: Optional[str] = None):
    """Initiates Google Calendar OAuth flow."""
    settings = get_settings()
    
    if not settings.google_calendar_client_id or not settings.google_calendar_redirect_uri:
        raise HTTPException(status_code=500, detail="Google Calendar OAuth not configured")
    
    state = GoogleAuthService.generate_state_token(user_id, client_id, "google")
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_calendar_client_id}"
        f"&redirect_uri={settings.google_calendar_redirect_uri}"
        f"&response_type=code"
        f"&scope=https://www.googleapis.com/auth/calendar"
        f"&access_type=offline"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str):
    """Callback endpoint handles code-token exchange."""
    state_payload = GoogleAuthService.verify_state_token(state)
    user_id = state_payload["user_id"]
    client_id = state_payload.get("client_id")
    
    settings = get_settings()
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_calendar_redirect_uri
            }
        )
    
    if response.status_code != 200:
        return HTMLResponse(
            status_code=400,
            content=get_error_html("Failed to exchange authorization code for tokens.")
        )
    
    tokens = response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    
    # Encrypt tokens
    encrypted_access = token_encryptor.encrypt(access_token)
    encrypted_refresh = token_encryptor.encrypt(refresh_token)
    
    client_uuid = uuid.UUID(client_id) if client_id else None
    user_uuid = uuid.UUID(user_id)
    
    # Store in database
    if client_uuid:
        await database.query(
            """INSERT INTO calendar_integrations (client_id, provider, access_token, refresh_token, event_type_url, is_active)
               VALUES ($1, 'google', $2, $3, 'primary', TRUE)
               ON CONFLICT (client_id, provider) 
               DO UPDATE SET access_token = $2, refresh_token = $3, is_active = TRUE, updated_at = CURRENT_TIMESTAMP""",
            [client_uuid, encrypted_access, encrypted_refresh]
        )
    else:
        await database.query(
            """INSERT INTO calendar_integrations (user_id, provider, access_token, refresh_token, event_type_url, is_active)
               VALUES ($1, 'google', $2, $3, 'primary', TRUE)
               ON CONFLICT (user_id, provider) 
               DO UPDATE SET access_token = $2, refresh_token = $3, is_active = TRUE, updated_at = CURRENT_TIMESTAMP""",
            [user_uuid, encrypted_access, encrypted_refresh]
        )
    
    return HTMLResponse(content="""
        <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fafafa;">
            <div style="text-align: center; border: 1px solid #e4e4e7; background: white; padding: 2.5rem; border-radius: 16px; max-width: 380px;">
              <div style="width: 48px; height: 48px; border-radius: 50%; background: #ecfdf5; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                <svg style="width: 24px; height: 24px; color: #10b981;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 style="color: #18181b; margin: 0 0 0.5rem 0; font-size: 1.25rem; font-weight: 700;">Google Calendar Connected!</h2>
              <p style="color: #71717a; margin: 0; font-size: 0.875rem; line-height: 1.5;">You have successfully connected Google Calendar. This window will close automatically.</p>
              <script>
                window.opener.postMessage({ type: "GOOGLE_CALENDAR_CONNECTED" }, "*");
                setTimeout(() => window.close(), 1500);
              </script>
            </div>
          </body>
        </html>
    """)


@router.get("/google/status")
async def get_google_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetches Google Calendar connection status."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    access_token = await GoogleAuthService.get_active_token(client_id, user_id, "google")
    if not access_token:
        return ApiResponse.success(
            status_code=200,
            message="Google Calendar not connected",
            data={"connected": False}
        )
    
    return ApiResponse.success(
        status_code=200,
        message="Google Calendar connected",
        data={"connected": True}
    )


@router.delete("/google")
async def disconnect_google(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Disconnects Google Calendar integration."""
    client_id = current_user.get("client_id")
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    if client_id:
        await database.query(
            "DELETE FROM calendar_integrations WHERE client_id = $1 AND provider = 'google'",
            [uuid.UUID(client_id)]
        )
    else:
        await database.query(
            "DELETE FROM calendar_integrations WHERE user_id = $1 AND provider = 'google'",
            [uuid.UUID(user_id)]
        )
    
    return ApiResponse.success(
        status_code=200,
        message="Google Calendar disconnected successfully"
    )


@router.get("/calendars")
async def list_calendars(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List all connected calendar integrations."""
    user_id = current_user.get("id")
    client_id = current_user.get("client_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    calendars = []
    
    try:
        # Fetch Calendly
        if client_id:
            calendly_rows = await database.query(
                "SELECT id, provider, is_active FROM calendar_integrations WHERE client_id = $1 AND provider = 'calendly'",
                [uuid.UUID(client_id)]
            )
        else:
            calendly_rows = await database.query(
                "SELECT id, provider, is_active FROM calendar_integrations WHERE user_id = $1 AND provider = 'calendly'",
                [uuid.UUID(user_id)]
            )
        
        for row in calendly_rows:
            if row["is_active"]:
                calendars.append({
                    "id": str(row["id"]),
                    "provider": "Calendly",
                    "name": "Calendly"
                })
        
        # Fetch Google Calendar
        if client_id:
            google_rows = await database.query(
                "SELECT id, provider, is_active FROM calendar_integrations WHERE client_id = $1 AND provider = 'google'",
                [uuid.UUID(client_id)]
            )
        else:
            google_rows = await database.query(
                "SELECT id, provider, is_active FROM calendar_integrations WHERE user_id = $1 AND provider = 'google'",
                [uuid.UUID(user_id)]
            )
        
        for row in google_rows:
            if row["is_active"]:
                calendars.append({
                    "id": str(row["id"]),
                    "provider": "Google Calendar",
                    "name": "Google Calendar"
                })
        
        return ApiResponse.success(
            status_code=200,
            message="Calendars retrieved successfully",
            data={"calendars": calendars}
        )
    
    except Exception as e:
        logger.error(f"Error listing calendars: {e}")
        return ApiResponse.success(
            status_code=200,
            message="No calendars found",
            data={"calendars": []}
        )


@router.get("/knowledge-bases")
async def list_knowledge_bases(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List all knowledge bases for the current user."""
    user_id = current_user.get("id")
    client_id = current_user.get("client_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    knowledge_bases = []
    
    try:
        if client_id:
            kb_rows = await database.query(
                "SELECT id, name FROM knowledge_bases WHERE client_id = $1 ORDER BY created_at DESC",
                [uuid.UUID(client_id)]
            )
        else:
            kb_rows = await database.query(
                "SELECT id, name FROM knowledge_bases WHERE user_id = $1 ORDER BY created_at DESC",
                [uuid.UUID(user_id)]
            )
        
        for row in kb_rows:
            knowledge_bases.append({
                "id": str(row["id"]),
                "name": row["name"]
            })
        
        return ApiResponse.success(
            status_code=200,
            message="Knowledge bases retrieved successfully",
            data={"knowledgeBases": knowledge_bases}
        )
    
    except Exception as e:
        logger.error(f"Error listing knowledge bases: {e}")
        return ApiResponse.success(
            status_code=200,
            message="No knowledge bases found",
            data={"knowledgeBases": []}
        )


@router.get("/phone-numbers")
async def list_phone_numbers(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List all phone numbers available for the current user."""
    user_id = current_user.get("id")
    client_id = current_user.get("client_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    phone_numbers = []
    
    try:
        if client_id:
            phone_rows = await database.query(
                "SELECT id, number, name FROM phone_numbers WHERE client_id = $1 AND is_active = TRUE ORDER BY created_at DESC",
                [uuid.UUID(client_id)]
            )
        else:
            phone_rows = await database.query(
                "SELECT id, number, name FROM phone_numbers WHERE user_id = $1 AND is_active = TRUE ORDER BY created_at DESC",
                [uuid.UUID(user_id)]
            )
        
        for row in phone_rows:
            phone_numbers.append({
                "id": str(row["id"]),
                "number": row["number"],
                "name": row["name"]
            })
        
        return ApiResponse.success(
            status_code=200,
            message="Phone numbers retrieved successfully",
            data={"phoneNumbers": phone_numbers}
        )
    
    except Exception as e:
        logger.error(f"Error listing phone numbers: {e}")
        return ApiResponse.success(
            status_code=200,
            message="No phone numbers found",
            data={"phoneNumbers": []}
        )


def get_error_html(detail_msg: str) -> str:
    """Helper to return styled HTML error feedback."""
    return f"""
        <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fafafa;">
            <div style="text-align: center; border: 1px solid #fca5a5; background: white; padding: 2.5rem; border-radius: 16px; max-width: 380px;">
              <div style="width: 48px; height: 48px; border-radius: 50%; background: #fef2f2; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                <svg style="width: 24px; height: 24px; color: #ef4444;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h2 style="color: #991b1b; margin: 0 0 0.5rem 0; font-size: 1.25rem; font-weight: 700;">OAuth Failed</h2>
              <p style="color: #7f1d1d; margin: 0; font-size: 0.875rem; line-height: 1.5;">{detail_msg}</p>
              <button onclick="window.close()" style="margin-top: 1.25rem; background: #991b1b; color: white; border: none; border-radius: 8px; padding: 0.5rem 1rem; font-size: 0.875rem; font-weight: 600; cursor: pointer;">Close Window</button>
            </div>
          </body>
        </html>
    """
