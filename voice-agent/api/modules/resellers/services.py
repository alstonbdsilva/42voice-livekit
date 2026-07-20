"""
Reseller Service.
Coordinates partner management and cascading database queries for resellers.
"""

import bcrypt
import logging
from typing import Dict, Any, List, Optional
from api import database
from api.utils.errors import ConflictError, NotFoundError
from api.modules.resellers.repositories import ResellerRepository
from api.modules.auth.repositories import UserRepository, AuditRepository
from config import get_settings

logger = logging.getLogger("voice-agent.api.resellers.services")


class ResellerService:
    def __init__(self):
        self.reseller_repository = ResellerRepository()
        self.user_repository = UserRepository()
        self.audit_repository = AuditRepository()

    async def get_all_resellers(self) -> List[Dict[str, Any]]:
        """Fetch all resellers and map keys for React client DataTable."""
        resellers = await self.reseller_repository.find_all()
        return [self.map_to_response(r) for r in resellers]

    async def get_reseller_by_id(self, reseller_id: str) -> Optional[Dict[str, Any]]:
        """Fetch reseller by ID."""
        reseller = await self.reseller_repository.find_by_id(reseller_id)
        if not reseller:
            return None
        return self.map_to_response(reseller)

    async def create_reseller(self, dto: Dict[str, Any], temp_password_plain: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Create reseller partner and seed associated user credential logins."""
        # 1. Partner and user email collision checks
        existing_reseller = await self.reseller_repository.find_by_email(dto["contactEmail"])
        if existing_reseller:
            raise ConflictError("A partner with this contact email already exists.", "RESELLER_ALREADY_EXISTS")
            
        existing_user = await self.user_repository.find_by_email(dto["contactEmail"])
        if existing_user:
            raise ConflictError("A user with this email address already exists.", "EMAIL_ALREADY_EXISTS")
            
        settings = get_settings()
        
        async def trans_cb(conn):
            # Create reseller record
            new_reseller = await self.reseller_repository.create(dto, client=conn)
            
            # Hash temp password
            hashed = bcrypt.hashpw(
                temp_password_plain.encode('utf-8'),
                bcrypt.gensalt(settings.bcrypt_salt_rounds)
            )
            password_hash = hashed.decode('utf-8')
            
            # Resolve reseller role ID
            role_id = await self.user_repository.get_role_id_by_name("RESELLER")
            
            # Resolve split names
            name_parts = dto["name"].strip().split()
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Partner"
            
            # Create linked user
            new_user = await self.user_repository.create(
                {
                    "email": dto["contactEmail"],
                    "password_hash": password_hash,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role_id": role_id,
                    "reseller_id": new_reseller["id"],
                    "is_verified": True # Auto verify reseller user
                },
                client=conn
            )
            
            # Audit log
            await self.audit_repository.create(
                user_id=new_user["id"],
                action="RESELLER_CREATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"reseller_id": str(new_reseller["id"]), "email": dto["contactEmail"]},
                client=conn
            )
            return new_reseller
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    async def update_reseller(self, reseller_id: str, dto: Dict[str, Any], client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Update reseller details and sync linked user credentials."""
        reseller = await self.reseller_repository.find_by_id(reseller_id)
        if not reseller:
            raise NotFoundError("Reseller not found", "RESELLER_NOT_FOUND")
            
        if "contactEmail" in dto and dto["contactEmail"] is not None:
            email_val = dto["contactEmail"].lower().strip()
            if email_val != reseller["contact_email"].lower():
                dup_reseller = await self.reseller_repository.find_by_email(email_val)
                if dup_reseller:
                    raise ConflictError("A partner with this contact email already exists.", "RESELLER_ALREADY_EXISTS")
                
                dup_user = await self.user_repository.find_by_email(email_val)
                if dup_user:
                    raise ConflictError("A user with this email address already exists.", "EMAIL_ALREADY_EXISTS")
                    
        updates = {}
        if "name" in dto: updates["name"] = dto["name"]
        if "country" in dto: updates["country"] = dto["country"]
        if "commissionPct" in dto: updates["commission_pct"] = dto["commissionPct"]
        if "contactEmail" in dto: updates["contact_email"] = dto["contactEmail"]
        if "status" in dto: updates["status"] = dto["status"]
        
        async def trans_cb(conn):
            # Update reseller
            updated = await self.reseller_repository.update(reseller_id, updates, client=conn)
            
            # Sync user
            first_name = None
            last_name = None
            if "name" in dto and dto["name"] is not None:
                name_parts = dto["name"].strip().split()
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Partner"
                
            email_val = dto["contactEmail"].lower().strip() if "contactEmail" in dto and dto["contactEmail"] is not None else None
            is_active_val = (dto["status"] == "active") if "status" in dto and dto["status"] is not None else None
            
            await self.user_repository.update_reseller_user(
                reseller_id, 
                email_val, 
                first_name, 
                last_name, 
                is_active_val, 
                client=conn
            )
            
            # Audit log
            linked_user = await self.user_repository.find_by_reseller_id(reseller_id, client=conn)
            await self.audit_repository.create(
                user_id=linked_user["id"] if linked_user else None,
                action="RESELLER_UPDATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"reseller_id": reseller_id, "updates": updates},
                client=conn
            )
            return updated
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    async def delete_reseller(self, reseller_id: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Delete reseller and cascade deletion of partner user logins."""
        reseller = await self.reseller_repository.find_by_id(reseller_id)
        if not reseller:
            raise NotFoundError("Reseller not found", "RESELLER_NOT_FOUND")
            
        async def trans_cb(conn):
            linked_user = await self.user_repository.find_by_reseller_id(reseller_id, client=conn)
            
            if linked_user:
                await self.audit_repository.create(
                    user_id=linked_user["id"],
                    action="RESELLER_DELETE",
                    ip_address=client_ip,
                    user_agent=user_agent,
                    payload={"reseller_id": reseller_id, "email": reseller["contact_email"]},
                    client=conn
                )
                await self.user_repository.delete_reseller_user(reseller_id, client=conn)
                
            await self.reseller_repository.delete(reseller_id, client=conn)
            
        await database.transaction(trans_cb)

    def map_to_response(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case reseller variables to React DataTable camelCase bindings."""
        return {
            "id": str(r["id"]),
            "name": r["name"],
            "country": r["country"],
            "commissionPct": float(r["commission_pct"]),
            "contactEmail": r["contact_email"],
            "status": r["status"],
            "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]
        }
