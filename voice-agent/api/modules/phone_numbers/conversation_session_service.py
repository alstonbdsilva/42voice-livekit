"""
Conversation Session Service.
Manages conversation sessions with multiple participants and handoffs.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.conversation_session_service")


class ConversationSessionService:
    """Service for managing conversation sessions."""
    
    @staticmethod
    async def create_session(
        session_id: str,
        phone_number_id: Optional[str],
        user_id: str,
        client_id: Optional[str] = None,
        detected_intent: Optional[str] = None,
        intent_confidence: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new conversation session."""
        try:
            query = """
                INSERT INTO conversation_sessions 
                (session_id, phone_number_id, user_id, client_id, detected_intent, intent_confidence)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, session_id, phone_number_id, user_id, client_id, 
                         detected_intent, intent_confidence, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [session_id, UUID(phone_number_id) if phone_number_id else None,
                 UUID(user_id), UUID(client_id) if client_id else None,
                 detected_intent, intent_confidence]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating conversation session: {e}")
            return None
    
    @staticmethod
    async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation session details."""
        try:
            query = """
                SELECT id, session_id, phone_number_id, user_id, client_id,
                       current_agent_id, current_capability_id, current_workflow_id,
                       detected_intent, intent_confidence,
                       conversation_history, session_state, extracted_entities,
                       user_context, workflow_context, created_at, updated_at
                FROM conversation_sessions
                WHERE session_id = $1
            """
            
            rows = await database.query(query, [session_id])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting conversation session: {e}")
            return None
    
    @staticmethod
    async def update_session(
        session_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update conversation session."""
        try:
            allowed_fields = [
                "current_agent_id", "current_capability_id", "current_workflow_id",
                "detected_intent", "intent_confidence",
                "conversation_history", "session_state", "extracted_entities",
                "user_context", "workflow_context"
            ]
            
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not updates:
                return await ConversationSessionService.get_session(session_id)
            
            set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values()) + [session_id]
            
            query = f"""
                UPDATE conversation_sessions
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ${len(values)}
                RETURNING id, session_id, phone_number_id, user_id, client_id,
                         current_agent_id, current_capability_id, current_workflow_id,
                         detected_intent, intent_confidence, created_at, updated_at
            """
            
            rows = await database.query(query, values)
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error updating conversation session: {e}")
            return None
    
    @staticmethod
    async def add_participant(
        session_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Add a participant (agent) to a session."""
        try:
            # Get session first
            session = await ConversationSessionService.get_session(session_id)
            if not session:
                return None
            
            query = """
                INSERT INTO conversation_participants (session_id, agent_id)
                VALUES ($1, $2)
                RETURNING id, session_id, agent_id, joined_at, left_at, duration_seconds, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(session["id"]), UUID(agent_id)]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error adding participant: {e}")
            return None
    
    @staticmethod
    async def remove_participant(
        session_id: str,
        agent_id: str
    ) -> bool:
        """Remove a participant from a session."""
        try:
            # Get session first
            session = await ConversationSessionService.get_session(session_id)
            if not session:
                return False
            
            query = """
                UPDATE conversation_participants
                SET left_at = CURRENT_TIMESTAMP
                WHERE session_id = $1 AND agent_id = $2
            """
            
            await database.query(
                query,
                [UUID(session["id"]), UUID(agent_id)]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing participant: {e}")
            return False
    
    @staticmethod
    async def get_session_participants(session_id: str) -> List[Dict[str, Any]]:
        """Get all participants in a session."""
        try:
            query = """
                SELECT cp.id, cp.agent_id, cp.joined_at, cp.left_at, cp.duration_seconds,
                       a.id as agent_id, a.name, a.type, a.agent_type
                FROM conversation_participants cp
                JOIN agents a ON cp.agent_id = a.id
                JOIN conversation_sessions cs ON cp.session_id = cs.id
                WHERE cs.session_id = $1
                ORDER BY cp.joined_at ASC
            """
            
            rows = await database.query(query, [session_id])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting session participants: {e}")
            return []
    
    @staticmethod
    async def create_handoff(
        session_id: str,
        from_agent_id: Optional[str],
        to_agent_id: str,
        workflow_id: Optional[str] = None,
        capability_id: Optional[str] = None,
        detected_intent: Optional[str] = None,
        confidence: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a handoff record within a session."""
        try:
            # Get session first
            session = await ConversationSessionService.get_session(session_id)
            if not session:
                return None
            
            query = """
                INSERT INTO conversation_handoffs 
                (session_id, from_agent_id, to_agent_id, workflow_id, capability_id,
                 detected_intent, confidence, reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, session_id, from_agent_id, to_agent_id, workflow_id,
                         capability_id, detected_intent, confidence, reason, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [UUID(session["id"]),
                 UUID(from_agent_id) if from_agent_id else None,
                 UUID(to_agent_id),
                 UUID(workflow_id) if workflow_id else None,
                 UUID(capability_id) if capability_id else None,
                 detected_intent,
                 confidence,
                 reason]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating handoff: {e}")
            return None
    
    @staticmethod
    async def get_session_handoffs(session_id: str) -> List[Dict[str, Any]]:
        """Get all handoffs in a session."""
        try:
            query = """
                SELECT ch.id, ch.session_id, ch.from_agent_id, ch.to_agent_id,
                       ch.workflow_id, ch.capability_id, ch.detected_intent,
                       ch.confidence, ch.reason, ch.created_at, ch.updated_at
                FROM conversation_handoffs ch
                JOIN conversation_sessions cs ON ch.session_id = cs.id
                WHERE cs.session_id = $1
                ORDER BY ch.created_at ASC
            """
            
            rows = await database.query(query, [session_id])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting session handoffs: {e}")
            return []
    
    @staticmethod
    async def get_session_context(session_id: str) -> Optional[Dict[str, Any]]:
        """Get full context for a session."""
        try:
            query = """
                SELECT conversation_history, session_state, extracted_entities,
                       user_context, workflow_context
                FROM conversation_sessions
                WHERE session_id = $1
            """
            
            rows = await database.query(query, [session_id])
            
            if rows:
                return {
                    "conversationHistory": rows[0]["conversation_history"],
                    "sessionState": rows[0]["session_state"],
                    "extractedEntities": rows[0]["extracted_entities"],
                    "userContext": rows[0]["user_context"],
                    "workflowContext": rows[0]["workflow_context"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting session context: {e}")
            return None
