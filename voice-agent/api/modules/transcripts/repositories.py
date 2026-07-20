"""
Transcripts Database Repository.
Stores full transcript dialogues and action item lists.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from api import database

logger = logging.getLogger("voice-agent.api.transcripts.repositories")


class TranscriptRepository:
    private_columns = "id, conversation_id, full_text, lines, action_items, created_at"

    async def find_by_conversation_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the transcript corresponding to a conversation ID."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM transcripts WHERE conversation_id = $1",
            [conversation_id]
        )
        return rows[0] if rows else None

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Save a new transcript log."""
        # Convert lists to json string for postgres jsonb input
        lines_json = json.dumps(data["lines"])
        action_items_json = json.dumps(data["actionItems"])
        
        rows = await database.query(
            f"""INSERT INTO transcripts (conversation_id, full_text, lines, action_items)
               VALUES ($1, $2, $3, $4)
               RETURNING {self.private_columns}""",
            [
                data["conversationId"],
                data["fullText"].strip(),
                lines_json,
                action_items_json
            ],
            client=client
        )
        return rows[0]
