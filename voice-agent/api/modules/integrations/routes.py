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


# --- API Routes ---

@router.get("/calendly/auth")
async def initiate_calendly_auth(user_id: str, client_id: Optional[str] = None):
    """
    Initiates Calendly OAuth flow.
    Generates a secure state parameter and redirects to Calendly authorization page.
    """
    settings = get_settings()
    if not settings.calendly_client_id or not settings.calendly_redirect_uri:
        raise HTTPException(status_code=500, detail="Calendly OAuth credentials are not configured in backend .env")
        
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
