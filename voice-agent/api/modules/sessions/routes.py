"""
Sessions and Agent Control Routers.
Defines endpoints for session management, message processing, and agent handoffs.
"""

import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.utils.errors import AppError, NotFoundError

router = APIRouter()
logger = logging.getLogger("voice-agent.api.sessions")

# --- Request Models ---

class SessionCreate(BaseModel):
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageRequest(BaseModel):
    session_id: str
    message: str


# --- Endpoints ---

@router.post("/sessions")
async def create_session(request: SessionCreate, req: Request):
    """Create a new session."""
    session_manager = req.app.state.session_manager
    try:
        session_id = str(uuid.uuid4())
        session_data = session_manager.create_session(
            session_id=session_id,
            user_id=request.user_id,
            metadata=request.metadata
        )
        return {"session_id": session_id, "data": session_data}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise AppError(f"Failed to create session: {e}", 500, "SESSION_CREATE_FAILED")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, req: Request):
    """Get session data."""
    session_manager = req.app.state.session_manager
    try:
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
        return session_data
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve session {session_id}: {e}")
        raise AppError(f"Failed to retrieve session: {e}", 500, "SESSION_RETRIEVAL_FAILED")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, req: Request):
    """Delete a session."""
    session_manager = req.app.state.session_manager
    try:
        success = session_manager.delete_session(session_id)
        if not success:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
        return {"message": "Session deleted successfully"}
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise AppError(f"Failed to delete session: {e}", 500, "SESSION_DELETE_FAILED")


@router.get("/sessions/{session_id}/history")
async def get_conversation_history(session_id: str, req: Request, limit: Optional[int] = None):
    """Get conversation history for a session."""
    session_manager = req.app.state.session_manager
    try:
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
            
        history = session_manager.get_conversation_history(session_id, limit)
        return {"session_id": session_id, "history": history}
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve conversation history for {session_id}: {e}")
        raise AppError(f"Failed to retrieve conversation history: {e}", 500, "HISTORY_RETRIEVAL_FAILED")


@router.post("/messages")
async def process_message(request: MessageRequest, req: Request):
    """Process a text message through the agent system."""
    session_manager = req.app.state.session_manager
    orchestrator = req.app.state.orchestrator
    try:
        if not orchestrator:
            raise AppError("Orchestrator not initialized", 503, "ORCHESTRATOR_NOT_INITIALIZED")
            
        session_data = session_manager.get_session(request.session_id)
        if not session_data:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
            
        response = await orchestrator.process_message(
            session_id=request.session_id,
            user_message=request.message
        )
        
        return {
            "session_id": request.session_id,
            "response": response,
            "current_agent": session_manager.get_current_agent(request.session_id)
        }
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Error processing message for session {request.session_id}: {e}")
        raise AppError(f"Error processing message: {e}", 500, "MESSAGE_PROCESS_FAILED")


@router.post("/agents/handoff")
async def request_handoff(session_id: str, target_agent: str, req: Request):
    """Request a handoff to a specific agent."""
    session_manager = req.app.state.session_manager
    orchestrator = req.app.state.orchestrator
    try:
        if not orchestrator:
            raise AppError("Orchestrator not initialized", 503, "ORCHESTRATOR_NOT_INITIALIZED")
            
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
            
        message = await orchestrator.request_agent_handoff(session_id, target_agent)
        return {"message": message, "current_agent": target_agent}
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Error requesting handoff for session {session_id} to {target_agent}: {e}")
        raise AppError(f"Error requesting handoff: {e}", 500, "HANDOFF_FAILED")


@router.post("/agents/return-to-orchestrator")
async def return_to_orchestrator(session_id: str, req: Request):
    """Return control to the orchestrator."""
    session_manager = req.app.state.session_manager
    orchestrator = req.app.state.orchestrator
    try:
        if not orchestrator:
            raise AppError("Orchestrator not initialized", 503, "ORCHESTRATOR_NOT_INITIALIZED")
            
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND")
            
        message = await orchestrator.return_to_orchestrator(session_id)
        return {"message": message, "current_agent": "orchestrator"}
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Error returning session {session_id} to orchestrator: {e}")
        raise AppError(f"Error returning to orchestrator: {e}", 500, "RETURN_ORCHESTRATOR_FAILED")


import json
from livekit import api as lk_api
from config import get_settings

class LiveKitTokenRequest(BaseModel):
    roomName: Optional[str] = None
    identity: Optional[str] = None
    name: Optional[str] = None
    agentId: Optional[str] = None
    agentName: Optional[str] = None

@router.post("/livekit/token")
async def generate_livekit_token(req_body: LiveKitTokenRequest):
    """
    Generate a LiveKit JWT AccessToken for web browser WebRTC voice calls.
    """
    try:
        settings = get_settings()
        room_name = req_body.roomName or f"room-{uuid.uuid4().hex[:8]}"
        participant_identity = req_body.identity or f"user-{uuid.uuid4().hex[:6]}"
        participant_name = req_body.name or "Web Caller"
        
        token = lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret) \
            .with_identity(participant_identity) \
            .with_name(participant_name) \
            .with_grants(lk_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True
            ))

        if req_body.agentId or req_body.agentName:
            token.with_metadata(json.dumps({
                "agent_id": req_body.agentId or "",
                "agent_name": req_body.agentName or "Voice Agent"
            }))

        jwt_token = token.to_jwt()

        # Create Agent Dispatch so the registered LiveKit worker (inbound-agent) joins the room
        try:
            async with lk_api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
                dispatch_metadata = json.dumps({
                    "agent_id": req_body.agentId or "",
                    "agent_name": req_body.agentName or "Voice Agent"
                })
                dispatch_req = lk_api.CreateAgentDispatchRequest(
                    agent_name=settings.livekit_agent_name,
                    room=room_name,
                    metadata=dispatch_metadata
                )
                await lk.agent_dispatch.create_dispatch(dispatch_req)
                logger.info(f"[LiveKit Token] Dispatched agent '{settings.livekit_agent_name}' to room '{room_name}'")
        except Exception as dispatch_err:
            logger.warning(f"[LiveKit Token] Could not create agent dispatch for room '{room_name}': {dispatch_err}")

        return {
            "token": jwt_token,
            "url": settings.livekit_url,
            "roomName": room_name,
            "identity": participant_identity
        }
    except Exception as e:
        logger.error(f"Failed to generate LiveKit token: {e}")
        raise AppError(f"Failed to generate LiveKit token: {e}", 500, "LIVEKIT_TOKEN_FAILED")


