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
_shared_redis: Optional[redis.Redis] = None


def _get_shared_redis() -> Optional[redis.Redis]:
    """Return the process-wide shared Redis client, creating it lazily once.

    Reuses a single client/connection pool across all SessionManager instances in
    this process (no per-call connect + ping). Each process has its own client,
    so there is no cross-process shared state. redis-py manages an internal
    connection pool, making shared use from the same event loop process-safe.
    """
    global _redis_available, _shared_redis
    if _shared_redis is not None:
        return _shared_redis
    if _redis_available is False:
        return None

    try:
        client = redis.Redis.from_url(
            get_settings().redis_url, decode_responses=True, socket_connect_timeout=1
        )
        # Test connection once at warm-up time
        client.ping()
        _shared_redis = client
        _redis_available = True
        logger.info("Redis connection established (shared client)")
        return client
    except Exception as e:
        _redis_available = False
        logger.info(f"Redis unavailable, using in-memory storage fallback.")
        return None


def warm_redis() -> Optional[redis.Redis]:
    """Warm the shared Redis client during worker startup (optional dependency).

    Returns the shared client if Redis is reachable, otherwise None (the caller
    must continue with the in-memory fallback). Never raises.
    """
    return _get_shared_redis()


class SessionManager:
    """Manages session state and conversation history using Redis with in-memory fallback."""
    
    def __init__(self):
        self.settings = get_settings()
        self.session_timeout = self.settings.session_timeout
        self.max_history = self.settings.max_conversation_history

        # Shared Redis client (connection + readiness probe happen once per
        # process, not per call). In-memory storage stays per-instance so
        # concurrent calls never share mutable call state.
        self.redis = _get_shared_redis()
        self.in_memory_storage = {}  # Fallback in-memory storage (per instance)
    
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
        """Close the shared Redis connection (process-wide shutdown only).

        The client is shared across SessionManager instances, so this must only
        be called once at process shutdown (as the API lifespan does). After
        close, the flag resets so a later instance can re-probe Redis.
        """
        global _shared_redis, _redis_available
        if _shared_redis is not None:
            try:
                _shared_redis.close()
                logger.info("Session manager Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing session manager Redis: {e}")
            _shared_redis = None
            _redis_available = None
