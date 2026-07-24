"""
Distributed Lock Service.
Prevents concurrent operations on shared resources.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.distributed_lock_service")


class DistributedLockService:
    """Service for distributed locking."""
    
    LOCK_TIMEOUT_SECONDS = 30
    
    @staticmethod
    async def acquire_lock(
        resource_type: str,
        resource_id: str,
        owner_id: str,
        timeout_seconds: int = LOCK_TIMEOUT_SECONDS
    ) -> Optional[str]:
        """Acquire distributed lock."""
        try:
            lock_key = f"{resource_type}:{resource_id}"
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
            
            query = """
                INSERT INTO distributed_locks 
                (lock_key, owner_id, resource_type, resource_id, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (lock_key, resource_type, resource_id) DO NOTHING
                RETURNING id
            """
            
            rows = await database.query(
                query,
                [lock_key, owner_id, resource_type, resource_id, expires_at]
            )
            
            if rows:
                return str(rows[0].get("id"))
            
            return None
            
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return None
    
    @staticmethod
    async def release_lock(
        resource_type: str,
        resource_id: str,
        owner_id: str
    ) -> bool:
        """Release distributed lock."""
        try:
            query = """
                DELETE FROM distributed_locks
                WHERE resource_type = $1 AND resource_id = $2 AND owner_id = $3
            """
            
            await database.query(query, [resource_type, resource_id, owner_id])
            return True
            
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            return False
    
    @staticmethod
    async def is_locked(resource_type: str, resource_id: str) -> bool:
        """Check if resource is locked."""
        try:
            query = """
                SELECT id FROM distributed_locks
                WHERE resource_type = $1 AND resource_id = $2
                AND expires_at > CURRENT_TIMESTAMP
            """
            
            rows = await database.query(query, [resource_type, resource_id])
            return len(rows) > 0
            
        except Exception as e:
            logger.error(f"Error checking lock: {e}")
            return False
    
    @staticmethod
    async def cleanup_expired_locks() -> int:
        """Clean up expired locks."""
        try:
            query = """
                DELETE FROM distributed_locks
                WHERE expires_at < CURRENT_TIMESTAMP
            """
            
            result = await database.query(query)
            return result.rowcount if hasattr(result, 'rowcount') else 0
            
        except Exception as e:
            logger.error(f"Error cleaning up locks: {e}")
            return 0
