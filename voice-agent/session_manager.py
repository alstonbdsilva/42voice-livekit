"""
Session Manager.
Handles shared session context and conversation history across agents using Redis.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import redis

from config import get_settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state and conversation history using Redis."""
    
    def __init__(self):
        self.settings = get_settings()
        self.session_timeout = self.settings.session_timeout
        self.max_history = self.settings.max_conversation_history
        
        # Initialize Redis client synchronously to avoid cascading async rewrites
        self.redis = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new session in Redis."""
        try:
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "conversation_history": [],
                "current_agent": "orchestrator",
                "context": {},
                "metadata": metadata or {}
            }
            
            self.redis.set(
                f"session:{session_id}",
                json.dumps(session_data),
                ex=self.session_timeout
            )
            
            logger.info(f"Session created: {session_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from Redis."""
        try:
            data = self.redis.get(f"session:{session_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update session data in Redis."""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"Session not found: {session_id}")
                return False
            
            for key, value in updates.items():
                session_data[key] = value
            
            session_data["updated_at"] = datetime.utcnow().isoformat()
            
            self.redis.set(
                f"session:{session_id}",
                json.dumps(session_data),
                ex=self.session_timeout
            )
            
            logger.info(f"Session updated: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: Optional[str] = None
    ) -> bool:
        """Add a message to conversation history in Redis."""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"Session not found: {session_id}")
                return False
            
            message = {
                "role": role,
                "content": content,
                "agent": agent or session_data.get("current_agent", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            history = session_data.get("conversation_history", [])
            history.append(message)
            
            if len(history) > self.max_history:
                history = history[-self.max_history:]
            
            return self.update_session(session_id, {
                "conversation_history": history
            })
            
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                return []
            
            history = session_data.get("conversation_history", [])
            if limit:
                history = history[-limit:]
            return history
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def set_current_agent(
        self,
        session_id: str,
        agent_name: str
    ) -> bool:
        """Set the current active agent for a session."""
        return self.update_session(session_id, {"current_agent": agent_name})
    
    def get_current_agent(self, session_id: str) -> Optional[str]:
        """Get the current active agent for a session."""
        session_data = self.get_session(session_id)
        if session_data:
            return session_data.get("current_agent")
        return None
    
    def update_context(
        self,
        session_id: str,
        context_updates: Dict[str, Any]
    ) -> bool:
        """Update session context."""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                return False
            
            current_context = session_data.get("context", {})
            current_context.update(context_updates)
            
            return self.update_session(session_id, {"context": current_context})
            
        except Exception as e:
            logger.error(f"Error updating context: {e}")
            return False
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get session context."""
        session_data = self.get_session(session_id)
        if session_data:
            return session_data.get("context", {})
        return {}
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis."""
        try:
            result = self.redis.delete(f"session:{session_id}")
            if result > 0:
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """No-op, Redis handles expiration via EX param."""
        pass
    
    def close(self):
        """Close Redis connection."""
        try:
            self.redis.close()
            logger.info("Session manager Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing session manager: {e}")
