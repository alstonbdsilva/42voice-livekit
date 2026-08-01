"""
Session Manager.
Handles shared session context and conversation history across agents using Redis with in-memory fallback.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import redis

from config import get_settings

logger = logging.getLogger(__name__)


_redis_available: Optional[bool] = None


class SessionManager:
    """Manages session state and conversation history using Redis with in-memory fallback."""
    
    def __init__(self):
        global _redis_available
        self.settings = get_settings()
        self.session_timeout = self.settings.session_timeout
        self.max_history = self.settings.max_conversation_history
        
        # Try to initialize Redis, fall back to in-memory storage
        self.redis = None
        self.in_memory_storage = {}  # Fallback in-memory storage
        
        if _redis_available is False:
            # Skip slow connection attempt if Redis was already determined to be unavailable
            return
            
        try:
            self.redis = redis.Redis.from_url(self.settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            # Test connection
            self.redis.ping()
            _redis_available = True
            logger.info("Redis connection established")
        except Exception as e:
            _redis_available = False
            logger.warning(f"Redis unavailable, using in-memory storage: {e}")
            self.redis = None
    
    def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new session in Redis or in-memory storage."""
        session_data: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "conversation_history": [],
            "current_agent": "orchestrator",
            "context": {},
            "metadata": metadata or {}
        }
        
        if self.redis:
            try:
                self.redis.set(
                    f"session:{session_id}",
                    json.dumps(session_data),
                    ex=self.session_timeout
                )
                logger.info(f"Session created in Redis: {session_id}")
            except Exception as e:
                logger.warning(f"Redis write failed, using in-memory: {e}")
                self.in_memory_storage[session_id] = session_data
        else:
            self.in_memory_storage[session_id] = session_data
            logger.info(f"Session created in-memory: {session_id}")
        
        return session_data
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from Redis or in-memory storage."""
        if self.redis:
            try:
                data = self.redis.get(f"session:{session_id}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis read failed, checking in-memory: {e}")
        
        # Fallback to in-memory
        return self.in_memory_storage.get(session_id)
    
    def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update session data in Redis or in-memory storage."""
        session_data = self.get_session(session_id)
        if not session_data:
            logger.warning(f"Session not found: {session_id}")
            return False
        
        for key, value in updates.items():
            session_data[key] = value
        
        session_data["updated_at"] = datetime.utcnow().isoformat()
        
        if self.redis:
            try:
                self.redis.set(
                    f"session:{session_id}",
                    json.dumps(session_data),
                    ex=self.session_timeout
                )
                logger.info(f"Session updated in Redis: {session_id}")
                return True
            except Exception as e:
                logger.warning(f"Redis update failed, using in-memory: {e}")
        
        # Fallback to in-memory
        self.in_memory_storage[session_id] = session_data
        logger.info(f"Session updated in-memory: {session_id}")
        return True
    
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
        """Delete a session from Redis or in-memory storage."""
        deleted = False
        try:
            if self.redis:
                result = self.redis.delete(f"session:{session_id}")
                if result > 0:
                    deleted = True
            
            if session_id in self.in_memory_storage:
                del self.in_memory_storage[session_id]
                deleted = True
                
            if deleted:
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """No-op, Redis handles expiration via EX param."""
        pass
    
    def clear_all_sessions(self):
        """Clear all sessions from Redis and in-memory storage for fresh call state."""
        # Clear in-memory storage
        self.in_memory_storage.clear()
        logger.info("Cleared in-memory sessions")
        
        # Clear Redis if available
        if self.redis:
            try:
                keys = self.redis.keys("session:*")
                if keys:
                    self.redis.delete(*keys)
                    logger.info(f"Cleared {len(keys)} sessions from Redis")
                else:
                    logger.info("No Redis sessions to clear")
            except Exception as e:
                logger.warning(f"Redis clear failed (may not be running): {e}")
    
    def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                self.redis.close()
                logger.info("Session manager Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing session manager: {e}")
