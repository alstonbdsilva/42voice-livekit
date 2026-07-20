"""
Conversations Database Repository.
Stores metadata logs and joins agent profiles.
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from api import database

logger = logging.getLogger("voice-agent.api.conversations.repositories")


class ConversationRepository:
    async def find_all(self, agent_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all conversations, optionally filtered by agent ID and limited."""
        sql = """
            SELECT c.*, a.name as agent_name 
            FROM conversations c
            LEFT JOIN agents a ON c.agent_id = a.id
        """
        params: List[Any] = []
        param_idx = 1
        
        if agent_id:
            sql += f" WHERE c.agent_id = ${param_idx}"
            params.append(agent_id)
            param_idx += 1
            
        sql += " ORDER BY c.started_at DESC"
        
        if limit:
            sql += f" LIMIT ${param_idx}"
            params.append(limit)
            
        return await database.query(sql, params)

    async def find_by_id(self, conversation_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find a single conversation joined with its agent name."""
        rows = await database.query(
            """SELECT c.*, a.name as agent_name 
               FROM conversations c
               LEFT JOIN agents a ON c.agent_id = a.id
               WHERE c.id = $1""",
            [conversation_id],
            client=client
        )
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Insert a new conversation record."""
        rows = await database.query(
            """INSERT INTO conversations (
                agent_id, customer_name, customer_contact, channel, duration, cost, 
                sentiment, outcome, summary, intent, lead_score, sentiment_score, 
                human_handoff, escalation_reason, user_id, client_id
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
               RETURNING id, agent_id, customer_name, customer_contact, channel, duration, cost, 
                         sentiment, outcome, summary, intent, lead_score, sentiment_score, 
                         human_handoff, escalation_reason, started_at, ended_at, user_id, client_id""",
            [
                data["agentId"],
                data["customerName"].strip(),
                data.get("customerContact"),
                data["channel"],
                data["duration"],
                Decimal(str(data["cost"])),
                data["sentiment"],
                data["outcome"],
                data.get("summary"),
                data.get("intent"),
                data.get("leadScore", 0),
                Decimal(str(data.get("sentimentScore", 0.00))),
                data.get("humanHandoff", False),
                data.get("escalationReason"),
                data.get("userId"),
                data.get("clientId")
            ],
            client=client
        )
        return rows[0]
