"""
Main FastAPI application.
Provides REST API endpoints and LiveKit integration for the voice agent system.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid

from config import get_settings
from session_manager import SessionManager
from services.deepgram_stt import DeepgramSTT
from services.elevenlabs_tts import ElevenLabsTTS
from services.openai_llm import OpenAILLM
from services.livekit_service import LiveKitService
from orchestrator import Orchestrator
from agents.booking_agent import BookingAgent
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent

# Configure logging
logging.basicConfig(
    level=get_settings().log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
session_manager: Optional[SessionManager] = None
stt_service: Optional[DeepgramSTT] = None
tts_service: Optional[ElevenLabsTTS] = None
llm_service: Optional[OpenAILLM] = None
livekit_service: Optional[LiveKitService] = None
orchestrator: Optional[Orchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global session_manager, stt_service, tts_service, llm_service, livekit_service, orchestrator
    
    logger.info("Starting voice agent backend...")
    
    # Initialize services
    try:
        session_manager = SessionManager()
        stt_service = DeepgramSTT()
        tts_service = ElevenLabsTTS()
        llm_service = OpenAILLM()
        
        # Initialize agents
        booking_agent = BookingAgent(llm_service, session_manager)
        sales_agent = SalesAgent(llm_service, session_manager)
        support_agent = SupportAgent(llm_service, session_manager)
        
        # Initialize orchestrator
        orchestrator = Orchestrator(
            llm_service,
            session_manager,
            booking_agent,
            sales_agent,
            support_agent
        )
        
        # Initialize LiveKit service with AI services
        livekit_service = LiveKitService(
            stt_service=stt_service,
            tts_service=tts_service,
            llm_service=llm_service,
            orchestrator=orchestrator
        )
        
        logger.info("All services initialized successfully")
        logger.info(f"Connecting to remote LiveKit server at: {get_settings().livekit_url}")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down voice agent backend...")
        if livekit_service:
            await livekit_service.close_all()
        if stt_service:
            await stt_service.close()
        if tts_service:
            await tts_service.close()
        if llm_service:
            await llm_service.close()
        if session_manager:
            session_manager.close()
        logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Voice Agent Backend",
    description="Realtime multi-agent AI voice system with LiveKit integration",
    version="1.0.0",
    lifespan=lifespan
)


# Pydantic models
class SessionCreate(BaseModel):
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageRequest(BaseModel):
    session_id: str
    message: str


class AudioTranscribeRequest(BaseModel):
    audio_data: str  # base64 encoded
    language: str = "hi-IN"


class TextToSpeechRequest(BaseModel):
    text: str
    language: str = "hi-IN"


class LiveKitConnectRequest(BaseModel):
    room_name: str
    participant_name: str
    session_id: Optional[str] = None


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "session_manager": session_manager is not None,
            "stt": stt_service is not None,
            "tts": tts_service is not None,
            "llm": llm_service is not None,
            "livekit": livekit_service is not None,
            "orchestrator": orchestrator is not None
        },
        "livekit_url": get_settings().livekit_url
    }


# Session management endpoints
@app.post("/sessions")
async def create_session(request: SessionCreate):
    """Create a new session."""
    try:
        session_id = str(uuid.uuid4())
        session_data = session_manager.create_session(
            session_id=session_id,
            user_id=request.user_id,
            metadata=request.metadata
        )
        return {"session_id": session_id, "data": session_data}
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session data."""
    try:
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        success = session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/history")
async def get_conversation_history(session_id: str, limit: Optional[int] = None):
    """Get conversation history for a session."""
    try:
        history = session_manager.get_conversation_history(session_id, limit)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Message processing endpoint
@app.post("/messages")
async def process_message(request: MessageRequest):
    """Process a text message through the agent system."""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        
        response = await orchestrator.process_message(
            session_id=request.session_id,
            user_message=request.message
        )
        
        return {
            "session_id": request.session_id,
            "response": response,
            "current_agent": session_manager.get_current_agent(request.session_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# STT endpoint
@app.post("/stt/transcribe")
async def transcribe_audio(request: AudioTranscribeRequest):
    """Transcribe audio to text using Sarvam STT."""
    try:
        import base64
        audio_bytes = base64.b64decode(request.audio_data)
        
        transcript = await stt_service.transcribe(
            audio_data=audio_bytes,
            language=request.language
        )
        
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# TTS endpoint
@app.post("/tts/synthesize")
async def synthesize_speech(request: TextToSpeechRequest):
    """Convert text to speech using Sarvam TTS."""
    try:
        audio_bytes = await tts_service.synthesize(
            text=request.text,
            language=request.language
        )
        
        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return {"audio_data": audio_base64}
    except Exception as e:
        logger.error(f"Error synthesizing speech: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# LiveKit endpoints
@app.post("/livekit/connect")
async def connect_livekit(request: LiveKitConnectRequest):
    """Connect to a LiveKit room on the remote server with audio pipeline."""
    try:
        if not livekit_service:
            raise HTTPException(status_code=503, detail="LiveKit service not initialized")
        
        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = str(uuid.uuid4())
            session_manager.create_session(session_id=session_id)
        
        session = await livekit_service.create_session(
            room_name=request.room_name,
            participant_name=request.participant_name
        )
        
        # Setup audio handler with session_id for the complete pipeline
        await livekit_service.setup_audio_handler(request.room_name, session_id)
        
        return {
            "message": "Connected to LiveKit room with audio pipeline",
            "room_name": request.room_name,
            "participant_name": request.participant_name,
            "session_id": session_id,
            "livekit_url": get_settings().livekit_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to LiveKit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/livekit/disconnect/{room_name}")
async def disconnect_livekit(room_name: str):
    """Disconnect from a LiveKit room."""
    try:
        if not livekit_service:
            raise HTTPException(status_code=503, detail="LiveKit service not initialized")
        
        await livekit_service.close_session(room_name)
        
        return {"message": "Disconnected from LiveKit room", "room_name": room_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting from LiveKit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/livekit/participants/{room_name}")
async def get_participants(room_name: str):
    """Get participants in a LiveKit room."""
    try:
        if not livekit_service:
            raise HTTPException(status_code=503, detail="LiveKit service not initialized")
        
        participants = await livekit_service.get_participants(room_name)
        
        return {"room_name": room_name, "participants": len(participants)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting participants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for realtime communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for realtime voice communication."""
    await websocket.accept()
    
    logger.info(f"WebSocket connected for session: {session_id}")
    
    # Create session if it doesn't exist
    if not session_manager.get_session(session_id):
        session_manager.create_session(session_id=session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "text":
                # Process text message
                response = await orchestrator.process_message(
                    session_id=session_id,
                    user_message=data.get("message", "")
                )
                
                await websocket.send_json({
                    "type": "text",
                    "response": response,
                    "current_agent": session_manager.get_current_agent(session_id)
                })
            
            elif message_type == "audio":
                # Process audio message
                import base64
                audio_bytes = base64.b64decode(data.get("audio_data", ""))
                
                # Transcribe
                transcript = await stt_service.transcribe(audio_bytes)
                
                # Process through orchestrator
                response = await orchestrator.process_message(
                    session_id=session_id,
                    user_message=transcript
                )
                
                # Synthesize response
                audio_response = await tts_service.synthesize(response)
                audio_base64 = base64.b64encode(audio_response).decode('utf-8')
                
                await websocket.send_json({
                    "type": "audio",
                    "transcript": transcript,
                    "response": response,
                    "audio_data": audio_base64,
                    "current_agent": session_manager.get_current_agent(session_id)
                })
            
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


# Agent handoff endpoint
@app.post("/agents/handoff")
async def request_handoff(session_id: str, target_agent: str):
    """Request a handoff to a specific agent."""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        
        message = await orchestrator.request_agent_handoff(session_id, target_agent)
        
        return {"message": message, "current_agent": target_agent}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting handoff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/return-to-orchestrator")
async def return_to_orchestrator(session_id: str):
    """Return control to the orchestrator."""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        
        message = await orchestrator.return_to_orchestrator(session_id)
        
        return {"message": message, "current_agent": "orchestrator"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error returning to orchestrator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
