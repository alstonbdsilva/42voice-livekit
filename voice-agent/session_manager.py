"""
Session Manager.
Handles shared session context and conversation history across agents.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config import get_settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state and conversation history using in-memory storage."""
    
    def __init__(self):
        self.settings = get_settings()
        self.session_timeout = self.settings.session_timeout
        self.max_history = self.settings.max_conversation_history
        
        # Initialize in-memory storage
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            metadata: Optional session metadata
            
        Returns:
            Session data
        """
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
            
            # Store in memory
            self.sessions[session_id] = session_data
            
            logger.info(f"Session created: {session_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None if not found
        """
        try:
            return self.sessions.get(session_id)
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"Session not found: {session_id}")
                return False
            
            # Apply updates
            for key, value in updates.items():
                session_data[key] = value
            
            session_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Store updated data in memory
            self.sessions[session_id] = session_data
            
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
        """
        Add a message to conversation history.
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            agent: Optional agent name
            
        Returns:
            True if successful, False otherwise
        """
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
            
            # Add to history
            session_data["conversation_history"].append(message)
            
            # Trim history if exceeds max
            if len(session_data["conversation_history"]) > self.max_history:
                session_data["conversation_history"] = session_data["conversation_history"][-self.max_history:]
            
            # Update session
            self.update_session(session_id, {
                "conversation_history": session_data["conversation_history"]
            })
            
            logger.info(f"Message added to session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages
            
        Returns:
            List of messages
        """
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
        """
        Set the current active agent for a session.
        
        Args:
            session_id: Session identifier
            agent_name: Agent name
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_session(session_id, {"current_agent": agent_name})
    
    def get_current_agent(self, session_id: str) -> Optional[str]:
        """
        Get the current active agent for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent name or None
        """
        session_data = self.get_session(session_id)
        if session_data:
            return session_data.get("current_agent")
        return None
    
    def update_context(
        self,
        session_id: str,
        context_updates: Dict[str, Any]
    ) -> bool:
        """
        Update session context.
        
        Args:
            session_id: Session identifier
            context_updates: Context key-value pairs to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                return False
            
            # Merge context updates
            current_context = session_data.get("context", {})
            current_context.update(context_updates)
            
            return self.update_session(session_id, {"context": current_context})
            
        except Exception as e:
            logger.error(f"Error updating context: {e}")
            return False
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get session context.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context dictionary
        """
        session_data = self.get_session(session_id)
        if session_data:
            return session_data.get("context", {})
        return {}
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions based on timeout."""
        try:
            current_time = datetime.utcnow()
            expired_sessions = []
            
            for session_id, session_data in self.sessions.items():
                created_at = datetime.fromisoformat(session_data["created_at"])
                if (current_time - created_at).total_seconds() > self.session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
                logger.info(f"Expired session deleted: {session_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
    
    def close(self):
        """Close session manager."""
        try:
            self.sessions.clear()
            logger.info("Session manager closed")
        except Exception as e:
            logger.error(f"Error closing session manager: {e}")
