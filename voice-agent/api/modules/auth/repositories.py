"""
Database repositories for the Authentication module.
Contains UserRepository, TokenRepository, and AuditRepository.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from api import database
from api.utils.logger import audit_logger

logger = logging.getLogger("voice-agent.api.auth.repositories")


class UserRepository:
    async def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find user details by email address."""
        rows = await database.query(
            """SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified, created_at, updated_at 
               FROM users 
               WHERE email = $1""",
            [email.lower().strip()]
        )
        return rows[0] if rows else None

    async def find_with_role_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Find user profile with role configuration details by ID."""
        rows = await database.query(
            """SELECT u.id, u.email, u.first_name, u.last_name, u.phone, u.avatar_url, u.role_id, r.name as role_name, u.reseller_id, u.client_id, u.is_active, u.is_verified, u.created_at, u.updated_at 
               FROM users u
               JOIN roles r ON u.role_id = r.id
               WHERE u.id = $1""",
            [user_id]
        )
        return rows[0] if rows else None

    async def get_role_id_by_name(self, role_name: str) -> int:
        """Get role ID by role name."""
        rows = await database.query(
            "SELECT id FROM roles WHERE name = $1",
            [role_name.upper().strip()]
        )
        if not rows:
            raise ValueError(f"Role name '{role_name}' does not exist in roles table.")
        return rows[0]["id"]

    async def create(self, dto: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Inserts a new user record."""
        email = dto["email"].lower().strip()
        first_name = dto["first_name"].strip()
        last_name = dto["last_name"].strip()
        
        rows = await database.query(
            """INSERT INTO users (email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) 
               RETURNING id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified, created_at, updated_at""",
            [
                email,
                dto["password_hash"],
                first_name,
                last_name,
                dto.get("phone"),
                dto.get("avatar_url"),
                dto["role_id"],
                dto.get("reseller_id"),
                dto.get("client_id"),
                True, # is_active
                dto.get("is_verified", False)
            ],
            client=client
        )
        return rows[0]

    async def update(self, user_id: str, dto: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically update profile attributes."""
        updates = []
        params = [user_id]
        idx = 2
        
        if "first_name" in dto and dto["first_name"] is not None:
            updates.append(f"first_name = ${idx}")
            params.append(dto["first_name"].strip())
            idx += 1
        if "last_name" in dto and dto["last_name"] is not None:
            updates.append(f"last_name = ${idx}")
            params.append(dto["last_name"].strip())
            idx += 1
        if "phone" in dto:
            updates.append(f"phone = ${idx}")
            params.append(dto["phone"])
            idx += 1
        if "avatar_url" in dto:
            updates.append(f"avatar_url = ${idx}")
            params.append(dto["avatar_url"])
            idx += 1
            
        if not updates:
            rows = await database.query(
                """SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, is_active, is_verified, created_at, updated_at 
                   FROM users 
                   WHERE id = $1""",
                [user_id]
            )
            return rows[0]
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        sql = f"""
            UPDATE users 
            SET {", ".join(updates)} 
            WHERE id = $1 
            RETURNING id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, is_active, is_verified, created_at, updated_at
        """
        rows = await database.query(sql, params)
        return rows[0]

    async def update_verification_status(self, user_id: str, is_verified: bool) -> None:
        """Update user verification state."""
        await database.query(
            "UPDATE users SET is_verified = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            [user_id, is_verified]
        )

    async def update_password(self, user_id: str, password_hash: str) -> None:
        """Update password hash."""
        await database.query(
            "UPDATE users SET password_hash = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            [user_id, password_hash]
        )

    async def deactivate(self, user_id: str) -> None:
        """Deactivate a user account."""
        await database.query(
            "UPDATE users SET is_active = false, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            [user_id]
        )

    async def update_reseller_user(self, reseller_id: str, email: Optional[str], first_name: Optional[str], last_name: Optional[str], is_active: Optional[bool], client: Optional[Any] = None) -> None:
        """Sync update reseller user metadata."""
        await database.query(
            """UPDATE users 
               SET email = COALESCE($1, email),
                   first_name = COALESCE($2, first_name),
                   last_name = COALESCE($3, last_name),
                   is_active = COALESCE($4, is_active),
                   updated_at = CURRENT_TIMESTAMP
               WHERE reseller_id = $5""",
            [email, first_name, last_name, is_active, reseller_id],
            client=client
        )

    async def delete_reseller_user(self, reseller_id: str, client: Optional[Any] = None) -> None:
        """Sync delete reseller user record."""
        await database.query("DELETE FROM users WHERE reseller_id = $1", [reseller_id], client=client)

    async def find_by_client_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Find a user account linked to a client organization."""
        rows = await database.query(
            "SELECT id, email, first_name, last_name, client_id FROM users WHERE client_id = $1 LIMIT 1",
            [client_id]
        )
        return rows[0] if rows else None

    async def update_client_user(self, client_id: str, updates: Dict[str, Any], client: Optional[Any] = None) -> None:
        """Sync update client user details."""
        fields = []
        params = [client_id]
        idx = 2
        
        if "email" in updates:
            fields.append(f"email = ${idx}")
            params.append(updates["email"].lower().strip())
            idx += 1
        if "first_name" in updates:
            fields.append(f"first_name = ${idx}")
            params.append(updates["first_name"].strip())
            idx += 1
            
        if fields:
            await database.query(
                f"UPDATE users SET {', '.join(fields)} WHERE client_id = $1",
                params,
                client=client
            )

    async def delete_client_user(self, client_id: str, client: Optional[Any] = None) -> None:
        """Sync delete client user."""
        await database.query("DELETE FROM users WHERE client_id = $1", [client_id], client=client)

    async def find_by_reseller_id(self, reseller_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find reseller owner user account."""
        rows = await database.query(
            """SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified, created_at, updated_at 
               FROM users 
               WHERE reseller_id = $1 LIMIT 1""",
            [reseller_id],
            client=client
        )
        return rows[0] if rows else None

    async def find_all(self) -> List[Dict[str, Any]]:
        """Fetch all users in the system."""
        return await database.query(
            """SELECT u.id, u.email, u.first_name, u.last_name, u.phone, u.avatar_url, u.role_id, r.name as role_name, 
                      u.reseller_id, res.name as reseller_name, 
                      u.client_id, cl.name as client_name, 
                      u.is_active, u.is_verified, u.created_at, u.updated_at 
               FROM users u
               JOIN roles r ON u.role_id = r.id
               LEFT JOIN resellers res ON u.reseller_id = res.id
               LEFT JOIN clients cl ON u.client_id = cl.id
               ORDER BY u.created_at DESC"""
        )

    async def admin_update(self, user_id: str, dto: Dict[str, Any]) -> Dict[str, Any]:
        """Admin updates user attributes dynamically."""
        updates = []
        params = [user_id]
        idx = 2
        
        fields_mapping = {
            "first_name": "first_name",
            "last_name": "last_name",
            "email": "email",
            "phone": "phone",
            "role_id": "role_id",
            "reseller_id": "reseller_id",
            "client_id": "client_id",
            "is_active": "is_active",
            "is_verified": "is_verified",
        }
        
        for key, col in fields_mapping.items():
            if key in dto and dto[key] is not None:
                updates.append(f"{col} = ${idx}")
                val = dto[key]
                if key in ["first_name", "last_name"]:
                    val = val.strip()
                elif key == "email":
                    val = val.lower().strip()
                params.append(val)
                idx += 1
                
        if not updates:
            rows = await database.query(
                """SELECT id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified, created_at, updated_at 
                   FROM users 
                   WHERE id = $1""",
                [user_id]
            )
            return rows[0]
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        sql = f"""
            UPDATE users 
            SET {", ".join(updates)} 
            WHERE id = $1 
            RETURNING id, email, password_hash, first_name, last_name, phone, avatar_url, role_id, reseller_id, client_id, is_active, is_verified, created_at, updated_at
        """
        rows = await database.query(sql, params)
        return rows[0]

    async def delete(self, user_id: str, client: Optional[Any] = None) -> None:
        """Permanently delete user record."""
        await database.query("DELETE FROM users WHERE id = $1", [user_id], client=client)


class TokenRepository:
    async def save_refresh_token(self, user_id: str, token_hash: str, expires_at: Any) -> None:
        """Save refresh token details in database."""
        await database.query(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
            [user_id, token_hash, expires_at]
        )

    async def find_refresh_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve refresh token record from database."""
        rows = await database.query(
            """SELECT id, user_id, token_hash, expires_at, is_revoked, created_at 
               FROM refresh_tokens 
               WHERE token_hash = $1""",
            [token_hash]
        )
        return rows[0] if rows else None

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a specific refresh token by hash."""
        await database.query(
            "UPDATE refresh_tokens SET is_revoked = true WHERE token_hash = $1",
            [token_hash]
        )

    async def revoke_all_user_refresh_tokens(self, user_id: str) -> None:
        """Revoke all active refresh sessions for a user."""
        await database.query(
            "UPDATE refresh_tokens SET is_revoked = true WHERE user_id = $1",
            [user_id]
        )

    async def save_user_token(self, user_id: str, token_hash: str, token_type: str, expires_at: Any) -> None:
        """Save verification/reset token."""
        await database.query(
            "INSERT INTO user_tokens (user_id, token_hash, type, expires_at) VALUES ($1, $2, $3, $4)",
            [user_id, token_hash, token_type, expires_at]
        )

    async def find_user_token(self, token_hash: str, token_type: str) -> Optional[Dict[str, Any]]:
        """Find user token by hash and type."""
        rows = await database.query(
            """SELECT id, user_id, token_hash, type, expires_at, is_used, created_at 
               FROM user_tokens 
               WHERE token_hash = $1 AND type = $2""",
            [token_hash, token_type]
        )
        return rows[0] if rows else None

    async def mark_user_token_used(self, token_hash: str) -> None:
        """Mark verification/reset token as consumed."""
        await database.query(
            "UPDATE user_tokens SET is_used = true WHERE token_hash = $1",
            [token_hash]
        )

    async def invalidate_user_tokens(self, user_id: str, token_type: str) -> None:
        """Invalidate all active user verification/reset tokens of a specific type."""
        await database.query(
            "UPDATE user_tokens SET is_used = true WHERE user_id = $1 AND type = $2 AND is_used = false",
            [user_id, token_type]
        )


class AuditRepository:
    async def create(self, user_id: Optional[str], action: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None, payload: Optional[Any] = None, client: Optional[Any] = None) -> None:
        """Record a security/compliance log row."""
        try:
            payload_str = json.dumps(payload) if payload is not None else None
            await database.query(
                """INSERT INTO audit_logs (user_id, action, ip_address, user_agent, payload) 
                   VALUES ($1, $2, $3, $4, $5)""",
                [user_id, action, ip_address, user_agent, payload_str],
                client=client
            )
            
            # Replicate to Winston mirror
            audit_logger.info(
                f"Audit Event: {action} - User: {user_id or 'System'} - IP: {ip_address or '-'} - Payload: {payload}"
            )
        except Exception as e:
            # Audit logging failures should not crash requests
            audit_logger.error(f"Audit log execution failed: {e}")

    async def find_all(self) -> List[Dict[str, Any]]:
        """Fetch all audit logs."""
        return await database.query(
            """SELECT al.id, al.user_id, al.action, al.ip_address, al.user_agent, al.payload, al.created_at,
                      u.email as actor_email, r.name as actor_role
               FROM audit_logs al
               LEFT JOIN users u ON al.user_id = u.id
               LEFT JOIN roles r ON u.role_id = r.id
               ORDER BY al.created_at DESC"""
        )
