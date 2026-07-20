"""
Clients Service.
Handles business operations and credentials sync for client organizations.
"""

import bcrypt
import logging
from typing import Dict, Any, List, Optional
from api import database
from api.utils.errors import ConflictError, NotFoundError
from api.modules.clients.repositories import ClientRepository
from api.modules.auth.repositories import UserRepository, AuditRepository
from config import get_settings

logger = logging.getLogger("voice-agent.api.clients.services")


class ClientService:
    def __init__(self):
        self.client_repository = ClientRepository()
        self.user_repository = UserRepository()
        self.audit_repository = AuditRepository()

    async def get_all_clients(self, reseller_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all clients, optionally filtered by reseller ID context."""
        clients = await self.client_repository.find_all(reseller_id)
        return [self.map_to_response(c) for c in clients]

    async def get_client_by_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Fetch individual client details."""
        client = await self.client_repository.find_by_id(client_id)
        if not client:
            return None
        return self.map_to_response(client)

    async def create_client(self, dto: Dict[str, Any], temp_password_plain: str, actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Create new client organization and generate linked login user profile."""
        existing_client = await self.client_repository.find_by_email(dto["contactEmail"])
        if existing_client:
            raise ConflictError("A client with this contact email already exists.", "CLIENT_ALREADY_EXISTS")
            
        existing_user = await self.user_repository.find_by_email(dto["contactEmail"])
        if existing_user:
            raise ConflictError("A user with this email address already exists.", "EMAIL_ALREADY_EXISTS")
            
        settings = get_settings()
        
        async def trans_cb(conn):
            # Create client
            new_client = await self.client_repository.create(dto, client=conn)
            
            # Hash temp password
            hashed = bcrypt.hashpw(
                temp_password_plain.encode('utf-8'),
                bcrypt.gensalt(settings.bcrypt_salt_rounds)
            )
            password_hash = hashed.decode('utf-8')
            
            # Get CLIENT role ID
            role_id = await self.user_repository.get_role_id_by_name("CLIENT")
            
            # Resolve split name
            name_parts = dto["name"].strip().split()
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Client"
            
            # Create linked user
            new_user = await self.user_repository.create(
                {
                    "email": dto["contactEmail"],
                    "password_hash": password_hash,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role_id": role_id,
                    "reseller_id": dto["resellerId"],
                    "client_id": new_client["id"],
                    "is_verified": True # Invited client user is pre-verified
                },
                client=conn
            )
            
            # Audit log
            await self.audit_repository.create(
                user_id=actor_id,
                action="CLIENT_CREATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"client_id": str(new_client["id"]), "name": dto["name"], "reseller_id": dto["resellerId"]},
                client=conn
            )
            return new_client
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    async def update_client(self, client_id: str, dto: Dict[str, Any], actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Update client company parameters and sync associated user records."""
        existing = await self.client_repository.find_by_id(client_id)
        if not existing:
            raise NotFoundError("Client not found", "CLIENT_NOT_FOUND")
            
        updates = {}
        if "name" in dto: updates["name"] = dto["name"]
        if "industry" in dto: updates["industry"] = dto["industry"]
        if "country" in dto: updates["country"] = dto["country"]
        if "monthlyRecurring" in dto: updates["monthlyRecurring"] = dto["monthlyRecurring"]
        if "contactEmail" in dto: updates["contactEmail"] = dto["contactEmail"]
        if "status" in dto: updates["status"] = dto["status"]
        if "resellerId" in dto: updates["resellerId"] = dto["resellerId"]
        
        async def trans_cb(conn):
            result = await self.client_repository.update(client_id, updates, client=conn)
            
            # Sync user if email or name changes
            if "contactEmail" in dto or "name" in dto:
                user_updates = {}
                if "contactEmail" in dto and dto["contactEmail"] is not None:
                    user_updates["email"] = dto["contactEmail"]
                if "name" in dto and dto["name"] is not None:
                    name_parts = dto["name"].strip().split()
                    user_updates["first_name"] = name_parts[0]
                    user_updates["last_name"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Client"
                await self.user_repository.update_client_user(client_id, user_updates, client=conn)
                
            # Audit log
            await self.audit_repository.create(
                user_id=actor_id,
                action="CLIENT_UPDATE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"client_id": client_id, "updates": updates},
                client=conn
            )
            return result
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    async def delete_client(self, client_id: str, actor_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Delete client organization and cascade linked user deletions."""
        existing = await self.client_repository.find_by_id(client_id)
        if not existing:
            raise NotFoundError("Client not found", "CLIENT_NOT_FOUND")
            
        async def trans_cb(conn):
            # Delete linked users first
            await self.user_repository.delete_client_user(client_id, client=conn)
            
            # Delete client record
            await self.client_repository.delete(client_id, client=conn)
            
            # Audit log
            await self.audit_repository.create(
                user_id=actor_id,
                action="CLIENT_DELETE",
                ip_address=client_ip,
                user_agent=user_agent,
                payload={"client_id": client_id, "name": existing["name"]},
                client=conn
            )
            
        await database.transaction(trans_cb)

    def map_to_response(self, c: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case clients columns to React DataTable camelCase bindings."""
        return {
            "id": str(c["id"]),
            "name": c["name"],
            "industry": c["industry"] or "",
            "country": c["country"] or "",
            "monthlyRecurring": float(c["monthly_recurring"]),
            "contactEmail": c["contact_email"],
            "status": c["status"],
            "resellerId": str(c["reseller_id"]) if c["reseller_id"] else None,
            "createdAt": c["created_at"].isoformat() if hasattr(c["created_at"], "isoformat") else c["created_at"]
        }
