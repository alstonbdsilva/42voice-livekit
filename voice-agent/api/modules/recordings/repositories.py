"""
Recordings Database Repository.
Stores S3 filename paths and duration details of recorded calls.
"""

import logging
from typing import List, Dict, Any, Optional
from api import database

logger = logging.getLogger("voice-agent.api.recordings.repositories")


class RecordingRepository:
    private_columns = "id, conversation_id, filename, duration, size, s3_key, created_at"

    async def find_all(self) -> List[Dict[str, Any]]:
        """Fetch all recordings."""
        return await database.query(
            f"SELECT {self.private_columns} FROM recordings ORDER BY created_at DESC"
        )

    async def find_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Find recording details by ID."""
        rows = await database.query(
            f"SELECT {self.private_columns} FROM recordings WHERE id = $1",
            [recording_id]
        )
        return rows[0] if rows else None

    async def find_by_conversation_id(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Find recordings linked to a specific conversation."""
        return await database.query(
            f"SELECT {self.private_columns} FROM recordings WHERE conversation_id = $1 ORDER BY created_at DESC",
            [conversation_id]
        )

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Save a new recording metadata log."""
        rows = await database.query(
            f"""INSERT INTO recordings (conversation_id, filename, duration, size, s3_key)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING {self.private_columns}""",
            [
                data["conversationId"],
                data["filename"].strip(),
                data["duration"],
                data["size"],
                data["s3_key"].strip()
            ],
            client=client
        )
        return rows[0]
