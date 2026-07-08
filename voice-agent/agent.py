"""
LiveKit Voice AI Agent Worker.
Listens for SIP room creation and manages the AI audio pipeline.
"""
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    function_tool,
    TurnHandlingOptions,
)
from livekit.plugins import deepgram, openai, silero
# ElevenLabs disabled - using OpenAI TTS only for lowest latency
# from livekit.plugins import elevenlabs

from config import get_settings
from transcript_service import transcript_service

logger = logging.getLogger("voice-agent")


# ElevenLabs validation disabled - using OpenAI TTS only


class VoiceAgent(Agent):
    """Voice agent with orchestrator tools."""
    
    def __init__(self, session_manager, booking_agent, sales_agent, support_agent, settings, vad=None):
        self.session_manager = session_manager
        self.booking_agent = booking_agent
        self.sales_agent = sales_agent
        self.support_agent = support_agent
        self.agent_name = "orchestrator"
        self.intent_mapping = {
            "booking": "booking_agent",
            "sales": "sales_agent",
            "support": "support_agent",
            "general": "orchestrator"
        }
        
        # Transcript tracking
        self.transcript_session_id = None
        self.settings = get_settings()
        
        logger.info("STT initialized")
        
        # Use VAD from prewarm if provided, otherwise load it
        vad_instance = vad if vad else silero.VAD.load()
        
        super().__init__(
            vad=vad_instance,
            stt=deepgram.STT(
                language="en-US",
                model="nova-2",
                interim_results=True
            ),
            llm=openai.LLM(model="gpt-4o-mini"),
            tts=openai.TTS(
                voice="alloy",
                model="tts-1"
            ),
            instructions="You are the orchestrator agent. Start by asking how you can help the user today. Use your tools to route requests or handle booking, sales, and support."
        )
        
        # Track if greeting has been sent to prevent duplicate greetings
        self._greeting_sent = False
    
    # Note: before_llm_generation, after_llm_generation, before_tts_synthesis, 
    # after_tts_synthesis, on_user_speech_committed hooks are NOT available in 1.5.13
    # These were removed as they don't exist in this version
    
    async def on_enter(self):
        """Greet the user when the agent joins the room."""
        logger.info("on_enter called")
        
        # Initialize transcript session
        if self.settings.enable_transcripts:
            try:
                room_name = getattr(self.session, 'room_name', 'unknown')
                participant_id = getattr(self.session, 'participant_id', 'unknown')
                self.transcript_session_id = transcript_service.create_transcript_session(
                    room_name=room_name,
                    participant_id=participant_id
                )
                logger.info(f"Transcript session initialized: {self.transcript_session_id}")
            except Exception as e:
                logger.error(f"Failed to initialize transcript session: {e}")
        
        if not self._greeting_sent:
            try:
                logger.info("Sending greeting")
                greeting = "Hello, how can I help you today?"
                self.session.say(greeting)
                
                # Add greeting to transcript
                if self.settings.enable_transcripts and self.transcript_session_id:
                    transcript_service.add_transcript_entry(
                        self.transcript_session_id, 
                        speaker="agent", 
                        text=greeting
                    )
                
                self._greeting_sent = True
                logger.info("Greeting sent")
            except Exception as e:
                logger.error(f"Error in on_enter: {e}")
        else:
            logger.info("Greeting already sent, skipping")
    
    async def on_exit(self):
        """Clean up when the agent exits."""
        logger.info("on_exit called - cleaning up session")
        self._greeting_sent = False
        
        # Finalize and save transcript
        if self.settings.enable_transcripts and self.transcript_session_id:
            try:
                # Create final transcript data
                transcript_data = transcript_service.finalize_transcript(
                    self.transcript_session_id,
                    summary="Voice agent conversation completed"
                )
                
                # Add session metadata
                transcript_data.update({
                    "room_name": getattr(self.session, 'room_name', 'unknown'),
                    "participant_id": getattr(self.session, 'participant_id', 'unknown'),
                    "agent_type": self.agent_name
                })
                
                # Save to S3
                success = await transcript_service.save_transcript_to_s3(
                    self.transcript_session_id,
                    transcript_data
                )
                
                if success:
                    logger.info(f"Transcript saved: {self.transcript_session_id}")
                else:
                    logger.error(f"Failed to save transcript: {self.transcript_session_id}")
                    
            except Exception as e:
                logger.error(f"Error saving transcript: {e}")
        
        # Clear session manager state for this call (safely)
        if hasattr(self, 'session_manager'):
            try:
                self.session_manager.clear_all_sessions()
            except Exception as e:
                logger.warning(f"Redis cleanup failed (may not be running): {e}")
        logger.info("SESSION CLEANED")
    
    @function_tool()
    async def request_agent_handoff(
        self,
        session_id: str,
        target_agent: str
    ) -> str:
        """Request a handoff to a specialized agent like booking_agent, sales_agent, or support_agent."""
        try:
            if target_agent not in self.intent_mapping.values():
                return f"Invalid agent: {target_agent}"
            
            self.session_manager.set_current_agent(session_id, target_agent)
            
            handoff_messages = {
                "booking_agent": "I'll connect you with our Booking Agent who can help you with appointments and reservations.",
                "sales_agent": "I'll connect you with our Sales Agent who can assist you with product information and recommendations.",
                "support_agent": "I'll connect you with our Support Agent who can help you with technical issues and account management."
            }
            
            handoff_msg = handoff_messages.get(target_agent, f"Transferring to {target_agent}.")
            
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=handoff_msg,
                agent=self.agent_name
            )
            
            return f"SYSTEM EVENT: Handoff successful. You must now act as the {target_agent}. Respond to the user confirming the transfer: {handoff_msg}"
            
        except Exception as e:
            logger.error(f"Error requesting handoff: {e}")
            return "Error processing handoff."
    
    @function_tool()
    async def return_to_orchestrator(self, session_id: str) -> str:
        """Return control to the orchestrator agent."""
        try:
            self.session_manager.set_current_agent(session_id, "orchestrator")
            return_msg = "I'm back to help you. How can I assist you today?"
            self.session_manager.add_message(
                session_id,
                role="assistant",
                content=return_msg,
                agent=self.agent_name
            )
            return f"SYSTEM EVENT: Returned to orchestrator. Acknowledge to the user: {return_msg}"
        except Exception as e:
            logger.error(f"Error returning to orchestrator: {e}")
            return "Error returning to orchestrator."
    
    @function_tool()
    async def handle_booking_confirmation(self, session_id: str, date: str, time: str, service: str) -> str:
        """Confirm a booking with the user and save it to the system."""
        return await self.booking_agent.handle_booking_confirmation(session_id, date, time, service)
    
    @function_tool()
    async def handle_booking_cancellation(self, session_id: str, booking_reference: str) -> str:
        """Cancel an existing booking using its reference number."""
        return await self.booking_agent.handle_booking_cancellation(session_id, booking_reference)
    
    @function_tool()
    async def provide_product_recommendation(self, session_id: str, user_needs: str) -> str:
        """Provide product recommendations based on user needs."""
        return await self.sales_agent.provide_product_recommendation(session_id, user_needs)
    
    @function_tool()
    async def handle_pricing_inquiry(self, session_id: str, product_or_service: str) -> str:
        """Retrieve pricing information for a specific product or service."""
        return await self.sales_agent.handle_pricing_inquiry(session_id, product_or_service)
    
    @function_tool()
    async def escalate_to_human(self, session_id: str, reason: str) -> str:
        """Escalate the conversation to a human sales representative."""
        return await self.sales_agent.escalate_to_human(session_id, reason)
    
    @function_tool()
    async def troubleshoot_issue(self, session_id: str, issue_description: str) -> str:
        """Provide troubleshooting steps for a technical issue."""
        return await self.support_agent.troubleshoot_issue(session_id, issue_description)
    
    @function_tool()
    async def handle_billing_inquiry(self, session_id: str, inquiry: str) -> str:
        """Handle billing-related inquiries."""
        return await self.support_agent.handle_billing_inquiry(session_id, inquiry)
    
    @function_tool()
    async def escalate_issue(self, session_id: str, category: str, description: str, urgency: str) -> str:
        """Escalate an issue to a human support representative."""
        return await self.support_agent.escalate_issue(session_id, category, description, urgency)
    
    @function_tool()
    async def confirm_resolution(self, session_id: str, resolution_summary: str) -> str:
        """Confirm that an issue has been successfully resolved."""
        return await self.support_agent.confirm_resolution(session_id, resolution_summary)


def prewarm(proc: JobProcess):
    """Preload VAD model to reduce startup time."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Entry point for LiveKit agent jobs."""
    settings = get_settings()
    room_name = ctx.room.name
    
    logger.info(f"Connecting to room {room_name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Initialize services
    from session_manager import SessionManager
    from agents.booking_agent import BookingAgent
    from agents.sales_agent import SalesAgent
    from agents.support_agent import SupportAgent
    
    session_manager = SessionManager()
    booking_agent = BookingAgent(session_manager)
    sales_agent = SalesAgent(session_manager)
    support_agent = SupportAgent(session_manager)
    
    # Create agent session with VAD from prewarm (aggressive low latency settings)
    logger.info("Creating AgentSession")
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            interruption={"mode": "vad"},  # Disable adaptive interruption, use VAD only
        ),
    )
    
    # Create and start the agent
    logger.info("Creating VoiceAgent")
    agent = VoiceAgent(
        session_manager=session_manager,
        booking_agent=booking_agent,
        sales_agent=sales_agent,
        support_agent=support_agent,
        settings=settings,
        vad=ctx.proc.userdata["vad"]  # Pass VAD from prewarm to avoid duplicate loading
    )
    
    logger.info("Starting session")
    await session.start(room=ctx.room, agent=agent)
    logger.info("SESSION STARTED")
    
    # Wait for the first participant to connect AFTER session is started
    participant = await ctx.wait_for_participant()
    logger.info(f"PARTICIPANT CONNECTED: {participant.identity}")
    
    # Handle participant disconnect for proper cleanup (synchronous wrapper)
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"PARTICIPANT DISCONNECTED: {participant.identity}")
        # Create async task for cleanup
        import asyncio
        asyncio.create_task(cleanup_on_disconnect(session, session_manager))


async def cleanup_on_disconnect(session, session_manager):
    """Async cleanup function called when participant disconnects."""
    # Session is automatically closed by LiveKit on participant disconnect
    # Just clear session manager state (safely)
    try:
        session_manager.clear_all_sessions()
    except Exception as e:
        logger.warning(f"Redis cleanup failed (may not be running): {e}")
    
    logger.info("SESSION CLEANED")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
