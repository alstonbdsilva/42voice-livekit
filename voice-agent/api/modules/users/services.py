"""
Users service.
Manages platform users under SUPER_ADMIN policies.
"""

import bcrypt
import logging
from typing import Dict, Any, List, Optional
from api import database
from api.utils.errors import ConflictError, NotFoundError
from api.modules.auth.repositories import UserRepository, AuditRepository
from config import get_settings

logger = logging.getLogger("voice-agent.api.users.services")


class UsersService:
    def __init__(self):
        self.user_repository = UserRepository()
        self.audit_repository = AuditRepository()

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Fetch all users and map to CamelCase response formats."""
        users = await self.user_repository.find_all()
        return [self.map_to_response(u) for u in users]

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user profile."""
        user = await self.user_repository.find_with_role_by_id(user_id)
        if not user:
            return None
        return self.map_to_response(user)

    async def create_user(self, dto: Dict[str, Any], temp_password_plain: str, actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user with secure password hash and email audit verification."""
        existing = await self.user_repository.find_by_email(dto["email"])
        if existing:
            raise ConflictError("A user with this email address already exists.", "EMAIL_ALREADY_EXISTS")
            
        settings = get_settings()
        
        async def trans_cb(conn):
            role_id = await self.user_repository.get_role_id_by_name(dto["roleName"])
            
            hashed = bcrypt.hashpw(
                temp_password_plain.encode('utf-8'),
                bcrypt.gensalt(settings.bcrypt_salt_rounds)
            )
            password_hash = hashed.decode('utf-8')
            
            new_user = await self.user_repository.create(
                {
                    "email": dto["email"],
                    "password_hash": password_hash,
                    "first_name": dto["firstName"],
                    "last_name": dto["lastName"],
                    "phone": dto.get("phone"),
                    "role_id": role_id,
                    "reseller_id": dto.get("resellerId"),
                    "client_id": dto.get("clientId"),
                    "is_verified": True # Invited users are pre-verified
                },
                client=conn
            )
            
            await self.audit_repository.create(
                user_id=actor_id,
                action="USER_CREATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"target_user_id": str(new_user["id"]), "email": dto["email"], "role_name": dto["roleName"]},
                client=conn
            )
            return new_user
            
        result = await database.transaction(trans_cb)
        
        # Retrieve full profile record
        full_user = await self.user_repository.find_with_role_by_id(result["id"])
        if not full_user:
            raise NotFoundError("Created user record not found", "USER_NOT_FOUND")
        return self.map_to_response(full_user)

    async def update_user(self, user_id: str, dto: Dict[str, Any], actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Update user properties."""
        existing = await self.user_repository.find_with_role_by_id(user_id)
        if not existing:
            raise NotFoundError("User not found", "USER_NOT_FOUND")
            
        # Email collision check
        if "email" in dto and dto["email"] is not None:
            email_val = dto["email"].lower().strip()
            if email_val != existing["email"].lower():
                dup = await self.user_repository.find_by_email(email_val)
                if dup:
                    raise ConflictError("A user with this email address already exists.", "EMAIL_ALREADY_EXISTS")
                    
        async def trans_cb(conn):
            role_id = None
            if "roleName" in dto and dto["roleName"] is not None:
                role_id = await self.user_repository.get_role_id_by_name(dto["roleName"])
                
            updated = await self.user_repository.admin_update(
                user_id,
                {
                    "first_name": dto.get("firstName"),
                    "last_name": dto.get("lastName"),
                    "email": dto.get("email"),
                    "phone": dto.get("phone"),
                    "role_id": role_id,
                    "reseller_id": dto.get("resellerId"),
                    "client_id": dto.get("clientId"),
                    "is_active": dto.get("isActive"),
                    "is_verified": dto.get("isVerified")
                }
            )
            
            await self.audit_repository.create(
                user_id=actor_id,
                action="USER_UPDATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"target_user_id": user_id, "email": dto.get("email") or existing["email"]},
                client=conn
            )
            return updated
            
        result = await database.transaction(trans_cb)
        full_user = await self.user_repository.find_with_role_by_id(result["id"])
        if not full_user:
            raise NotFoundError("Updated user record not found", "USER_NOT_FOUND")
        return self.map_to_response(full_user)

    async def delete_user(self, user_id: str, actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Permanently delete user record."""
        existing = await self.user_repository.find_with_role_by_id(user_id)
        if not existing:
            raise NotFoundError("User not found", "USER_NOT_FOUND")
            
        async def trans_cb(conn):
            await self.user_repository.delete(user_id, client=conn)
            await self.audit_repository.create(
                user_id=actor_id,
                action="USER_DELETE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"target_user_id": user_id, "email": existing["email"]},
                client=conn
            )
            
        await database.transaction(trans_cb)

    def map_to_response(self, u: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case DB columns to frontend camelCase DataTable properties."""
        first_name = u["first_name"] or ""
        last_name = u["last_name"] or ""
        return {
            "id": str(u["id"]),
            "email": u["email"],
            "firstName": first_name,
            "lastName": last_name,
            "name": f"{first_name} {last_name}".strip(),
            "phone": u["phone"] or "",
            "avatarUrl": u["avatar_url"] or "",
            "role": u["role_name"].lower(), # lowercase standard expected by React UI
            "resellerId": str(u["reseller_id"]) if u["reseller_id"] else None,
            "resellerName": u.get("reseller_name"),
            "clientId": str(u["client_id"]) if u["client_id"] else None,
            "clientName": u.get("client_name"),
            "isActive": u["is_active"],
            "isVerified": u["is_verified"],
            "status": "active" if u["is_active"] else "inactive",
            "createdAt": u["created_at"].isoformat() if hasattr(u["created_at"], "isoformat") else u["created_at"],
            "updatedAt": u["updated_at"].isoformat() if hasattr(u["updated_at"], "isoformat") else u["updated_at"]
        }
