"""
LiveKit Voice AI Agent Worker.
Listens for SIP room creation and manages the AI audio pipeline.
"""
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent as VoicePipelineAgent
from livekit.plugins import deepgram, elevenlabs, openai, silero

from config import get_settings

logger = logging.getLogger("voice-agent")

async def entrypoint(ctx: JobContext):
    # Retrieve configuration
    settings = get_settings()
    room_name = ctx.room.name
    
    logger.info(f"[DEBUG] Starting entrypoint for room: {room_name}")
    logger.info(f"[DEBUG] About to call ctx.connect()")
    # Auto-subscribe to the caller's audio track
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"[DEBUG] ctx.connect() completed successfully")

    # Initialize services and context
    logger.info(f"[DEBUG] Initializing services...")
    from session_manager import SessionManager
    from orchestrator import Orchestrator
    from agents.booking_agent import BookingAgent
    from agents.sales_agent import SalesAgent
    from agents.support_agent import SupportAgent
    
    session_manager = SessionManager()
    booking_agent = BookingAgent(session_manager)
    sales_agent = SalesAgent(session_manager)
    support_agent = SupportAgent(session_manager)
    orchestrator_ctx = Orchestrator(
        session_manager,
        booking_agent,
        sales_agent,
        support_agent
    )
    logger.info(f"[DEBUG] Services initialized")
    
    # Initialize the VoicePipelineAgent
    logger.info(f"[DEBUG] Creating VoicePipelineAgent...")
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=deepgram.STT(language="en-US"),
        llm=openai.LLM(model=settings.openai_model),
        tts=elevenlabs.TTS(
            model_id=settings.elevenlabs_tts_model,
            voice=elevenlabs.Voice(
                id=settings.elevenlabs_tts_voice_id,
                name="Agent",
                category="premade"
            )
        ),
        tools=[orchestrator_ctx],
        instructions="You are the orchestrator agent. Start by asking how you can help the user today. Use your tools to route requests or handle booking, sales, and support."
    )
    logger.info(f"[DEBUG] VoicePipelineAgent created")
    
    logger.info(f"[DEBUG] Starting agent...")
    agent.start(ctx.room)
    logger.info(f"[DEBUG] Agent started")
    
    # Send an initial greeting
    logger.info(f"[DEBUG] Sending initial greeting...")
    await agent.say("Hello, how can I help you today?", allow_interruptions=True)
    logger.info(f"[DEBUG] Initial greeting sent")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
