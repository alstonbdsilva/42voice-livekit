"""
Calendar Selection Service.
Manages calendar selection strategy for agents with multiple calendars.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.calendar.calendar_selection_service")


class CalendarSelectionService:
    """Service for selecting calendars based on strategy."""
    
    @staticmethod
    async def set_strategy(
        agent_id: str,
        strategy: str,
        configuration: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Set calendar selection strategy for agent."""
        try:
            query = """
                INSERT INTO calendar_selection_strategies 
                (agent_id, strategy, configuration)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id) DO UPDATE
                SET strategy = $2, configuration = $3, updated_at = CURRENT_TIMESTAMP
                RETURNING id, agent_id, strategy, configuration, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [UUID(agent_id), strategy, configuration]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error setting strategy: {e}")
            return None
    
    @staticmethod
    async def get_strategy(agent_id: str) -> Optional[Dict[str, Any]]:
        """Get calendar selection strategy for agent."""
        try:
            query = """
                SELECT id, agent_id, strategy, configuration, created_at, updated_at
                FROM calendar_selection_strategies
                WHERE agent_id = $1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting strategy: {e}")
            return None
    
    @staticmethod
    async def select_calendar(
        agent_id: str,
        manual_selection: Optional[str] = None,
        workflow_context: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Select calendar for agent based on strategy.
        
        Returns agent_calendar_connection details.
        """
        try:
            # Get strategy
            strategy_row = await CalendarSelectionService.get_strategy(agent_id)
            strategy = strategy_row.get("strategy", "primary") if strategy_row else "primary"
            
            # Get agent calendars
            query = """
                SELECT acc.*, cc.provider, cc.calendar_id, cc.calendar_name
                FROM agent_calendar_connections acc
                JOIN calendar_connections cc ON acc.calendar_connection_id = cc.id
                WHERE acc.agent_id = $1 AND acc.booking_enabled = TRUE
                ORDER BY acc.is_primary DESC, acc.created_at ASC
            """
            
            calendars = await database.query(query, [UUID(agent_id)])
            
            if not calendars:
                return None
            
            # Select based on strategy
            if strategy == "primary":
                return CalendarSelectionService._select_primary(calendars)
            
            elif strategy == "round_robin":
                return await CalendarSelectionService._select_round_robin(agent_id, calendars)
            
            elif strategy == "least_busy":
                return await CalendarSelectionService._select_least_busy(calendars)
            
            elif strategy == "manual":
                if manual_selection:
                    return CalendarSelectionService._select_manual(calendars, manual_selection)
                return CalendarSelectionService._select_primary(calendars)
            
            elif strategy == "workflow_defined":
                if workflow_context and "calendar_id" in workflow_context:
                    return CalendarSelectionService._select_manual(calendars, workflow_context["calendar_id"])
                return CalendarSelectionService._select_primary(calendars)
            
            else:
                return CalendarSelectionService._select_primary(calendars)
            
        except Exception as e:
            logger.error(f"Error selecting calendar: {e}")
            return None
    
    @staticmethod
    def _select_primary(calendars: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select primary calendar."""
        try:
            for cal in calendars:
                if cal.get("is_primary"):
                    return cal
            return calendars[0] if calendars else None
        except Exception as e:
            logger.error(f"Error selecting primary: {e}")
            return None
    
    @staticmethod
    async def _select_round_robin(agent_id: str, calendars: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select calendar using round-robin."""
        try:
            if not calendars:
                return None
            
            # Get last selected calendar
            query = """
                SELECT calendar_connection_id FROM calendar_bookings
                WHERE agent_calendar_connection_id IN (
                    SELECT id FROM agent_calendar_connections WHERE agent_id = $1
                )
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(agent_id)])
            
            if not rows:
                return calendars[0]
            
            last_calendar_id = rows[0].get("calendar_connection_id")
            
            # Find next calendar
            found = False
            for cal in calendars:
                if found:
                    return cal
                if cal.get("calendar_connection_id") == last_calendar_id:
                    found = True
            
            return calendars[0]
            
        except Exception as e:
            logger.error(f"Error selecting round-robin: {e}")
            return calendars[0] if calendars else None
    
    @staticmethod
    async def _select_least_busy(calendars: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select least busy calendar."""
        try:
            if not calendars:
                return None
            
            least_busy = None
            min_bookings = float('inf')
            
            for cal in calendars:
                # Count bookings for this calendar
                query = """
                    SELECT COUNT(*) as count FROM calendar_bookings
                    WHERE agent_calendar_connection_id = $1
                    AND status IN ('confirmed', 'pending')
                    AND start_time >= CURRENT_TIMESTAMP
                """
                
                rows = await database.query(query, [UUID(cal.get("id"))])
                count = rows[0].get("count", 0) if rows else 0
                
                if count < min_bookings:
                    min_bookings = count
                    least_busy = cal
            
            return least_busy
            
        except Exception as e:
            logger.error(f"Error selecting least busy: {e}")
            return calendars[0] if calendars else None
    
    @staticmethod
    def _select_manual(calendars: List[Dict[str, Any]], calendar_id: str) -> Optional[Dict[str, Any]]:
        """Select specific calendar."""
        try:
            for cal in calendars:
                if str(cal.get("id")) == calendar_id or str(cal.get("calendar_connection_id")) == calendar_id:
                    return cal
            return calendars[0] if calendars else None
        except Exception as e:
            logger.error(f"Error selecting manual: {e}")
            return None
