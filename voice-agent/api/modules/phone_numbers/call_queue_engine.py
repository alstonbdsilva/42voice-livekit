"""
Call Queue Engine.
Manages call queues with priority, FIFO, and callback support.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.call_queue_engine")


class CallQueueEngine:
    """Engine for managing call queues."""
    
    @staticmethod
    async def create_queue(
        phone_number_id: str,
        queue_name: str,
        queue_type: str = "fifo",
        priority_enabled: bool = False,
        max_wait_time_seconds: int = 3600,
        overflow_destination: Optional[str] = None,
        callback_enabled: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Create call queue."""
        try:
            query = """
                INSERT INTO call_queues 
                (phone_number_id, queue_name, queue_type, priority_enabled,
                 max_wait_time_seconds, overflow_destination, callback_enabled)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, phone_number_id, queue_name, queue_type, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(phone_number_id), queue_name, queue_type, priority_enabled,
                 max_wait_time_seconds, overflow_destination, callback_enabled]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating queue: {e}")
            return None
    
    @staticmethod
    async def add_to_queue(
        queue_id: str,
        call_id: str,
        priority: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Add call to queue."""
        try:
            # Get queue
            queue_query = """
                SELECT id, queue_type FROM call_queues WHERE id = $1
            """
            
            queue_rows = await database.query(queue_query, [UUID(queue_id)])
            if not queue_rows:
                return None
            
            queue = queue_rows[0]
            
            # Get next position
            position_query = """
                SELECT MAX(position) as max_position FROM call_queue_members
                WHERE queue_id = $1
            """
            
            position_rows = await database.query(position_query, [UUID(queue_id)])
            next_position = (position_rows[0].get("max_position") or 0) + 1
            
            # Add to queue
            query = """
                INSERT INTO call_queue_members 
                (queue_id, call_id, position, priority, status)
                VALUES ($1, $2, $3, $4, 'waiting')
                RETURNING id, queue_id, call_id, position, priority, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(queue_id), call_id, next_position, priority]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
            return None
    
    @staticmethod
    async def get_queue_position(queue_id: str, call_id: str) -> Optional[int]:
        """Get call position in queue."""
        try:
            query = """
                SELECT position FROM call_queue_members
                WHERE queue_id = $1 AND call_id = $2
            """
            
            rows = await database.query(query, [UUID(queue_id), call_id])
            return rows[0].get("position") if rows else None
            
        except Exception as e:
            logger.error(f"Error getting queue position: {e}")
            return None
    
    @staticmethod
    async def get_estimated_wait_time(queue_id: str) -> int:
        """Get estimated wait time in seconds."""
        try:
            query = """
                SELECT COUNT(*) as queue_size FROM call_queue_members
                WHERE queue_id = $1 AND status = 'waiting'
            """
            
            rows = await database.query(query, [UUID(queue_id)])
            queue_size = rows[0].get("queue_size", 0) if rows else 0
            
            # Assume 5 minutes per call
            return queue_size * 300
            
        except Exception as e:
            logger.error(f"Error getting estimated wait time: {e}")
            return 0
    
    @staticmethod
    async def offer_call(queue_id: str, call_id: str) -> bool:
        """Offer call to agent."""
        try:
            query = """
                UPDATE call_queue_members
                SET status = 'offered', updated_at = CURRENT_TIMESTAMP
                WHERE queue_id = $1 AND call_id = $2
            """
            
            await database.query(query, [UUID(queue_id), call_id])
            return True
            
        except Exception as e:
            logger.error(f"Error offering call: {e}")
            return False
    
    @staticmethod
    async def connect_call(queue_id: str, call_id: str) -> bool:
        """Connect call to agent."""
        try:
            query = """
                UPDATE call_queue_members
                SET status = 'connected', updated_at = CURRENT_TIMESTAMP
                WHERE queue_id = $1 AND call_id = $2
            """
            
            await database.query(query, [UUID(queue_id), call_id])
            return True
            
        except Exception as e:
            logger.error(f"Error connecting call: {e}")
            return False
    
    @staticmethod
    async def abandon_call(queue_id: str, call_id: str) -> bool:
        """Mark call as abandoned."""
        try:
            query = """
                UPDATE call_queue_members
                SET status = 'abandoned', updated_at = CURRENT_TIMESTAMP
                WHERE queue_id = $1 AND call_id = $2
            """
            
            await database.query(query, [UUID(queue_id), call_id])
            return True
            
        except Exception as e:
            logger.error(f"Error abandoning call: {e}")
            return False
    
    @staticmethod
    async def schedule_callback(queue_id: str, call_id: str, callback_time: datetime) -> bool:
        """Schedule callback for call."""
        try:
            query = """
                UPDATE call_queue_members
                SET status = 'callback_scheduled', updated_at = CURRENT_TIMESTAMP
                WHERE queue_id = $1 AND call_id = $2
            """
            
            await database.query(query, [UUID(queue_id), call_id])
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling callback: {e}")
            return False
    
    @staticmethod
    async def get_queue_stats(queue_id: str) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN status = 'waiting' THEN 1 ELSE 0 END) as waiting_calls,
                    SUM(CASE WHEN status = 'offered' THEN 1 ELSE 0 END) as offered_calls,
                    SUM(CASE WHEN status = 'connected' THEN 1 ELSE 0 END) as connected_calls,
                    SUM(CASE WHEN status = 'abandoned' THEN 1 ELSE 0 END) as abandoned_calls,
                    SUM(CASE WHEN status = 'callback_scheduled' THEN 1 ELSE 0 END) as callback_calls,
                    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_wait_seconds
                FROM call_queue_members
                WHERE queue_id = $1
            """
            
            rows = await database.query(query, [UUID(queue_id)])
            
            if rows:
                return rows[0]
            
            return {
                "total_calls": 0,
                "waiting_calls": 0,
                "offered_calls": 0,
                "connected_calls": 0,
                "abandoned_calls": 0,
                "callback_calls": 0,
                "avg_wait_seconds": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    @staticmethod
    async def remove_from_queue(queue_id: str, call_id: str) -> bool:
        """Remove call from queue."""
        try:
            query = """
                DELETE FROM call_queue_members
                WHERE queue_id = $1 AND call_id = $2
            """
            
            await database.query(query, [UUID(queue_id), call_id])
            return True
            
        except Exception as e:
            logger.error(f"Error removing from queue: {e}")
            return False
