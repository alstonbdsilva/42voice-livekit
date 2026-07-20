"""
Reseller Database Repository.
Handles DB CRUD query executions for partner resellers.
"""

import logging
from typing import List, Dict, Any, Optional
from api import database

logger = logging.getLogger("voice-agent.api.resellers.repositories")


class ResellerRepository:
    private_columns = "id, name, country, commission_pct, contact_email, status, created_at, updated_at"

    async def find_all(self) -> List[Dict[str, Any]]:
        """Find all resellers ordered by join date."""
        return await database.query(
            f"SELECT {self.private_columns} FROM resellers ORDER BY created_at DESC"
        )

    async def find_by_id(self, reseller_id: str) -> Optional[Dict[str, Any]]:
        """Find reseller by ID."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM resellers WHERE id = $1",
            [reseller_id]
        )
        return rows[0] if rows else None

    async def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find reseller by contact email."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM resellers WHERE contact_email = $1",
            [email.lower().strip()]
        )
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Create a new reseller record."""
        email = data["contactEmail"].lower().strip()
        name = data["name"].strip()
        country = data["country"].strip()
        
        rows = await database.query(
            """INSERT INTO resellers (name, country, commission_pct, contact_email, status)
               VALUES ($1, $2, $3, $4, 'active')
               RETURNING id, name, country, commission_pct, contact_email, status, created_at, updated_at""",
            [name, country, data["commissionPct"], email],
            client=client
        )
        return rows[0]

    async def update(self, reseller_id: str, updates: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Update reseller fields dynamically."""
        fields = []
        params = [reseller_id]
        idx = 2
        
        fields_mapping = {
            "name": "name",
            "country": "country",
            "commission_pct": "commission_pct",
            "contact_email": "contact_email",
            "status": "status"
        }
        
        for key, col in fields_mapping.items():
            if key in updates and updates[key] is not None:
                fields.append(f"{col} = ${idx}")
                val = updates[key]
                if key in ["name", "country"]:
                    val = val.strip()
                elif key == "contact_email":
                    val = val.lower().strip()
                params.append(val)
                idx += 1
                
        if not fields:
            reseller = await self.find_by_id(reseller_id)
            if not reseller:
                raise ValueError("Reseller not found")
            return reseller
            
        fields.append("updated_at = CURRENT_TIMESTAMP")
        
        sql = f"""
            UPDATE resellers 
            SET {", ".join(fields)} 
            WHERE id = $1 
            RETURNING id, name, country, commission_pct, contact_email, status, created_at, updated_at
        """
        rows = await database.query(sql, params, client=client)
        return rows[0]

    async def delete(self, reseller_id: str, client: Optional[Any] = None) -> None:
        """Delete reseller by ID."""
        await database.query("DELETE FROM resellers WHERE id = $1", [reseller_id], client=client)
