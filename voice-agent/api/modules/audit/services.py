"""
Audit Logs Service.
Handles retrieval and formatting of security/compliance logs.
"""

import json
import logging
from typing import Dict, Any, List
from api.modules.auth.repositories import AuditRepository

logger = logging.getLogger("voice-agent.api.audit.services")


class AuditService:
    def __init__(self):
        self.audit_repository = AuditRepository()

    async def get_all_audit_logs(self) -> List[Dict[str, Any]]:
        """Fetch all system audit records."""
        logs = await self.audit_repository.find_all()
        return [self.map_to_response(al) for al in logs]

    def map_to_response(self, al: Dict[str, Any]) -> Dict[str, Any]:
        """Convert audit log fields to camelCase structures and resolve targets."""
        target = "System"
        details = ""
        
        payload = al["payload"]
        if payload:
            try:
                p = json.loads(payload) if isinstance(payload, str) else payload
                if "email" in p:
                    target = p["email"]
                elif "name" in p:
                    target = p["name"]
                elif "target_user_id" in p:
                    target = f"User ID: {p['target_user_id']}"
                elif "client_id" in p:
                    target = f"Client ID: {p['client_id']}"
                elif "reseller_id" in p:
                    target = f"Reseller ID: {p['reseller_id']}"
                    
                details = json.dumps(p)
            except Exception:
                details = str(payload)
                
        return {
            "id": str(al["id"]),
            "userId": str(al["user_id"]) if al["user_id"] else None,
            "action": al["action"],
            "ipAddress": al["ip_address"] or "",
            "userAgent": al["user_agent"] or "",
            "createdAt": al["created_at"].isoformat() if hasattr(al["created_at"], "isoformat") else al["created_at"],
            "actorEmail": al["actor_email"] or "system@42voice.com",
            "actorRole": (al["actor_role"] or "SYSTEM").lower(),
            "target": target,
            "details": details
        }
