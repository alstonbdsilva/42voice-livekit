"""
Authentication and Role authorization dependencies.
Decodes JWT Bearer tokens and checks user database states.
"""

import hmac
import jwt
from fastapi import Request, Depends
from typing import List, Dict, Any, Callable
from api.utils.errors import UnauthorizedError, ForbiddenError
from api import database
from config import get_settings


async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to extract and validate the JWT Access Token.
    Returns user details if active and verified in database.
    """
    settings = get_settings()
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Access token is missing or malformed", "TOKEN_MISSING")
        
    token = auth_header.split(" ")[1]
    
    try:
        # Decode the access token
        decoded = jwt.decode(
            token, 
            settings.jwt_access_secret, 
            algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Access token has expired", "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid access token", "TOKEN_INVALID")
        
    user_id = decoded.get("id")
    if not user_id:
        raise UnauthorizedError("Invalid token payload structure", "TOKEN_INVALID")
        
    # Look up database to verify active status and actual role
    users = await database.query(
        """SELECT u.id, u.email, u.is_active, u.is_verified, u.client_id, u.reseller_id, r.name as role 
           FROM users u
           JOIN roles r ON u.role_id = r.id
           WHERE u.id = $1""",
        [user_id]
    )
    
    if not users:
        raise UnauthorizedError("User account not found", "USER_NOT_FOUND")
        
    user = users[0]
    
    if not user["is_active"]:
        raise ForbiddenError("Your account has been deactivated. Please contact support.", "USER_DEACTIVATED")
        
    # Standardize formats (e.g. client_id / reseller_id as strings, not UUID type, for JSON serialization)
    user_dict = {
        "id": str(user["id"]),
        "email": user["email"],
        "role": user["role"], # E.g. 'SUPER_ADMIN'
        "is_verified": user["is_verified"],
        "client_id": str(user["client_id"]) if user["client_id"] else None,
        "reseller_id": str(user["reseller_id"]) if user["reseller_id"] else None,
    }
    
    # Store user state on the request context
    request.state.user = user_dict
    return user_dict


async def require_internal_worker(request: Request) -> None:
    """
    FastAPI dependency that authenticates machine-to-machine requests from the
    trusted voice-agent worker (e.g. POST /conversations/register).

    Authenticates via an `Authorization: Bearer <token>` header carrying the
    shared internal worker token (INTERNAL_WORKER_TOKEN). Comparison is done in
    constant time to avoid timing side-channels.

    Fail-closed: if the token is not configured, every request is rejected.
    In production the Settings model itself refuses to boot without the token.
    """
    settings = get_settings()

    # In development the worker token is optional and registration may proceed
    # (matching the pre-existing dev/test behaviour). Production/staging always
    # fail-closed: a missing or mismatched token rejects the request.
    if settings.environment == "development":
        return

    raw_token = settings.internal_worker_token
    # A missing token is always a hard failure, never a pass-through.
    if not raw_token:
        raise UnauthorizedError(
            "Internal worker authentication is not configured", "INTERNAL_TOKEN_NOT_CONFIGURED"
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Internal worker token is missing or malformed", "TOKEN_MISSING")

    presented = auth_header.split(" ", 1)[1].strip()
    if not hmac.compare_digest(presented.encode("utf-8"), raw_token.encode("utf-8")):
        raise UnauthorizedError("Invalid internal worker token", "TOKEN_INVALID")


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory to restrict routes to specified roles.
    Must be used in combination with get_current_user.
    """
    async def dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user["role"] not in allowed_roles:
            raise ForbiddenError(
                "You do not have the required permissions to access this resource", 
                "ROLE_FORBIDDEN"
            )
        return current_user
        
    return dependency
