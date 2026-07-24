"""
Conversation Handoff Service.
Manages AI-to-AI conversation handoffs with full context preservation.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.conversation_handoff_service")


class ConversationHandoffService:
    """Service for managing conversation handoffs."""
    
    @staticmethod
    async def create_handoff(
        session_id: str,
        from_agent_id: Optional[str],
        to_agent_id: str,
        detected_intent: Optional[str] = None,
        detected_capability_id: Optional[str] = None,
        confidence: Optional[float] = None,
        conversation_history: Optional[Dict] = None,
        session_state: Optional[Dict] = None,
        extracted_entities: Optional[Dict] = None,
        user_context: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a conversation handoff record.
        Preserves all context for seamless AI-to-AI handoff.
        """
        try:
            query = """
                INSERT INTO conversation_handoffs 
                (session_id, from_agent_id, to_agent_id, detected_intent, detected_capability_id,
                 confidence, conversation_history, session_state, extracted_entities, user_context)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, session_id, from_agent_id, to_agent_id, detected_intent, 
                         detected_capability_id, confidence, created_at, updated_at
            """
            
            rows = await database.query(
                query,
                [
                    session_id,
                    UUID(from_agent_id) if from_agent_id else None,
                    UUID(to_agent_id),
                    detected_intent,
                    UUID(detected_capability_id) if detected_capability_id else None,
                    confidence,
                    conversation_history,
                    session_state,
                    extracted_entities,
                    user_context
                ]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating handoff: {e}")
            return None
    
    @staticmethod
    async def get_handoff(handoff_id: str) -> Optional[Dict[str, Any]]:
        """Get handoff details with full context."""
        try:
            query = """
                SELECT id, session_id, from_agent_id, to_agent_id, detected_intent,
                       detected_capability_id, confidence, conversation_history, session_state,
                       extracted_entities, user_context, created_at, updated_at
                FROM conversation_handoffs
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(handoff_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting handoff: {e}")
            return None
    
    @staticmethod
    async def get_session_handoffs(session_id: str) -> list:
        """Get all handoffs for a session."""
        try:
            query = """
                SELECT id, session_id, from_agent_id, to_agent_id, detected_intent,
                       detected_capability_id, confidence, created_at, updated_at
                FROM conversation_handoffs
                WHERE session_id = $1
                ORDER BY created_at ASC
            """
            
            rows = await database.query(query, [session_id])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting session handoffs: {e}")
            return []
    
    @staticmethod
    async def get_latest_handoff(session_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest handoff for a session."""
        try:
            query = """
                SELECT id, session_id, from_agent_id, to_agent_id, detected_intent,
                       detected_capability_id, confidence, conversation_history, session_state,
                       extracted_entities, user_context, created_at, updated_at
                FROM conversation_handoffs
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            rows = await database.query(query, [session_id])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting latest handoff: {e}")
            return None
    
    @staticmethod
    async def update_handoff_context(
        handoff_id: str,
        conversation_history: Optional[Dict] = None,
        session_state: Optional[Dict] = None,
        extracted_entities: Optional[Dict] = None,
        user_context: Optional[Dict] = None
    ) -> bool:
        """Update handoff context during conversation."""
        try:
            updates = []
            values = []
            param_count = 1
            
            if conversation_history is not None:
                updates.append(f"conversation_history = ${param_count}")
                values.append(conversation_history)
                param_count += 1
            
            if session_state is not None:
                updates.append(f"session_state = ${param_count}")
                values.append(session_state)
                param_count += 1
            
            if extracted_entities is not None:
                updates.append(f"extracted_entities = ${param_count}")
                values.append(extracted_entities)
                param_count += 1
            
            if user_context is not None:
                updates.append(f"user_context = ${param_count}")
                values.append(user_context)
                param_count += 1
            
            if not updates:
                return True
            
            updates.append(f"updated_at = CURRENT_TIMESTAMP")
            values.append(UUID(handoff_id))
            
            query = f"""
                UPDATE conversation_handoffs
                SET {', '.join(updates)}
                WHERE id = ${param_count}
            """
            
            await database.query(query, values)
            return True
            
        except Exception as e:
            logger.error(f"Error updating handoff context: {e}")
            return False
    
    @staticmethod
    async def get_handoff_context(handoff_id: str) -> Optional[Dict[str, Any]]:
        """Get full context for a handoff."""
        try:
            query = """
                SELECT conversation_history, session_state, extracted_entities, user_context
                FROM conversation_handoffs
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(handoff_id)])
            
            if rows:
                return {
                    "conversationHistory": rows[0]["conversation_history"],
                    "sessionState": rows[0]["session_state"],
                    "extractedEntities": rows[0]["extracted_entities"],
                    "userContext": rows[0]["user_context"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting handoff context: {e}")
            return None
