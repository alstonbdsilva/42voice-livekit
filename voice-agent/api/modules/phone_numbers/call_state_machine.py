"""
Call State Machine.
Manages call state transitions with validation.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.call_state_machine")


class CallStateMachine:
    """State machine for call lifecycle."""
    
    VALID_TRANSITIONS = {
        "initiated": ["ringing", "failed", "cancelled"],
        "ringing": ["answered", "busy", "no_answer", "failed", "cancelled"],
        "answered": ["active", "hold", "transferred", "completed", "failed"],
        "active": ["hold", "transferred", "conference", "completed", "failed"],
        "hold": ["active", "transferred", "completed", "failed"],
        "transferred": ["active", "completed", "failed"],
        "conference": ["active", "completed", "failed"],
        "completed": [],
        "failed": [],
        "busy": [],
        "no_answer": [],
        "cancelled": []
    }
    
    @staticmethod
    async def initialize_call(
        call_id: str,
        phone_number_id: str
    ) -> Optional[Dict[str, Any]]:
        """Initialize call state machine."""
        try:
            query = """
                INSERT INTO call_state_machine 
                (call_id, phone_number_id, current_state, previous_state)
                VALUES ($1, $2, 'initiated', NULL)
                RETURNING id, call_id, current_state, created_at
            """
            
            rows = await database.query(
                query,
                [call_id, UUID(phone_number_id)]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error initializing call state: {e}")
            return None
    
    @staticmethod
    async def transition_state(
        call_id: str,
        to_state: str,
        reason: Optional[str] = None,
        state_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Transition call to new state."""
        try:
            # Get current state
            current_query = """
                SELECT current_state FROM call_state_machine
                WHERE call_id = $1
            """
            
            current_rows = await database.query(current_query, [call_id])
            if not current_rows:
                logger.error(f"Call not found: {call_id}")
                return None
            
            current_state = current_rows[0].get("current_state")
            
            # Validate transition
            if to_state not in CallStateMachine.VALID_TRANSITIONS.get(current_state, []):
                logger.error(f"Invalid transition: {current_state} -> {to_state}")
                return None
            
            # Update state
            update_query = """
                UPDATE call_state_machine
                SET previous_state = current_state,
                    current_state = $1,
                    state_data = $2,
                    transition_reason = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE call_id = $4
                RETURNING id, call_id, current_state, previous_state, updated_at
            """
            
            update_rows = await database.query(
                update_query,
                [to_state, state_data, reason, call_id]
            )
            
            if update_rows:
                # Log transition
                await CallStateMachine._log_transition(
                    call_id,
                    current_state,
                    to_state,
                    reason,
                    state_data
                )
                
                return update_rows[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error transitioning state: {e}")
            return None
    
    @staticmethod
    async def get_call_state(call_id: str) -> Optional[Dict[str, Any]]:
        """Get current call state."""
        try:
            query = """
                SELECT id, call_id, current_state, previous_state, state_data,
                       transition_reason, created_at, updated_at
                FROM call_state_machine
                WHERE call_id = $1
            """
            
            rows = await database.query(query, [call_id])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting call state: {e}")
            return None
    
    @staticmethod
    async def get_transition_history(call_id: str) -> list:
        """Get call state transition history."""
        try:
            query = """
                SELECT from_state, to_state, reason, metadata, created_at
                FROM call_state_transitions
                WHERE call_id = $1
                ORDER BY created_at ASC
            """
            
            rows = await database.query(query, [call_id])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting transition history: {e}")
            return []
    
    @staticmethod
    async def _log_transition(
        call_id: str,
        from_state: str,
        to_state: str,
        reason: Optional[str],
        metadata: Optional[Dict]
    ) -> bool:
        """Log state transition."""
        try:
            query = """
                INSERT INTO call_state_transitions 
                (call_id, from_state, to_state, reason, metadata)
                VALUES ($1, $2, $3, $4, $5)
            """
            
            await database.query(
                query,
                [call_id, from_state, to_state, reason, metadata]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging transition: {e}")
            return False
