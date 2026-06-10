"""
LiveKit service.
Handles realtime audio transport using LiveKit Agents SDK.
"""

import asyncio
import logging
import sys
import os
from typing import Optional, Callable, Dict
from livekit import rtc
from livekit.agents import Agent, AgentSession

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_settings

logger = logging.getLogger(__name__)


class LiveKitService:
    """Service for LiveKit audio transport and agent management."""
    
    def __init__(self, stt_service=None, tts_service=None, llm_service=None, orchestrator=None):
        self.settings = get_settings()
        self.url = self.settings.livekit_url
        self.api_key = self.settings.livekit_api_key
        self.api_secret = self.settings.livekit_api_secret
        self.sessions: Dict[str, AgentSession] = {}
        self.audio_callbacks: Dict[str, Callable] = {}
        
        # AI services for audio pipeline
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.llm_service = llm_service
        self.orchestrator = orchestrator
    
    async def create_session(
        self,
        room_name: str,
        participant_name: str
    ) -> AgentSession:
        """
        Create a LiveKit agent session.
        
        Args:
            room_name: LiveKit room name
            participant_name: Participant identity
            
        Returns:
            AgentSession instance
        """
        try:
            # Connect to LiveKit room
            session = AgentSession(
                url=self.url,
                api_key=self.api_key,
                api_secret=self.api_secret,
                room_name=room_name,
                participant_name=participant_name
            )
            
            await session.connect()
            self.sessions[room_name] = session
            
            logger.info(f"LiveKit session created for room: {room_name}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating LiveKit session: {e}")
            raise
    
    async def close_session(self, room_name: str):
        """
        Close a LiveKit session.
        
        Args:
            room_name: Room name to close
        """
        try:
            if room_name in self.sessions:
                session = self.sessions[room_name]
                await session.disconnect()
                del self.sessions[room_name]
                logger.info(f"LiveKit session closed for room: {room_name}")
        except Exception as e:
            logger.error(f"Error closing LiveKit session: {e}")
    
    async def send_audio(
        self,
        room_name: str,
        audio_data: bytes
    ):
        """
        Send audio data to a LiveKit room.
        
        Args:
            room_name: Target room name
            audio_data: Audio bytes to send
        """
        try:
            if room_name not in self.sessions:
                logger.error(f"No active session for room: {room_name}")
                return
            
            session = self.sessions[room_name]
            
            # Create audio track
            audio_track = rtc.AudioTrack(
                rtc.AudioSource(
                    sample_rate=24000,
                    num_channels=1
                )
            )
            
            # Publish audio track
            await session.publish_audio_track(audio_track)
            
            # Write audio data
            audio_frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=24000,
                num_channels=1
            )
            await audio_track.write_frame(audio_frame)
            
            logger.info(f"Audio sent to room: {room_name}")
            
        except Exception as e:
            logger.error(f"Error sending audio to LiveKit: {e}")
    
    def on_audio_received(
        self,
        room_name: str,
        callback: Callable[[bytes], None]
    ):
        """
        Register callback for received audio.
        
        Args:
            room_name: Room name
            callback: Callback function receiving audio bytes
        """
        self.audio_callbacks[room_name] = callback
        logger.info(f"Audio callback registered for room: {room_name}")
    
    async def setup_audio_handler(self, room_name: str, session_id: str = None):
        """
        Setup audio handler for a session with complete audio pipeline.
        
        Args:
            room_name: Room name
            session_id: Optional session ID for agent processing
        """
        try:
            if room_name not in self.sessions:
                logger.error(f"No active session for room: {room_name}")
                return
            
            session = self.sessions[room_name]
            
            @session.on("track_subscribed")
            def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.Participant):
                if track.kind == rtc.TrackKind.AUDIO:
                    logger.info(f"Audio track subscribed for participant: {participant.identity}")
                    
                    @track.on("frame_received")
                    async def on_frame_received(frame: rtc.AudioFrame):
                        try:
                            # 1. Detect audio and convert speech → text (STT)
                            if self.stt_service:
                                transcript = await self.stt_service.transcribe(frame.data)
                                logger.info(f"STT transcript: {transcript}")
                                
                                # 2. Send to Groq via orchestrator
                                if self.orchestrator and session_id:
                                    response = await self.orchestrator.process_message(
                                        session_id=session_id,
                                        user_message=transcript
                                    )
                                    logger.info(f"LLM response: {response}")
                                    
                                    # 3. Convert text → audio (TTS)
                                    if self.tts_service:
                                        audio_response = await self.tts_service.synthesize(response)
                                        logger.info(f"TTS audio generated: {len(audio_response)} bytes")
                                        
                                        # 4. Play back to room
                                        await self.send_audio(room_name, audio_response)
                                        logger.info(f"Audio sent back to room: {room_name}")
                        except Exception as e:
                            logger.error(f"Error processing audio frame: {e}")
            
            logger.info(f"Audio handler setup for room: {room_name}")
            
        except Exception as e:
            logger.error(f"Error setting up audio handler: {e}")
    
    async def get_participants(self, room_name: str) -> list:
        """
        Get list of participants in a room.
        
        Args:
            room_name: Room name
            
        Returns:
            List of participants
        """
        try:
            if room_name not in self.sessions:
                logger.error(f"No active session for room: {room_name}")
                return []
            
            session = self.sessions[room_name]
            participants = list(session.room.participants.values())
            
            logger.info(f"Retrieved {len(participants)} participants for room: {room_name}")
            return participants
            
        except Exception as e:
            logger.error(f"Error getting participants: {e}")
            return []
    
    async def close_all(self):
        """Close all active sessions."""
        for room_name in list(self.sessions.keys()):
            await self.close_session(room_name)
        logger.info("All LiveKit sessions closed")
