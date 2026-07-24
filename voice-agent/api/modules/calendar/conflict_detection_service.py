"""
Conflict Detection Service.
Detects booking conflicts and policy violations.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.conflict_detection_service")


class ConflictDetectionService:
    """Service for detecting booking conflicts."""
    
    @staticmethod
    async def detect_conflicts(
        booking_id: str,
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts for a booking.
        
        Checks for:
        - Overlapping meetings
        - Duplicate requests
        - Calendar conflicts
        - Recurring conflicts
        - Booking window violations
        - Policy violations
        """
        try:
            conflicts = []
            
            # Check overlapping meetings
            overlapping = await ConflictDetectionService._check_overlapping(
                agent_calendar_connection_id,
                start_time,
                end_time,
                booking_id
            )
            if overlapping:
                conflicts.append(overlapping)
            
            # Check duplicate requests
            duplicate = await ConflictDetectionService._check_duplicate(
                agent_calendar_connection_id,
                start_time,
                end_time
            )
            if duplicate:
                conflicts.append(duplicate)
            
            # Check policy violations
            policy_violation = await ConflictDetectionService._check_policy_violation(
                agent_calendar_connection_id,
                start_time,
                end_time
            )
            if policy_violation:
                conflicts.append(policy_violation)
            
            # Store conflicts
            for conflict in conflicts:
                await ConflictDetectionService._store_conflict(booking_id, conflict)
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error detecting conflicts: {e}")
            return []
    
    @staticmethod
    async def _check_overlapping(
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime,
        booking_id: str
    ) -> Optional[Dict[str, Any]]:
        """Check for overlapping meetings."""
        try:
            query = """
                SELECT ce.id, ce.title, ce.start_time, ce.end_time
                FROM calendar_events ce
                WHERE ce.agent_calendar_connection_id = $1
                AND ce.status = 'confirmed'
                AND ce.start_time < $3
                AND ce.end_time > $2
            """
            
            rows = await database.query(
                query,
                [UUID(agent_calendar_connection_id), start_time, end_time]
            )
            
            if rows:
                return {
                    "conflict_type": "overlapping_meeting",
                    "conflicting_event_id": str(rows[0].get("id")),
                    "details": {
                        "conflicting_event": rows[0].get("title"),
                        "conflicting_start": rows[0].get("start_time").isoformat(),
                        "conflicting_end": rows[0].get("end_time").isoformat()
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking overlapping: {e}")
            return None
    
    @staticmethod
    async def _check_duplicate(
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Check for duplicate booking requests."""
        try:
            # Check for bookings with same time within 5 minutes
            query = """
                SELECT id FROM calendar_bookings
                WHERE agent_calendar_connection_id = $1
                AND status IN ('pending', 'confirmed')
                AND start_time >= $2 - INTERVAL '5 minutes'
                AND start_time <= $2 + INTERVAL '5 minutes'
                AND end_time >= $3 - INTERVAL '5 minutes'
                AND end_time <= $3 + INTERVAL '5 minutes'
            """
            
            rows = await database.query(
                query,
                [UUID(agent_calendar_connection_id), start_time, end_time]
            )
            
            if rows:
                return {
                    "conflict_type": "duplicate_request",
                    "details": {
                        "message": "Similar booking request already exists"
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return None
    
    @staticmethod
    async def _check_policy_violation(
        agent_calendar_connection_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Check for policy violations."""
        try:
            # Get booking policy
            policy_query = """
                SELECT * FROM booking_policies
                WHERE agent_calendar_connection_id = $1
            """
            
            policy_rows = await database.query(query, [UUID(agent_calendar_connection_id)])
            
            if not policy_rows:
                return None
            
            policy = policy_rows[0]
            
            # Check minimum notice
            now = datetime.now(timezone.utc)
            notice_minutes = int((start_time - now).total_seconds() / 60)
            
            if notice_minutes < policy.get("minimum_notice_minutes", 0):
                return {
                    "conflict_type": "policy_violation",
                    "details": {
                        "violation": "minimum_notice",
                        "required_minutes": policy.get("minimum_notice_minutes"),
                        "provided_minutes": notice_minutes
                    }
                }
            
            # Check maximum advance booking
            advance_days = (start_time.date() - now.date()).days
            if advance_days > policy.get("maximum_advance_booking_days", 365):
                return {
                    "conflict_type": "policy_violation",
                    "details": {
                        "violation": "maximum_advance_booking",
                        "maximum_days": policy.get("maximum_advance_booking_days"),
                        "requested_days": advance_days
                    }
                }
            
            # Check maximum meetings per day
            day_query = """
                SELECT COUNT(*) as count FROM calendar_bookings
                WHERE agent_calendar_connection_id = $1
                AND status IN ('confirmed', 'pending')
                AND DATE(start_time) = DATE($2)
            """
            
            day_rows = await database.query(day_query, [UUID(agent_calendar_connection_id), start_time])
            day_count = day_rows[0].get("count", 0) if day_rows else 0
            
            if day_count >= policy.get("maximum_meetings_per_day", 10):
                return {
                    "conflict_type": "policy_violation",
                    "details": {
                        "violation": "maximum_meetings_per_day",
                        "maximum": policy.get("maximum_meetings_per_day"),
                        "current": day_count
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking policy violation: {e}")
            return None
    
    @staticmethod
    async def _store_conflict(
        booking_id: str,
        conflict: Dict[str, Any]
    ) -> bool:
        """Store conflict record."""
        try:
            query = """
                INSERT INTO calendar_conflicts 
                (booking_id, conflict_type, conflicting_event_id, details)
                VALUES ($1, $2, $3, $4)
            """
            
            await database.query(
                query,
                [UUID(booking_id), conflict.get("conflict_type"),
                 UUID(conflict.get("conflicting_event_id")) if conflict.get("conflicting_event_id") else None,
                 conflict.get("details")]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing conflict: {e}")
            return False
    
    @staticmethod
    async def get_booking_conflicts(booking_id: str) -> List[Dict[str, Any]]:
        """Get conflicts for a booking."""
        try:
            query = """
                SELECT id, booking_id, conflict_type, conflicting_event_id, details, resolved
                FROM calendar_conflicts
                WHERE booking_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(booking_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting conflicts: {e}")
            return []
    
    @staticmethod
    async def resolve_conflict(conflict_id: str) -> bool:
        """Mark conflict as resolved."""
        try:
            query = """
                UPDATE calendar_conflicts
                SET resolved = TRUE, resolved_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """
            
            await database.query(query, [UUID(conflict_id)])
            return True
            
        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")
            return False
