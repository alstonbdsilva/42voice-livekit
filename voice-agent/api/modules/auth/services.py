"""
Authentication services.
Contains TokenService and AuthService.
"""

import hmac
import hashlib
import secrets
import jwt
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

from config import get_settings
from api import database
from api.utils.errors import (
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    BadRequestError
)
from api.modules.auth.repositories import UserRepository, TokenRepository, AuditRepository

logger = logging.getLogger("voice-agent.api.auth.services")


class TokenService:
    def __init__(self):
        self.token_repository = TokenRepository()

    def hash_token(self, token: str) -> str:
        """Generate sha256 hash of opaque or JWT token."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def get_expiry_date(self, expiry_str: str) -> datetime:
        """Parse JWT expiry string ('15m', '7d') into a datetime object."""
        now = datetime.utcnow()
        try:
            val = int("".join([c for c in expiry_str if c.isdigit()]))
        except ValueError:
            val = 7 # Fallback
            
        if expiry_str.endswith('m'):
            return now + timedelta(minutes=val)
        elif expiry_str.endswith('h'):
            return now + timedelta(hours=val)
        elif expiry_str.endswith('d'):
            return now + timedelta(days=val)
        else:
            return now + timedelta(days=val)

    def generate_access_token(self, payload: Dict[str, Any]) -> str:
        """Sign a new JWT access token."""
        settings = get_settings()
        expiry = self.get_expiry_date(settings.jwt_access_expiry)
        
        # Build claim payload
        claims = payload.copy()
        claims.update({
            "exp": expiry
        })
        return jwt.encode(claims, settings.jwt_access_secret, algorithm="HS256")

    def generate_refresh_token(self, payload: Dict[str, Any]) -> str:
        """Sign a new JWT refresh token."""
        settings = get_settings()
        expiry = self.get_expiry_date(settings.jwt_refresh_expiry)
        
        claims = payload.copy()
        claims.update({
            "exp": expiry
        })
        return jwt.encode(claims, settings.jwt_refresh_secret, algorithm="HS256")

    async def register_refresh_token(self, user_id: str, token: str) -> None:
        """Store hashed refresh token in database."""
        settings = get_settings()
        token_hash = self.hash_token(token)
        expires_at = self.get_expiry_date(settings.jwt_refresh_expiry)
        await self.token_repository.save_refresh_token(user_id, token_hash, expires_at)

    async def rotate_refresh_token(self, token: str) -> Tuple[str, str]:
        """Perform Refresh Token Rotation (RTR). Returns (new_access_token, new_refresh_token)."""
        settings = get_settings()
        
        try:
            decoded = jwt.decode(token, settings.jwt_refresh_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise UnauthorizedError("Invalid or expired refresh token signature", "REFRESH_TOKEN_INVALID")
            
        token_hash = self.hash_token(token)
        stored_token = await self.token_repository.find_refresh_token(token_hash)
        
        if not stored_token:
            raise UnauthorizedError("Refresh token record not found", "REFRESH_TOKEN_NOT_FOUND")
            
        if stored_token["is_revoked"]:
            # Token reuse breach! Invalidate all refresh tokens for this user
            await self.token_repository.revoke_all_user_refresh_tokens(stored_token["user_id"])
            raise UnauthorizedError("Session compromise detected. All login sessions invalidated.", "TOKEN_REUSE_DETECTED")
            
        # Verify expiration
        # Note: stored_token["expires_at"] could be offset-aware or naive. Let's make comparison naive to match utcnow.
        expires_at = stored_token["expires_at"]
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
            
        if datetime.utcnow() > expires_at:
            raise UnauthorizedError("Refresh token has expired", "REFRESH_TOKEN_EXPIRED")
            
        # Revoke used token
        await self.token_repository.revoke_refresh_token(token_hash)
        
        # Build fresh payload and sign tokens
        user_payload = {
            "id": decoded["id"],
            "email": decoded["email"],
            "role": decoded["role"],
            "is_verified": decoded["is_verified"]
        }
        
        new_access = self.generate_access_token(user_payload)
        new_refresh = self.generate_refresh_token(user_payload)
        
        # Save new refresh token
        new_hash = self.hash_token(new_refresh)
        new_expiry = self.get_expiry_date(settings.jwt_refresh_expiry)
        await self.token_repository.save_refresh_token(stored_token["user_id"], new_hash, new_expiry)
        
        return new_access, new_refresh

    async def revoke_refresh_token(self, token: str) -> None:
        """Revoke a refresh token on logout."""
        token_hash = self.hash_token(token)
        await self.token_repository.revoke_refresh_token(token_hash)

    def generate_opaque_token(self) -> str:
        """Generate a random 64-character token."""
        return secrets.token_hex(32)

    async def save_verification_token(self, user_id: str, token: str) -> None:
        """Generate and save email verification token."""
        token_hash = self.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(hours=24) # 24 hours
        await self.token_repository.invalidate_user_tokens(user_id, "EMAIL_VERIFICATION")
        await self.token_repository.save_user_token(user_id, token_hash, "EMAIL_VERIFICATION", expires_at)

    async def save_password_reset_token(self, user_id: str, token: str) -> None:
        """Generate and save password reset token."""
        token_hash = self.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(minutes=30) # 30 minutes
        await self.token_repository.invalidate_user_tokens(user_id, "PASSWORD_RESET")
        await self.token_repository.save_user_token(user_id, token_hash, "PASSWORD_RESET", expires_at)

    async def verify_user_token(self, token: str, token_type: str) -> str:
        """Verify verification or reset token, returning the user_id on success."""
        token_hash = self.hash_token(token)
        record = await self.token_repository.find_user_token(token_hash, token_type)
        
        if not record or record["is_used"]:
            raise UnauthorizedError("Token is invalid or has already been used", "TOKEN_INVALID")
            
        expires_at = record["expires_at"]
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
            
        if datetime.utcnow() > expires_at:
            raise UnauthorizedError("Verification link has expired", "TOKEN_EXPIRED")
            
        # Single-use consumption
        await self.token_repository.mark_user_token_used(token_hash)
        return str(record["user_id"])


class AuthService:
    def __init__(self):
        self.user_repository = UserRepository()
        self.token_repository = TokenRepository()
        self.audit_repository = AuditRepository()
        self.token_service = TokenService()

    async def register(self, dto: Dict[str, Any], client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Registers a new user record."""
        # 1. Unique email check
        existing = await self.user_repository.find_by_email(dto["email"])
        if existing:
            raise ConflictError("A user account with this email address already exists.", "EMAIL_ALREADY_EXISTS")
            
        settings = get_settings()
        
        # 2. Hash password with bcrypt
        # bcrypt.hashpw expects bytes. Salt rounds default to 12.
        hashed = bcrypt.hashpw(
            dto["password_hash"].encode('utf-8'), 
            bcrypt.gensalt(settings.bcrypt_salt_rounds)
        )
        password_hash = hashed.decode('utf-8')
        
        # 3. Role mapping
        role_name = dto.get("role_name") or "CLIENT"
        role_id = await self.user_repository.get_role_id_by_name(role_name)
        
        # 4. Save user
        user_dto = dto.copy()
        user_dto.update({
            "password_hash": password_hash,
            "role_id": role_id
        })
        new_user = await self.user_repository.create(user_dto)
        
        # 5. Verification token flow
        verification_token = self.token_service.generate_opaque_token()
        await self.token_service.save_verification_token(new_user["id"], verification_token)
        
        # Mock Email Dispatch logging
        settings = get_settings()
        verify_url = f"{settings.backend_url}/auth/verify-email?token={verification_token}"
        logger.info(f"[MAIL] Dispatching email verification to [{new_user['email']}] | Link: {verify_url}")
        
        # 6. Audit Trail
        await self.audit_repository.create(
            user_id=new_user["id"],
            action="USER_REGISTER",
            ip_address=client_ip,
            user_agent=user_agent,
            payload={"email": new_user["email"], "role": role_name}
        )
        
        # Prepare response
        res = dict(new_user)
        res.pop("password_hash", None)
        # Convert UUID columns to string representation
        for k in ["id", "reseller_id", "client_id"]:
            if res.get(k):
                res[k] = str(res[k])
        res["role_name"] = role_name
        return res

    async def login(self, email: str, password_plain: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate credentials, return tokens and user details."""
        user = await self.user_repository.find_by_email(email)
        if not user:
            raise UnauthorizedError("Invalid email or password credentials", "INVALID_CREDENTIALS")
            
        # Password check
        pw_hash = user["password_hash"]
        if not bcrypt.checkpw(password_plain.encode('utf-8'), pw_hash.encode('utf-8')):
            raise UnauthorizedError("Invalid email or password credentials", "INVALID_CREDENTIALS")
            
        # Active status check
        if not user["is_active"]:
            raise ForbiddenError("Your account has been deactivated. Please contact support.", "USER_DEACTIVATED")
            
        # Get role name
        role_details = await self.user_repository.find_with_role_by_id(user["id"])
        role_name = role_details["role_name"] if role_details else "CLIENT"
        
        # Token payload
        payload = {
            "id": str(user["id"]),
            "email": user["email"],
            "role": role_name,
            "is_verified": user["is_verified"]
        }
        
        access_token = self.token_service.generate_access_token(payload)
        refresh_token = self.token_service.generate_refresh_token(payload)
        
        # Register in database
        await self.token_service.register_refresh_token(user["id"], refresh_token)
        
        # Audit log
        await self.audit_repository.create(
            user_id=user["id"],
            action="USER_LOGIN",
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        user_res = dict(user)
        user_res.pop("password_hash", None)
        for k in ["id", "reseller_id", "client_id"]:
            if user_res.get(k):
                user_res[k] = str(user_res[k])
                
        user_res["role_name"] = role_name
        return {
            "user": user_res,
            "tokens": {
                "accessToken": access_token,
                "refreshToken": refresh_token
            }
        }

    async def logout(self, refresh_token: str, user_id: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Revoke refresh session."""
        await self.token_service.revoke_refresh_token(refresh_token)
        await self.audit_repository.create(
            user_id=user_id,
            action="USER_LOGOUT",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def verify_email(self, token: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Consume verification token and mark user verified."""
        user_id = await self.token_service.verify_user_token(token, "EMAIL_VERIFICATION")
        await self.user_repository.update_verification_status(user_id, True)
        
        await self.audit_repository.create(
            user_id=user_id,
            action="EMAIL_VERIFIED_SUCCESS",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def resend_verification(self, email: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Request new validation email challenge."""
        user = await self.user_repository.findByEmail(email)
        if not user:
            return # silent return
            
        if user["is_verified"]:
            raise BadRequestError("Email address is already verified", "EMAIL_ALREADY_VERIFIED")
            
        token = self.token_service.generate_opaque_token()
        await self.token_service.save_verification_token(user["id"], token)
        
        # Log email link
        settings = get_settings()
        verify_url = f"{settings.backend_url}/auth/verify-email?token={token}"
        logger.info(f"[MAIL] Resending email verification to [{user['email']}] | Link: {verify_url}")
        
        await self.audit_repository.create(
            user_id=user["id"],
            action="EMAIL_VERIFICATION_RESEND",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def forgot_password(self, email: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Create password reset challenge and log verification link."""
        user = await self.user_repository.find_by_email(email)
        if not user:
            return # silent return
            
        token = self.token_service.generate_opaque_token()
        await self.token_service.save_password_reset_token(user["id"], token)
        
        # Log link
        settings = get_settings()
        reset_url = f"{settings.backend_url}/auth/reset-password?token={token}"
        logger.info(f"[MAIL] Dispatching password reset to [{user['email']}] | Link: {reset_url}")
        
        await self.audit_repository.create(
            user_id=user["id"],
            action="PASSWORD_RESET_REQUEST",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def reset_password(self, token: str, password_plain: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Reset password and revoke active refresh tokens."""
        user_id = await self.token_service.verify_user_token(token, "PASSWORD_RESET")
        settings = get_settings()
        
        hashed = bcrypt.hashpw(
            password_plain.encode('utf-8'),
            bcrypt.gensalt(settings.bcrypt_salt_rounds)
        )
        password_hash = hashed.decode('utf-8')
        
        await self.user_repository.update_password(user_id, password_hash)
        await self.token_repository.revoke_all_user_refresh_tokens(user_id)
        
        await self.audit_repository.create(
            user_id=user_id,
            action="PASSWORD_RESET_SUCCESS",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def change_password(self, user_id: str, old_password: str, new_password: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Change authenticated user password."""
        user = await self.user_repository.find_with_role_by_id(user_id)
        if not user:
            raise NotFoundError("User account not found", "USER_NOT_FOUND")
            
        raw_user = await self.user_repository.find_by_email(user["email"])
        if not raw_user:
            raise NotFoundError("User account not found", "USER_NOT_FOUND")
            
        # Verify current password
        if not bcrypt.checkpw(old_password.encode('utf-8'), raw_user["password_hash"].encode('utf-8')):
            raise UnauthorizedError("Current password is incorrect", "INVALID_OLD_PASSWORD")
            
        settings = get_settings()
        hashed = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt(settings.bcrypt_salt_rounds)
        )
        new_password_hash = hashed.decode('utf-8')
        
        await self.user_repository.update_password(user_id, new_password_hash)
        await self.token_repository.revoke_all_user_refresh_tokens(user_id)
        
        await self.audit_repository.create(
            user_id=user_id,
            action="PASSWORD_CHANGE_SUCCESS",
            ip_address=client_ip,
            user_agent=user_agent
        )

    async def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch user profile record joined with role details."""
        profile = await self.user_repository.find_with_role_by_id(user_id)
        if not profile:
            raise NotFoundError("User profile not found", "PROFILE_NOT_FOUND")
            
        res = dict(profile)
        for k in ["id", "reseller_id", "client_id"]:
            if res.get(k):
                res[k] = str(res[k])
        # Client expected role_name mapping
        res["role_name"] = profile["role_name"]
        return res

    async def update_profile(self, user_id: str, dto: Dict[str, Any], client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Update authenticated user profile fields."""
        updated = await self.user_repository.update(user_id, dto)
        
        await self.audit_repository.create(
            user_id=user_id,
            action="USER_PROFILE_UPDATE",
            ip_address=client_ip,
            user_agent=user_agent,
            payload={"updated_fields": list(dto.keys())}
        )
        
        role_details = await self.user_repository.find_with_role_by_id(user_id)
        role_name = role_details["role_name"] if role_details else "CLIENT"
        
        res = dict(updated)
        res.pop("password_hash", None)
        for k in ["id", "reseller_id", "client_id"]:
            if res.get(k):
                res[k] = str(res[k])
        res["role_name"] = role_name
        return res

    async def deactivate_user(self, user_id: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Deactivate account and revoke all sessions."""
        await self.user_repository.deactivate(user_id)
        await self.token_repository.revoke_all_user_refresh_tokens(user_id)
        
        await self.audit_repository.create(
            user_id=user_id,
            action="USER_DEACTIVATED",
            ip_address=client_ip,
            user_agent=user_agent
        )
