"""
Calendar Health Service.
Monitors calendar health and synchronization status.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_health_service")


class CalendarHealthService:
    """Service for monitoring calendar health."""
    
    @staticmethod
    async def initialize_health(calendar_connection_id: str) -> Optional[Dict[str, Any]]:
        """Initialize health record for calendar."""
        try:
            query = """
                INSERT INTO calendar_health 
                (calendar_connection_id, oauth_status, webhook_status, sync_status)
                VALUES ($1, 'active', 'active', 'healthy')
                ON CONFLICT (calendar_connection_id) DO NOTHING
                RETURNING calendar_connection_id, oauth_status, webhook_status, sync_status, created_at
            """
            
            rows = await database.query(query, [UUID(calendar_connection_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing health: {e}")
            return None
    
    @staticmethod
    async def get_health(calendar_connection_id: str) -> Optional[Dict[str, Any]]:
        """Get health status for calendar."""
        try:
            query = """
                SELECT calendar_connection_id, oauth_status, webhook_status, sync_status,
                       last_successful_sync, last_failed_sync, last_error,
                       rate_limit_remaining, rate_limit_reset_at, consecutive_failures,
                       created_at, updated_at
                FROM calendar_health
                WHERE calendar_connection_id = $1
            """
            
            rows = await database.query(query, [UUID(calendar_connection_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting health: {e}")
            return None
    
    @staticmethod
    async def update_oauth_status(
        calendar_connection_id: str,
        status: str,
        error: Optional[str] = None
    ) -> bool:
        """Update OAuth status."""
        try:
            query = """
                UPDATE calendar_health
                SET oauth_status = $1, last_error = $2, updated_at = CURRENT_TIMESTAMP
                WHERE calendar_connection_id = $3
            """
            
            await database.query(query, [status, error, UUID(calendar_connection_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating OAuth status: {e}")
            return False
    
    @staticmethod
    async def update_webhook_status(
        calendar_connection_id: str,
        status: str,
        error: Optional[str] = None
    ) -> bool:
        """Update webhook status."""
        try:
            query = """
                UPDATE calendar_health
                SET webhook_status = $1, last_error = $2, updated_at = CURRENT_TIMESTAMP
                WHERE calendar_connection_id = $3
            """
            
            await database.query(query, [status, error, UUID(calendar_connection_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating webhook status: {e}")
            return False
    
    @staticmethod
    async def record_sync_success(
        calendar_connection_id: str,
        events_synced: int = 0,
        events_created: int = 0,
        events_updated: int = 0,
        events_deleted: int = 0
    ) -> bool:
        """Record successful sync."""
        try:
            query = """
                UPDATE calendar_health
                SET sync_status = 'healthy',
                    last_successful_sync = CURRENT_TIMESTAMP,
                    consecutive_failures = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE calendar_connection_id = $1
            """
            
            await database.query(query, [UUID(calendar_connection_id)])
            
            # Log sync
            await CalendarHealthService._log_sync(
                calendar_connection_id,
                'completed',
                events_synced,
                events_created,
                events_updated,
                events_deleted
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording sync success: {e}")
            return False
    
    @staticmethod
    async def record_sync_failure(
        calendar_connection_id: str,
        error: str
    ) -> bool:
        """Record failed sync."""
        try:
            # Get current failure count
            health = await CalendarHealthService.get_health(calendar_connection_id)
            failures = (health.get("consecutive_failures", 0) if health else 0) + 1
            
            # Determine sync status
            sync_status = "degraded" if failures < 3 else "unhealthy"
            
            query = """
                UPDATE calendar_health
                SET sync_status = $1,
                    last_failed_sync = CURRENT_TIMESTAMP,
                    last_error = $2,
                    consecutive_failures = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE calendar_connection_id = $4
            """
            
            await database.query(query, [sync_status, error, failures, UUID(calendar_connection_id)])
            
            # Log sync failure
            await CalendarHealthService._log_sync(
                calendar_connection_id,
                'failed',
                error_message=error
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording sync failure: {e}")
            return False
    
    @staticmethod
    async def update_rate_limit(
        calendar_connection_id: str,
        remaining: int,
        reset_at: Optional[datetime] = None
    ) -> bool:
        """Update rate limit information."""
        try:
            query = """
                UPDATE calendar_health
                SET rate_limit_remaining = $1, rate_limit_reset_at = $2, updated_at = CURRENT_TIMESTAMP
                WHERE calendar_connection_id = $3
            """
            
            await database.query(query, [remaining, reset_at, UUID(calendar_connection_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")
            return False
    
    @staticmethod
    async def _log_sync(
        calendar_connection_id: str,
        status: str,
        events_synced: int = 0,
        events_created: int = 0,
        events_updated: int = 0,
        events_deleted: int = 0,
        error_message: Optional[str] = None
    ) -> bool:
        """Log sync operation."""
        try:
            query = """
                INSERT INTO calendar_sync_logs 
                (calendar_connection_id, sync_type, status, events_synced, 
                 events_created, events_updated, events_deleted, error_message, completed_at)
                VALUES ($1, 'incremental', $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
            """
            
            await database.query(
                query,
                [UUID(calendar_connection_id), status, events_synced, events_created,
                 events_updated, events_deleted, error_message]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging sync: {e}")
            return False
    
    @staticmethod
    async def get_unhealthy_calendars() -> list:
        """Get all unhealthy calendars."""
        try:
            query = """
                SELECT calendar_connection_id, oauth_status, webhook_status, sync_status,
                       last_error, consecutive_failures
                FROM calendar_health
                WHERE sync_status IN ('degraded', 'unhealthy')
                OR oauth_status IN ('expired', 'revoked', 'error')
                ORDER BY consecutive_failures DESC
            """
            
            rows = await database.query(query)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting unhealthy calendars: {e}")
            return []
