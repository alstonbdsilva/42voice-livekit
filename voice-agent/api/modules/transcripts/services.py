"""
Transcripts Service.
Queries and formats dialogue transcript records.
"""

import json
import logging
from typing import Dict, Any, Optional
from api.modules.transcripts.repositories import TranscriptRepository

logger = logging.getLogger("voice-agent.api.transcripts.services")


class TranscriptsService:
    def __init__(self):
        self.transcript_repository = TranscriptRepository()

    async def get_transcript_by_conversation_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch transcript logged for a specific conversation session."""
        transcript = await self.transcript_repository.find_by_conversation_id(conversation_id)
        if not transcript:
            return None
        return self.map_to_response(transcript)

    def map_to_response(self, t: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case database columns to React DataTable camelCase bindings."""
        # Convert JSON strings if asyncpg returned them as raw text (usually parsed automatically)
        lines = t["lines"]
        if isinstance(lines, str):
            lines = json.loads(lines)
            
        action_items = t["action_items"]
        if isinstance(action_items, str):
            action_items = json.loads(action_items)
            
        return {
            "id": str(t["id"]),
            "fullText": t["full_text"],
            "lines": lines,
            "actionItems": action_items,
            "createdAt": t["created_at"].isoformat() if hasattr(t["created_at"], "isoformat") else t["created_at"],
            "conversationId": str(t["conversation_id"])
        }
