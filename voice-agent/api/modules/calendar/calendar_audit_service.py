"""
Calendar Audit Service.
Tracks all calendar operations for compliance and debugging.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_audit_service")


class CalendarAuditService:
    """Service for auditing calendar operations."""
    
    @staticmethod
    async def log_action(
        action: str,
        actor_type: str,
        actor_id: Optional[str] = None,
        calendar_connection_id: Optional[str] = None,
        agent_calendar_connection_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        details: Optional[Dict] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Log a calendar action."""
        try:
            query = """
                INSERT INTO calendar_audit_logs 
                (calendar_connection_id, agent_calendar_connection_id, booking_id,
                 action, actor_type, actor_id, details, status, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, action, actor_type, status, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(calendar_connection_id) if calendar_connection_id else None,
                 UUID(agent_calendar_connection_id) if agent_calendar_connection_id else None,
                 UUID(booking_id) if booking_id else None,
                 action, actor_type, actor_id, details, status, error_message]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error logging action: {e}")
            return None
    
    @staticmethod
    async def log_connected(
        calendar_connection_id: str,
        actor_id: str,
        provider: str
    ) -> bool:
        """Log calendar connection."""
        try:
            await CalendarAuditService.log_action(
                action="connected",
                actor_type="user",
                actor_id=actor_id,
                calendar_connection_id=calendar_connection_id,
                details={"provider": provider}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging connected: {e}")
            return False
    
    @staticmethod
    async def log_disconnected(
        calendar_connection_id: str,
        actor_id: str
    ) -> bool:
        """Log calendar disconnection."""
        try:
            await CalendarAuditService.log_action(
                action="disconnected",
                actor_type="user",
                actor_id=actor_id,
                calendar_connection_id=calendar_connection_id
            )
            return True
        except Exception as e:
            logger.error(f"Error logging disconnected: {e}")
            return False
    
    @staticmethod
    async def log_booking_created(
        booking_id: str,
        agent_calendar_connection_id: str,
        customer_email: str
    ) -> bool:
        """Log booking creation."""
        try:
            await CalendarAuditService.log_action(
                action="booking_created",
                actor_type="system",
                agent_calendar_connection_id=agent_calendar_connection_id,
                booking_id=booking_id,
                details={"customer_email": customer_email}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging booking created: {e}")
            return False
    
    @staticmethod
    async def log_booking_updated(
        booking_id: str,
        agent_calendar_connection_id: str,
        changes: Dict
    ) -> bool:
        """Log booking update."""
        try:
            await CalendarAuditService.log_action(
                action="booking_updated",
                actor_type="system",
                agent_calendar_connection_id=agent_calendar_connection_id,
                booking_id=booking_id,
                details={"changes": changes}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging booking updated: {e}")
            return False
    
    @staticmethod
    async def log_booking_cancelled(
        booking_id: str,
        agent_calendar_connection_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """Log booking cancellation."""
        try:
            await CalendarAuditService.log_action(
                action="booking_cancelled",
                actor_type="system",
                agent_calendar_connection_id=agent_calendar_connection_id,
                booking_id=booking_id,
                details={"reason": reason}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging booking cancelled: {e}")
            return False
    
    @staticmethod
    async def log_webhook_received(
        calendar_connection_id: str,
        event_type: str,
        details: Dict
    ) -> bool:
        """Log webhook reception."""
        try:
            await CalendarAuditService.log_action(
                action="webhook_received",
                actor_type="webhook",
                calendar_connection_id=calendar_connection_id,
                details={"event_type": event_type, **details}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging webhook received: {e}")
            return False
    
    @staticmethod
    async def log_token_refreshed(
        calendar_connection_id: str,
        success: bool,
        error: Optional[str] = None
    ) -> bool:
        """Log token refresh."""
        try:
            await CalendarAuditService.log_action(
                action="token_refreshed",
                actor_type="system",
                calendar_connection_id=calendar_connection_id,
                status="success" if success else "failed",
                error_message=error
            )
            return True
        except Exception as e:
            logger.error(f"Error logging token refreshed: {e}")
            return False
    
    @staticmethod
    async def log_sync_completed(
        calendar_connection_id: str,
        events_synced: int,
        sync_type: str = "incremental"
    ) -> bool:
        """Log sync completion."""
        try:
            await CalendarAuditService.log_action(
                action="sync_completed",
                actor_type="system",
                calendar_connection_id=calendar_connection_id,
                details={"events_synced": events_synced, "sync_type": sync_type}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging sync completed: {e}")
            return False
    
    @staticmethod
    async def log_booking_failed(
        agent_calendar_connection_id: str,
        customer_email: str,
        error: str
    ) -> bool:
        """Log booking failure."""
        try:
            await CalendarAuditService.log_action(
                action="booking_failed",
                actor_type="system",
                agent_calendar_connection_id=agent_calendar_connection_id,
                details={"customer_email": customer_email},
                status="failed",
                error_message=error
            )
            return True
        except Exception as e:
            logger.error(f"Error logging booking failed: {e}")
            return False
    
    @staticmethod
    async def log_slot_reserved(
        agent_calendar_connection_id: str,
        customer_email: str
    ) -> bool:
        """Log slot reservation."""
        try:
            await CalendarAuditService.log_action(
                action="slot_reserved",
                actor_type="system",
                agent_calendar_connection_id=agent_calendar_connection_id,
                details={"customer_email": customer_email}
            )
            return True
        except Exception as e:
            logger.error(f"Error logging slot reserved: {e}")
            return False
    
    @staticmethod
    async def log_conflict_detected(
        booking_id: str,
        conflict_type: str,
        details: Dict
    ) -> bool:
        """Log conflict detection."""
        try:
            await CalendarAuditService.log_action(
                action="conflict_detected",
                actor_type="system",
                booking_id=booking_id,
                details={"conflict_type": conflict_type, **details},
                status="warning"
            )
            return True
        except Exception as e:
            logger.error(f"Error logging conflict detected: {e}")
            return False
    
    @staticmethod
    async def get_audit_logs(
        calendar_connection_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """Get audit logs with optional filtering."""
        try:
            query = "SELECT * FROM calendar_audit_logs WHERE 1=1"
            params = []
            
            if calendar_connection_id:
                query += " AND calendar_connection_id = $" + str(len(params) + 1)
                params.append(UUID(calendar_connection_id))
            
            if booking_id:
                query += " AND booking_id = $" + str(len(params) + 1)
                params.append(UUID(booking_id))
            
            if action:
                query += " AND action = $" + str(len(params) + 1)
                params.append(action)
            
            query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await database.query(query, params)
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return []
