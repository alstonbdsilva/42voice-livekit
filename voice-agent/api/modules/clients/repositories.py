"""
Clients Database Repository.
Exposes database CRUD wrappers for clients.
"""

import logging
from typing import List, Dict, Any, Optional
from api import database

logger = logging.getLogger("voice-agent.api.clients.repositories")


class ClientRepository:
    private_columns = "id, name, industry, country, monthly_recurring, contact_email, status, reseller_id, created_at, updated_at"

    async def find_all(self, reseller_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all clients, optionally filtered by Reseller ID."""
        if reseller_id:
            return await database.query(
                f"SELECT {self.private_columns} FROM clients WHERE reseller_id = $1 ORDER BY created_at DESC",
                [reseller_id]
            )
        return await database.query(
            f"SELECT {self.private_columns} FROM clients ORDER BY created_at DESC"
        )

    async def find_by_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Find a single client by ID."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM clients WHERE id = $1",
            [client_id]
        )
        return rows[0] if rows else None

    async def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find client by contact email."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM clients WHERE contact_email = $1",
            [email.lower().strip()]
        )
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Create a new client record."""
        email = data["contactEmail"].lower().strip()
        name = data["name"].strip()
        raw_industry = data.get("industry")
        industry = raw_industry.strip() if raw_industry else None
        raw_country = data.get("country")
        country = raw_country.strip() if raw_country else None
        
        rows = await database.query(
            f"""INSERT INTO clients (name, industry, country, monthly_recurring, contact_email, status, reseller_id)
               VALUES ($1, $2, $3, $4, $5, 'active', $6)
               RETURNING {self.private_columns}""",
            [
                name,
                industry,
                country,
                data.get("monthlyRecurring", 0.00),
                email,
                data["resellerId"]
            ],
            client=client
        )
        return rows[0]

    async def update(self, client_id: str, updates: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Update client fields dynamically."""
        field_map = {
            "name": "name",
            "industry": "industry",
            "country": "country",
            "monthlyRecurring": "monthly_recurring",
            "contactEmail": "contact_email",
            "status": "status",
            "resellerId": "reseller_id"
        }
        
        fields = []
        params = [client_id]
        idx = 2
        
        for key, col in field_map.items():
            if key in updates and updates[key] is not None:
                fields.append(f"{col} = ${idx}")
                val = updates[key]
                if key in ["name", "industry", "country"]:
                    val = val.strip()
                elif key == "contactEmail":
                    val = val.lower().strip()
                params.append(val)
                idx += 1
                
        if not fields:
            rows = await database.query(f"SELECT {self.private_columns} FROM clients WHERE id = $1", [client_id])
            return rows[0]
            
        fields.append("updated_at = CURRENT_TIMESTAMP")
        
        sql = f"""
            UPDATE clients SET {", ".join(fields)}
            WHERE id = $1
            RETURNING {self.private_columns}
        """
        rows = await database.query(sql, params, client=client)
        return rows[0]

    async def delete(self, client_id: str, client: Optional[Any] = None) -> None:
        """Delete client by ID."""
        await database.query("DELETE FROM clients WHERE id = $1", [client_id], client=client)
