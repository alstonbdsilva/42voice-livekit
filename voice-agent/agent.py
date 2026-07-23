"""
LiveKit Voice AI Agent Worker.
Listens for SIP room creation and manages the AI audio pipeline.
"""
import asyncio
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
    
    def __init__(self, session_manager, booking_agent, sales_agent, support_agent, settings, room_name: str, participant_id: str, ctx: JobContext, vad=None, out_of_credits: bool = False):
        self.session_manager = session_manager
        self.booking_agent = booking_agent
        self.sales_agent = sales_agent
        self.support_agent = support_agent
        self.room_name = room_name
        self.participant_id = participant_id
        self.ctx = ctx
        self.agent_name = "orchestrator"
        self.out_of_credits = out_of_credits
        self.intent_mapping = {
            "booking": "booking_agent",
            "sales": "sales_agent",
            "support": "support_agent",
            "general": "orchestrator"
        }
        
        # Transcript tracking
        self.transcript_session_id = None
        self.settings = get_settings()
        self.call_start = None
        self.egress_id = None
        self.recording_filename = None
        self._recording_task = None
        
        logger.info("STT initialized")
        
        # Use VAD from prewarm if provided, otherwise load it
        vad_instance = vad if vad else silero.VAD.load()
        
        instructions = (
            "You are a billing notice voice. State that the account is out of credits and goodbye."
            if out_of_credits
            else "You are the orchestrator agent. Start by asking how you can help the user today. Use your tools to route requests or handle booking, sales, and support."
        )
        
        super().__init__(
            vad=vad_instance,
            stt=deepgram.STT(
                language="en-US",
                model="nova-2",
                interim_results=True
            ),
            llm=openai.LLM(model="gpt-4o-mini"),
            tts=deepgram.TTS(),
            instructions=instructions
        )
        
        # Track if greeting has been sent to prevent duplicate greetings
        self._greeting_sent = False
    
    # Note: before_llm_generation, after_llm_generation, before_tts_synthesis, 
    # after_tts_synthesis, on_user_speech_committed hooks are NOT available in 1.5.13
    # These were removed as they don't exist in this version
    
    async def on_enter(self):
        """Greet the user when the agent joins the room."""
        logger.info("on_enter called")
        from datetime import datetime, timezone
        self.call_start = datetime.now(timezone.utc)
        
        # Initialize transcript session
        if self.settings.enable_transcripts:
            try:
                room_name = getattr(self, 'room_name', 'unknown')
                participant_id = getattr(self, 'participant_id', 'unknown')
                self.transcript_session_id = transcript_service.create_transcript_session(
                    room_name=room_name,
                    participant_id=participant_id
                )
                logger.info(f"Transcript session initialized: {self.transcript_session_id}")
            except Exception as e:
                logger.error(f"Failed to initialize transcript session: {e}")
        
        if self.out_of_credits:
            try:
                logger.info("Sending out of credits warning")
                warning = "We are sorry, but this account has run out of call minutes. Please recharge your balance in the dashboard. Goodbye."
                self.session.say(warning)
                self._greeting_sent = True
                
                async def delayed_disconnect():
                    await asyncio.sleep(6.0)
                    logger.info("Disconnecting room due to out of credits balance")
                    if self.ctx and self.ctx.room:
                        await self.ctx.room.disconnect()
                asyncio.create_task(delayed_disconnect())
            except Exception as e:
                logger.error(f"Error speaking out of credits warning: {e}")
            return

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
        
        # Wait for recording startup task to complete before stopping
        # This ensures egress_id is set if recording was successful
        recording_task = getattr(self, '_recording_task', None)
        if recording_task and not recording_task.done():
            try:
                logger.debug("Waiting for recording startup task to complete")
                await asyncio.wait_for(recording_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Recording startup task did not complete within timeout")
            except Exception as e:
                logger.warning(f"Error waiting for recording startup task: {e}")
        
        # Stop recording if active
        try:
            from recording_service import recording_service
            egress_id = getattr(self, 'egress_id', None)
            
            if egress_id:
                success = await recording_service.stop_recording(egress_id)
                if success:
                    logger.info(f"Recording stopped: egress_id={egress_id}")
                else:
                    logger.warning(f"Recording stop failed: egress_id={egress_id}")
            else:
                logger.warning("Recording was never started (egress_id is None)")
        except Exception as e:
            logger.error(f"Recording stop error: {e}", exc_info=True)
        
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

        # Dynamically register call details in database
        if self.call_start:
            from datetime import datetime, timezone
            call_end = datetime.now(timezone.utc)
            asyncio.create_task(register_call_with_backend(self, self.call_start, call_end))
    
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


async def register_call_with_backend(agent, started_at, ended_at):
    try:
        import httpx
        from datetime import datetime
        
        duration = int((ended_at - started_at).total_seconds())
        room_name = getattr(agent, 'room_name', 'unknown')
        
        agent_name = "Voice Agent"
        # Try to get agent names from settings, with fallback to default
        agent_names_str = getattr(agent.settings, 'agent_names', 'Voice Agent')
        if agent_names_str:
            agent_names = agent_names_str.split(",")
            for name in agent_names:
                name = name.strip()
                if name.lower().replace(" ", "") in room_name.lower().replace("_", "").replace("-", ""):
                    agent_name = name
                    break
        
        lines = []
        full_text = ""
        action_items = []
        
        if agent.settings.enable_transcripts and agent.transcript_session_id:
            transcript_data = transcript_service.finalize_transcript(
                agent.transcript_session_id,
                summary="Voice agent conversation completed"
            )
            transcript_data.update({
                "room_name": room_name,
                "participant_id": getattr(agent, 'participant_id', 'unknown'),
                "agent_type": agent.agent_name
            })
            
            await transcript_service.save_transcript_to_s3(
                agent.transcript_session_id,
                transcript_data
            )
            
            raw_lines = transcript_data.get("lines", [])
            lines = [{"speaker": l["speaker"], "text": l["text"]} for l in raw_lines]
            full_text = transcript_data.get("full_text", "")
            
            for l in lines:
                text = l["text"].lower()
                if "book" in text or "schedule" in text or "appointment" in text:
                    action_items.append("Follow up on booking/appointment request")
                elif "price" in text or "cost" in text or "quote" in text:
                    action_items.append("Send pricing packages and details")
            
            action_items = list(set(action_items))
            if not action_items:
                action_items = ["Follow up with customer inquiry"]

        recording_enabled = getattr(agent.settings, "enable_recording", True)
        filename = getattr(agent, 'recording_filename', None)
        egress_id = getattr(agent, 'egress_id', None)
        s3_key = None
        size = 0
        recording_status = "success" if filename and egress_id else "failed"
        failure_reason = None
        
        if recording_enabled:
            if not filename:
                failure_reason = "Recording filename not set (recording might have failed to start or connection timed out)"
                logger.warning(f"Recording failed: {failure_reason}")
            elif not egress_id:
                failure_reason = "Egress ID not set"
                logger.warning(f"Recording failed: {failure_reason}")
            else:
                s3_key = f"recordings/{filename}"
                try:
                    import boto3
                    from recording_service import recording_service
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=agent.settings.aws_access_key_id,
                        aws_secret_access_key=agent.settings.aws_secret_access_key,
                        region_name=agent.settings.aws_region
                    )
                    
                    # For self-hosted egress, verify upload completion with retries
                    upload_verified = await recording_service.verify_s3_upload(s3_key)
                    
                    if upload_verified:
                        try:
                            response = await asyncio.wait_for(
                                asyncio.to_thread(
                                    s3_client.head_object,
                                    Bucket=agent.settings.s3_bucket_name,
                                    Key=s3_key
                                ),
                                timeout=5.0
                            )
                            size = response.get('ContentLength', 0)
                        except asyncio.TimeoutError:
                            logger.warning(f"S3 head_object timeout for {s3_key}")
                            size = duration * 16000
                    else:
                        logger.warning(f"S3 upload verification failed for {s3_key}")
                        size = duration * 16000
                except Exception as e:
                    logger.warning(f"Failed to query S3 object size for {s3_key}: {e}")
                    size = duration * 16000
            
        outcome = "resolved"
        sentiment = "neutral"
        sentiment_score = 0.00
        human_handoff = False
        escalation_reason = None
        
        full_text_lower = full_text.lower()
        if "escalat" in full_text_lower or "transfer" in full_text_lower:
            outcome = "escalated_to_human"
            human_handoff = True
            escalation_reason = "Customer requested human agent assistance"
        elif "book" in full_text_lower or "appointment" in full_text_lower:
            outcome = "booked_appointment"
            sentiment = "positive"
            sentiment_score = 0.80
            
        recording_payload = None
        if filename and egress_id and s3_key:
            recording_payload = {
                "filename": filename,
                "duration": duration,
                "size": size,
                "s3_key": s3_key
            }

        payload = {
            "agentName": agent_name,
            "customerName": "Customer",
            "customerContact": getattr(agent, 'participant_id', 'Unknown'),
            "channel": "voice",
            "duration": duration,
            "cost": round(duration * 0.0015, 2),
            "sentiment": sentiment,
            "outcome": outcome,
            "summary": "Voice agent conversation completed",
            "intent": "general",
            "leadScore": 75 if outcome == "booked_appointment" else 50,
            "sentimentScore": sentiment_score,
            "humanHandoff": human_handoff,
            "escalationReason": escalation_reason,
            "recording": recording_payload,
            "transcript": {
                "fullText": full_text if full_text else "No transcript lines",
                "lines": lines if lines else [{"speaker": "agent", "text": "Call started"}],
                "actionItems": action_items
            }
        }
        
        backend_url = getattr(agent.settings, 'backend_url', 'http://localhost:5000/api/v1')
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{backend_url}/conversations/register", json=payload, timeout=30.0)
            if response.status_code == 201:
                logger.info("Call successfully registered in backend database.")
            else:
                logger.error(f"Failed to register call in backend. Status: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error registering call with backend: {e}", exc_info=True)


def prewarm(proc: JobProcess):
    """Preload VAD model to reduce startup time."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    """Entry point for LiveKit agent jobs."""
    settings = get_settings()
    room_name = ctx.room.name
    
    logger.info(f"Connecting to room {room_name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    shutdown_event = asyncio.Event()
    
    @ctx.room.on("disconnected")
    def on_disconnected():
        logger.info("Room disconnected, shutting down entrypoint...")
        shutdown_event.set()

    async def on_shutdown(reason: str):
        logger.info(f"Shutdown requested: {reason}")
        shutdown_event.set()

    ctx.add_shutdown_callback(on_shutdown)
    
    # Initialize services
    from session_manager import SessionManager
    from agents.booking_agent import BookingAgent
    from agents.sales_agent import SalesAgent
    from agents.support_agent import SupportAgent
    from recording_service import recording_service
    
    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"PARTICIPANT CONNECTED: {participant.identity}")
    
    # 1. Run credit check
    import httpx
    backend_url = getattr(settings, 'backend_url', 'http://localhost:5000/api/v1')
    out_of_credits = False
    
    try:
        async with httpx.AsyncClient() as http_client:
            credit_check_resp = await http_client.get(
                f"{backend_url}/billing/check-credits?agent_name=orchestrator",
                timeout=10.0
            )
            if credit_check_resp.status_code == 200:
                credit_data = credit_check_resp.json()
                if not credit_data.get("has_credits", True):
                    logger.warning(f"Rejecting call: client/reseller has no minutes left. Balance: {credit_data.get('minutes_balance', 0)}")
                    out_of_credits = True
    except Exception as e:
        logger.error(f"Error checking minutes balance: {e}")

    session_manager = SessionManager()
    booking_agent = BookingAgent(session_manager)
    sales_agent = SalesAgent(session_manager)
    support_agent = SupportAgent(session_manager)
    
    # Create agent session with VAD from prewarm (aggressive low latency settings)
    logger.info("Creating AgentSession")
    session: AgentSession = AgentSession(
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
        room_name=ctx.room.name,
        participant_id=participant.identity,
        ctx=ctx,
        vad=ctx.proc.userdata["vad"],
        out_of_credits=out_of_credits
    )
    
    # Initialize recording state
    agent.egress_id = None
    agent.recording_filename = None
    agent._recording_task = None  # Track recording startup task for synchronization

    # Subscribe to speech/message events to build transcripts dynamically
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        if event.is_final and event.transcript.strip():
            logger.info(f"User speech transcribed: {event.transcript}")
            if agent.settings.enable_transcripts and agent.transcript_session_id:
                transcript_service.add_transcript_entry(
                    agent.transcript_session_id,
                    speaker="customer",
                    text=event.transcript
                )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        msg = event.item
        if hasattr(msg, "role") and (msg.role == "assistant" or msg.role == "agent"):
            content_text = ""
            if isinstance(msg.content, str):
                content_text = msg.content
            elif hasattr(msg.content, '__iter__'):
                parts = []
                for part in msg.content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif hasattr(part, 'text') and part.text:
                        parts.append(part.text)
                content_text = " ".join(parts)
            
            if content_text.strip():
                logger.info(f"Agent speech: {content_text}")
                if agent.settings.enable_transcripts and agent.transcript_session_id:
                    transcript_service.add_transcript_entry(
                        agent.transcript_session_id,
                        speaker="agent",
                        text=content_text
                    )
    
    logger.info("Starting session")
    await session.start(room=ctx.room, agent=agent)
    logger.info("SESSION STARTED")
    
    # Wait for the caller (SIP bridge) to subscribe to the agent's track 
    # BEFORE starting the egress recording. This prevents the egress participant 
    # from triggering the playout of greeting audio prematurely.
    try:
        logger.info("Waiting for caller to subscribe to agent track...")
        subscribed_fut = session.room_io.subscribed_fut
        if subscribed_fut is not None:
            await asyncio.wait_for(subscribed_fut, timeout=15.0)
            logger.info("Caller subscribed to agent track. Initializing recording...")
        else:
            logger.warning("session.room_io.subscribed_fut is None, skipping wait")
    except asyncio.TimeoutError:
        logger.warning("Timed out waiting for caller to subscribe to agent track")
    except Exception as e:
        logger.error(f"Error waiting for track subscription: {e}")
    
    # Start recording AFTER session.start() and subscription as a background task
    if getattr(agent.settings, "enable_recording", True):
        async def start_recording_task():
            try:
                logger.info(f"Starting recording for room: {room_name}, participant: {participant.identity}")
                egress_id, filename = await recording_service.start_room_recording(room_name)
                agent.egress_id = egress_id
                agent.recording_filename = filename
                if egress_id:
                    logger.info(f"Recording started: egress_id={egress_id}, filename={filename}, room={room_name}")
                else:
                    logger.error(f"Recording failed to start: egress_id is None for room {room_name}")
            except Exception as e:
                logger.error(f"Recording startup error for room {room_name}: {e}", exc_info=True)
        
        # Run recording start as background task so it continues even if participant disconnects
        # Track the task so on_exit can wait for it to complete
        agent._recording_task = asyncio.create_task(start_recording_task())
    else:
        logger.info(f"Recording disabled by configuration for room {room_name}")
    
    # Handle participant disconnect for proper cleanup (synchronous wrapper)
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"PARTICIPANT DISCONNECTED: {participant.identity}")
        # Create async task for cleanup
        async def run_cleanup():
            await cleanup_on_disconnect(session, session_manager)
            shutdown_event.set()
        asyncio.create_task(run_cleanup())

    # Keep the entrypoint running until participant disconnects, room is disconnected, or job is shutdown
    await shutdown_event.wait()
    logger.info("Entrypoint exiting")


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
