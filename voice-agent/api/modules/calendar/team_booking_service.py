"""
Team Booking Service.
Supports booking across agent groups.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database
from api.modules.calendar.calendar_service_enhanced import EnhancedCalendarService
from api.modules.calendar.calendar_selection_service import CalendarSelectionService

logger = logging.getLogger("voice-agent.api.modules.calendar.team_booking_service")


class TeamBookingService:
    """Service for booking across agent groups."""
    
    @staticmethod
    async def book_with_team(
        session_id: str,
        agent_group_id: str,
        customer_name: str,
        customer_email: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str,
        customer_phone: Optional[str] = None,
        strategy: str = "least_busy"
    ) -> Optional[Dict[str, Any]]:
        """
        Book meeting with agent group.
        
        Strategies:
        - round_robin: Rotate through agents
        - least_busy: Use least booked agent
        - priority: Use highest priority agent
        - workflow_defined: Use workflow-specified agent
        """
        try:
            # Get agents in group
            query = """
                SELECT agent_id FROM agent_group_members
                WHERE agent_group_id = $1
                ORDER BY priority ASC
            """
            
            rows = await database.query(query, [UUID(agent_group_id)])
            
            if not rows:
                logger.warning(f"No agents in group: {agent_group_id}")
                return None
            
            agent_ids = [str(row.get("agent_id")) for row in rows]
            
            # Select agent based on strategy
            selected_agent_id = await TeamBookingService._select_agent(
                agent_ids,
                strategy,
                start_time,
                end_time
            )
            
            if not selected_agent_id:
                logger.warning(f"Could not select agent from group: {agent_group_id}")
                return None
            
            # Book with selected agent
            booking = await EnhancedCalendarService.book_meeting_safe(
                session_id,
                selected_agent_id,
                customer_name,
                customer_email,
                start_time,
                end_time,
                timezone,
                customer_phone
            )
            
            return booking
            
        except Exception as e:
            logger.error(f"Error booking with team: {e}")
            return None
    
    @staticmethod
    async def get_team_availability(
        agent_group_id: str,
        start_date: datetime,
        end_date: datetime,
        strategy: str = "least_busy"
    ) -> List[Dict[str, Any]]:
        """
        Get earliest available slot across team.
        
        Returns slots with agent information.
        """
        try:
            # Get agents in group
            query = """
                SELECT agent_id FROM agent_group_members
                WHERE agent_group_id = $1
                ORDER BY priority ASC
            """
            
            rows = await database.query(query, [UUID(agent_group_id)])
            
            if not rows:
                return []
            
            agent_ids = [str(row.get("agent_id")) for row in rows]
            
            # Get availability for each agent
            all_slots = []
            
            for agent_id in agent_ids:
                slots = await EnhancedCalendarService.get_available_slots_safe(
                    agent_id,
                    start_date,
                    end_date
                )
                
                # Add agent info to slots
                for slot in slots:
                    slot["agent_id"] = agent_id
                    all_slots.append(slot)
            
            # Sort by start time
            all_slots.sort(key=lambda x: x.get("start", ""))
            
            return all_slots
            
        except Exception as e:
            logger.error(f"Error getting team availability: {e}")
            return []
    
    @staticmethod
    async def _select_agent(
        agent_ids: List[str],
        strategy: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[str]:
        """Select agent from group based on strategy."""
        try:
            if strategy == "round_robin":
                return await TeamBookingService._select_round_robin(agent_ids)
            
            elif strategy == "least_busy":
                return await TeamBookingService._select_least_busy(agent_ids, start_time, end_time)
            
            elif strategy == "priority":
                return agent_ids[0] if agent_ids else None
            
            else:
                return agent_ids[0] if agent_ids else None
            
        except Exception as e:
            logger.error(f"Error selecting agent: {e}")
            return agent_ids[0] if agent_ids else None
    
    @staticmethod
    async def _select_round_robin(agent_ids: List[str]) -> Optional[str]:
        """Select agent using round-robin."""
        try:
            if not agent_ids:
                return None
            
            # Get last booked agent
            query = """
                SELECT agent_id FROM calendar_bookings
                WHERE agent_calendar_connection_id IN (
                    SELECT id FROM agent_calendar_connections
                    WHERE agent_id = ANY($1::uuid[])
                )
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            agent_uuids = [UUID(aid) for aid in agent_ids]
            rows = await database.query(query, [agent_uuids])
            
            if not rows:
                return agent_ids[0]
            
            last_agent = str(rows[0].get("agent_id"))
            
            # Find next agent
            try:
                idx = agent_ids.index(last_agent)
                return agent_ids[(idx + 1) % len(agent_ids)]
            except ValueError:
                return agent_ids[0]
            
        except Exception as e:
            logger.error(f"Error selecting round-robin: {e}")
            return agent_ids[0] if agent_ids else None
    
    @staticmethod
    async def _select_least_busy(
        agent_ids: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Optional[str]:
        """Select least busy agent."""
        try:
            least_busy_agent = None
            min_bookings = float('inf')
            
            for agent_id in agent_ids:
                # Count future bookings for this agent
                query = """
                    SELECT COUNT(*) as count FROM calendar_bookings
                    WHERE agent_calendar_connection_id IN (
                        SELECT id FROM agent_calendar_connections
                        WHERE agent_id = $1
                    )
                    AND status IN ('confirmed', 'pending')
                    AND start_time >= CURRENT_TIMESTAMP
                """
                
                rows = await database.query(query, [UUID(agent_id)])
                count = rows[0].get("count", 0) if rows else 0
                
                if count < min_bookings:
                    min_bookings = count
                    least_busy_agent = agent_id
            
            return least_busy_agent
            
        except Exception as e:
            logger.error(f"Error selecting least busy: {e}")
            return agent_ids[0] if agent_ids else None
