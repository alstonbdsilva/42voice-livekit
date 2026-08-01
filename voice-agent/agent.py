"""
LiveKit Voice AI Agent Worker.
Listens for SIP room creation and manages the AI audio pipeline.
"""
import asyncio
import logging
import sys
import warnings
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=".*HMAC key is.*")
warnings.filterwarnings("ignore", category=UserWarning, module="jwt")

load_dotenv()

import json
import httpx
import redis
from api.modules.phone_numbers.livekit_sip import livekit_sip_service
from api import database
from custom_tools import (
    tool_to_function_schema,
    execute_http_tool,
    resolve_transfer_config,
    call_mcp_tool,
    safe_calculator
)
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
    
    def __init__(self, session_manager, booking_agent, sales_agent, support_agent, settings, room_name: str, participant_id: str, ctx: JobContext, vad=None, out_of_credits: bool = False, custom_prompt: Optional[str] = None, agent_name: Optional[str] = None, unassigned_number: bool = False, client_id: Optional[str] = None, tools: Optional[list] = None):
        self.session_manager = session_manager
        self.booking_agent = booking_agent
        self.sales_agent = sales_agent
        self.support_agent = support_agent
        self.room_name = room_name
        self.participant_id = participant_id
        self.ctx = ctx
        self.client_id = client_id
        # agent_name must be explicitly set from phone number lookup; None indicates unassigned
        self.agent_name = agent_name or "unknown"
        self.out_of_credits = out_of_credits
        self.unassigned_number = unassigned_number
        self.intent_mapping = {
            "booking": "booking_agent",
            "sales": "sales_agent",
            "support": "support_agent",
            "general": self.agent_name
        }
        
        # Transcript tracking
        self.transcript_session_id = None
        self.settings = get_settings()
        self.call_start = None
        self.egress_id = None
        self.recording_filename = None
        self._recording_task: Optional[asyncio.Task[Any]] = None
        
        logger.info("STT initialized")
        
        # Use VAD from prewarm if provided, otherwise load it
        vad_instance = vad if vad else silero.VAD.load()
        
        instructions = (
            "You are a billing notice voice. State that the account is out of credits and goodbye."
            if out_of_credits
            else (custom_prompt if custom_prompt else "You are the orchestrator agent. Start by asking how you can help the user today. Use your tools to route requests, handle booking, sales, and support, or end the call when the conversation is finished.")
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
            instructions=instructions,
            tools=tools
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
        
        # Handle unassigned phone numbers - reject the call
        if self.unassigned_number:
            try:
                logger.warning("Rejecting call: phone number is unassigned (no agent configured)")
                # Default message from the lookup instructions (e.g. agent is currently unavailable, config error, etc.)
                message = self.instructions if self.instructions else "Welcome to 42 voice and we will get back to you."
                
                # Fetch end_call tool config from database if available (checking client-specific first, then system-wide/default)
                try:
                    if database.pool is None:
                        await database.init_pool()
                    rows = []
                    if self.client_id:
                        rows = await database.query(
                            "SELECT definition FROM tools WHERE client_id = $1::uuid AND category = 'end_call' AND status = 'active' LIMIT 1",
                            [self.client_id]
                        )
                    if not rows:
                        rows = await database.query(
                            "SELECT definition FROM tools WHERE client_id IS NULL AND category = 'end_call' AND status = 'active' LIMIT 1"
                        )
                    if rows:
                        definition = rows[0]["definition"] or {}
                        if isinstance(definition, str):
                            try:
                                definition = json.loads(definition)
                            except Exception:
                                definition = {}
                        config = definition.get("config", {}) if isinstance(definition, dict) else {}
                        message_type = config.get("messageType", "none")
                        if message_type == "custom":
                            message = config.get("customMessage", "")
                        elif message_type == "none":
                            message = ""
                except Exception as db_err:
                    logger.error(f"Error fetching end_call config for unassigned number: {db_err}")
                
                if message:
                    self.session.say(message)
                self._greeting_sent = True
                
                async def delayed_disconnect():
                    await asyncio.sleep(4.0 if message else 0.5)
                    logger.info("Disconnecting room due to unassigned phone number")
                    if self.ctx and self.ctx.room:
                        await self.ctx.room.disconnect()
                asyncio.create_task(delayed_disconnect())
            except Exception as e:
                logger.error(f"Error speaking unassigned number message: {e}")
            return
        
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

    @function_tool()
    async def end_call(self) -> str:
        """End the call immediately when the conversation is finished, when the user requests to disconnect, or when you are done helping."""
        logger.info("end_call tool executed")
        goodbye_msg = "Thank you for calling. Goodbye."
        
        try:
            if database.pool is None:
                await database.init_pool()
            # Query client-specific end_call tool first, and fall back to system-wide default (client_id IS NULL)
            rows = []
            if self.client_id:
                rows = await database.query(
                    "SELECT definition FROM tools WHERE client_id = $1::uuid AND category = 'end_call' AND status = 'active' LIMIT 1",
                    [self.client_id]
                )
            if not rows:
                rows = await database.query(
                    "SELECT definition FROM tools WHERE client_id IS NULL AND category = 'end_call' AND status = 'active' LIMIT 1"
                )
            if rows:
                definition = rows[0]["definition"] or {}
                if isinstance(definition, str):
                    try:
                        definition = json.loads(definition)
                    except Exception:
                        definition = {}
                config = definition.get("config", {}) if isinstance(definition, dict) else {}
                message_type = config.get("messageType", "none")
                if message_type == "custom":
                    goodbye_msg = config.get("customMessage", "")
                elif message_type == "none":
                    goodbye_msg = ""
        except Exception as e:
            logger.error(f"Error fetching end_call tool config: {e}")

        if goodbye_msg:
            try:
                if hasattr(self.session, "interrupt"):
                    self.session.interrupt(force=True)
                self.session.say(goodbye_msg)
            except Exception as e:
                logger.error(f"Error saying goodbye message: {e}")
                
        async def delayed_disconnect():
            await asyncio.sleep(2.0 if goodbye_msg else 0.5)
            logger.info("Disconnecting room via end_call tool")
            if self.ctx and self.ctx.room:
                await self.ctx.room.disconnect()
        asyncio.create_task(delayed_disconnect())
        return "Call is ending."


async def analyze_transcript_with_llm(full_text: str, settings) -> dict:
    """Analyze conversation transcript using OpenAI to extract summary, sentiment, lead score, intent, and action items."""
    if not full_text or len(full_text.strip()) < 10:
        return {
            "summary": "Short call with minimal conversation.",
            "sentiment": "neutral",
            "sentimentScore": 0.0,
            "intent": "general",
            "leadScore": 50,
            "actionItems": ["Follow up with customer inquiry"]
        }
    
    try:
        api_key = getattr(settings, "openai_api_key", None)
        if api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                prompt = (
                    "Analyze the following call transcript between a Customer and an AI Voice Agent. "
                    "Return ONLY a JSON object with these exact keys:\n"
                    "- \"summary\": A concise 1-2 sentence summary of the discussion.\n"
                    "- \"sentiment\": \"positive\", \"neutral\", or \"negative\".\n"
                    "- \"sentimentScore\": Float between -1.0 and 1.0.\n"
                    "- \"intent\": Short intent tag (e.g. \"inquiry\", \"booking\", \"support\", \"billing\", \"general\").\n"
                    "- \"leadScore\": Integer from 0 to 100 representing customer interest/lead quality.\n"
                    "- \"actionItems\": Array of 1 to 3 specific follow-up action items.\n\n"
                    f"Transcript:\n{full_text}"
                )
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return {
                        "summary": str(parsed.get("summary", "Voice agent conversation completed")),
                        "sentiment": str(parsed.get("sentiment", "neutral")).lower(),
                        "sentimentScore": float(parsed.get("sentimentScore", 0.0)),
                        "intent": str(parsed.get("intent", "general")).lower().replace(" ", "_"),
                        "leadScore": int(parsed.get("leadScore", 50)),
                        "actionItems": [str(x) for x in parsed.get("actionItems", [])] or ["Follow up with customer inquiry"]
                    }
    except Exception as e:
        logger.warning(f"AI transcript analysis via OpenAI failed: {e}")
        
    # Smart Fallback rules if LLM is unreachable
    lines_count = len(full_text.splitlines())
    text_lower = full_text.lower()
    
    intent = "general"
    summary_parts = []
    action_items = []
    sentiment = "neutral"
    sentiment_score = 0.00
    lead_score = 50

    if "book" in text_lower or "appointment" in text_lower or "schedule" in text_lower:
        intent = "booking"
        summary_parts.append("Customer called regarding booking an appointment or reservation.")
        action_items.append("Confirm appointment details and update calendar")
        lead_score += 30
        sentiment_score += 0.40
        sentiment = "positive"
    if "price" in text_lower or "cost" in text_lower or "rate" in text_lower or "package" in text_lower:
        intent = "inquiry"
        summary_parts.append("Customer requested information on pricing, rates, and available packages.")
        action_items.append("Send detailed pricing guide and quote to customer")
        lead_score += 25
    if "help" in text_lower or "issue" in text_lower or "problem" in text_lower or "support" in text_lower:
        intent = "support"
        summary_parts.append("Customer reached out for technical support and troubleshooting assistance.")
        action_items.append("Review support ticket details and follow up with customer")
    if "thank" in text_lower or "great" in text_lower or "awesome" in text_lower or "helpful" in text_lower:
        sentiment = "positive"
        sentiment_score = max(0.65, sentiment_score)
        lead_score += 15
    if "angry" in text_lower or "cancel" in text_lower or "bad" in text_lower or "terrible" in text_lower:
        sentiment = "negative"
        sentiment_score = -0.65
        lead_score = max(10, lead_score - 30)

    if not action_items:
        action_items = ["Follow up with customer inquiry"]
    if not summary_parts:
        summary_parts.append(f"Voice conversation completed with {lines_count} spoken exchanges.")

    return {
        "summary": " ".join(summary_parts),
        "sentiment": sentiment,
        "sentimentScore": round(sentiment_score, 2),
        "intent": intent,
        "leadScore": min(100, max(0, lead_score)),
        "actionItems": action_items
    }


async def register_call_with_backend(agent, started_at, ended_at):
    try:
        import httpx
        from datetime import datetime
        
        duration = int((ended_at - started_at).total_seconds())
        room_name = getattr(agent, 'room_name', 'unknown')
        
        agent_name = getattr(agent, 'agent_name', 'Voice Agent')
        
        lines = []
        full_text = ""
        
        if agent.settings.enable_transcripts and agent.transcript_session_id:
            transcript_data = transcript_service.finalize_transcript(
                agent.transcript_session_id,
                summary="Voice agent conversation completed"
            )
            
            raw_lines = transcript_data.get("lines", [])
            lines = [{"speaker": l["speaker"], "text": l["text"]} for l in raw_lines]
            full_text = transcript_data.get("full_text", "")
            
        ai_metrics = await analyze_transcript_with_llm(full_text, agent.settings)

        recording_enabled = getattr(agent.settings, "enable_recording", True)
        filename = getattr(agent, 'recording_filename', None)
        egress_id = getattr(agent, 'egress_id', None)
        s3_key = None
        size = 0
        
        if recording_enabled:
            if filename and egress_id:
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
        human_handoff = False
        escalation_reason = None
        
        full_text_lower = full_text.lower()
        if "escalat" in full_text_lower or "transfer" in full_text_lower:
            outcome = "escalated_to_human"
            human_handoff = True
            escalation_reason = "Customer requested human agent assistance"
        elif "book" in full_text_lower or "appointment" in full_text_lower:
            outcome = "booked_appointment"
            
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
            "sentiment": ai_metrics["sentiment"],
            "outcome": outcome,
            "summary": ai_metrics["summary"],
            "intent": ai_metrics["intent"],
            "leadScore": ai_metrics["leadScore"],
            "sentimentScore": ai_metrics["sentimentScore"],
            "humanHandoff": human_handoff,
            "escalationReason": escalation_reason,
            "recording": recording_payload,
            "transcript": {
                "fullText": full_text if full_text else "No transcript lines",
                "lines": lines if lines else [{"speaker": "agent", "text": "Call started"}],
                "actionItems": ai_metrics["actionItems"]
            }
        }
        
        backend_url = agent.settings.backend_url
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{backend_url}/conversations/register", json=payload, timeout=30.0)
            if response.status_code == 201:
                logger.info(f"Registered call details for room {room_name} with agent {agent_name}")
            else:
                logger.error(f"Failed to register call details for room {room_name}: {response.status_code} {response.text}")
        
        if agent.transcript_session_id:
            transcript_service.clear_session(agent.transcript_session_id)
                
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
    
    # 1. Resolve the called phone number from SIP participant attributes
    backend_url = settings.backend_url
    out_of_credits = False
    custom_prompt = None
    agent_name = None  # Must be explicitly set from phone number lookup
    unassigned_number = False
    client_id = None
    agent_id = None
    
    called_number = (
        participant.attributes.get("sip.trunkPhoneNumber") or
        participant.attributes.get("sip.toUser") or
        participant.attributes.get("sip.to") or
        participant.attributes.get("sip.phoneNumber")
    )
    logger.info("[SIP] Participant Connected")
    logger.info(f"[SIP] Participant identity: {participant.identity}")
    logger.info(f"[SIP] Participant attributes: {participant.attributes}")
    logger.info(f"[SIP] Resolved called_number using attribute: {called_number}")
    
    if called_number:
        logger.info(f"[Backend] Starting routing lookup for {called_number} at {backend_url}/phone-numbers/lookup")
        try:
            async with httpx.AsyncClient() as http_client:
                lookup_resp = await http_client.get(
                    f"{backend_url}/phone-numbers/lookup?number={called_number}",
                    timeout=10.0
                )
                logger.info(f"[Backend] Lookup response status: {lookup_resp.status_code}")
                
                if lookup_resp.status_code == 200:
                    lookup_data = lookup_resp.json()
                    logger.info(f"[Backend] Lookup success: {lookup_data}")
                    client_id = lookup_data.get("client_id")
                    
                    # Runtime validation before starting the voice agent
                    if not lookup_data.get("has_credits", True):
                        logger.warning(f"[Credits] Insufficient credits for {called_number}")
                        out_of_credits = True
                    elif lookup_data.get("agent_status") != "active":
                        logger.warning(f"[Agent] Assigned agent is not active (status={lookup_data.get('agent_status')})")
                        unassigned_number = True
                        custom_prompt = "The assigned agent is currently unavailable. Please try again later."
                    elif not lookup_data.get("agent_id"):
                        logger.warning(f"[Agent] No agent_id returned for {called_number}")
                        unassigned_number = True
                        custom_prompt = "This phone number is not fully configured. Please contact support."
                    elif not lookup_data.get("prompt"):
                        logger.warning(f"[Agent] No prompt configured for assigned agent on {called_number}")
                        unassigned_number = True
                        custom_prompt = "The assigned agent is not configured. Please contact support."
                    else:
                        custom_prompt = lookup_data.get("prompt")
                        agent_name = lookup_data.get("agent_name")
                        agent_id = lookup_data.get("agent_id")
                        logger.info(f"[Agent] Loaded agent '{agent_name}' for {called_number} (ID={agent_id})")
                elif lookup_resp.status_code == 404:
                    logger.warning(f"[Backend] PHONE_NUMBER_NOT_FOUND: {called_number}")
                    unassigned_number = True
                    try:
                        detail = lookup_resp.json().get("detail", {})
                        custom_prompt = detail.get("prompt", "This phone number is not configured in the system.")
                    except Exception:
                        custom_prompt = "This phone number is not configured in the system."
                elif lookup_resp.status_code == 409:
                    logger.warning(f"[Backend] PHONE_NOT_ASSIGNED: {called_number}")
                    unassigned_number = True
                    try:
                        detail = lookup_resp.json().get("detail", {})
                        custom_prompt = detail.get("prompt", "Welcome to 42 voice and we will get back to you.")
                    except Exception:
                        custom_prompt = "Welcome to 42 voice and we will get back to you."
                elif lookup_resp.status_code == 403:
                    logger.warning(f"[Backend] INSUFFICIENT_CREDITS: {called_number}")
                    out_of_credits = True
                else:
                    logger.error(f"[Backend] Lookup failed: status={lookup_resp.status_code}, body={lookup_resp.text}")
                    unassigned_number = True
                    custom_prompt = "An error occurred while processing your call. Please try again later."
        except Exception as e:
            logger.exception(f"[Backend] Exception during phone number lookup for {called_number}: {e}")
            unassigned_number = True
            custom_prompt = "An error occurred while processing your call. Please try again later."
    else:
        logger.warning("[SIP] No called number attribute found. Rejecting as unassigned.")
        unassigned_number = True
        custom_prompt = "This call cannot be routed. Please dial a configured phone number."
    
    # Validate required voice service configuration is present
    if not settings.deepgram_api_key or not settings.openai_api_key:
        logger.error("[Runtime] Missing required voice API keys (deepgram/openai)")
        unassigned_number = True
        custom_prompt = "Voice service configuration is incomplete. Please contact support."

    session_manager = SessionManager()
    booking_agent = BookingAgent(session_manager)
    sales_agent = SalesAgent(session_manager)
    support_agent = SupportAgent(session_manager)
    
    # Dynamic tools loading from database
    dynamic_tools = []
    if agent_id:
        try:
            if database.pool is None:
                await database.init_pool()
            
            # Fetch tool_ids from agents table
            agent_rows = await database.query("SELECT tool_ids FROM agents WHERE id = $1::uuid", [agent_id])
            if agent_rows:
                tool_ids = agent_rows[0].get("tool_ids") or []
                if isinstance(tool_ids, str):
                    tool_ids = json.loads(tool_ids)
                
                if tool_ids:
                    from api.modules.tools.repositories import ToolRepository
                    tool_repo = ToolRepository()
                    active_tools = await tool_repo.find_by_uuids(tool_ids)
                    
                    for tool in active_tools:
                        try:
                            # Parse definition config
                            definition = tool.get("definition") or {}
                            if isinstance(definition, str):
                                definition = json.loads(definition)
                            config = definition.get("config", {})
                            category = tool.get("category")
                            
                            # 1. Convert tool model to function schema
                            schema = tool_to_function_schema(tool)
                            func_name = schema["function"]["name"]
                            
                            # Define callback closure
                            def make_callback(t, cfg, cat):
                                async def tool_callback(**kwargs) -> str:
                                    logger.info(f"Custom tool callback executed: {t['name']} ({t['tool_uuid']}) with arguments: {kwargs}")
                                    
                                    # Handle Category-specific execution
                                    if cat == "http_api":
                                        # Play custom message if configured
                                        custom_message = cfg.get("customMessage", "")
                                        if custom_message:
                                            agent.session.say(custom_message)
                                        
                                        # Execute HTTP API call
                                        result = await execute_http_tool(
                                            tool=t,
                                            arguments=kwargs,
                                            call_context_vars={
                                                "phone_number": called_number,
                                                "customer_contact": participant.identity,
                                                "client_id": client_id,
                                                "room_name": room_name
                                            },
                                            gathered_context_vars={},
                                            client_id=client_id
                                        )
                                        return json.dumps(result)
                                        
                                    elif cat == "calculator":
                                        try:
                                            expr = kwargs.get("expression", "")
                                            val = safe_calculator(expr)
                                            return json.dumps({"expression": expr, "result": val})
                                        except Exception as err:
                                            return json.dumps({"error": str(err)})
                                            
                                    elif cat == "end_call":
                                        msg_type = cfg.get("messageType", "none")
                                        goodbye = ""
                                        if msg_type == "custom":
                                            goodbye = cfg.get("customMessage", "")
                                        if goodbye:
                                            if hasattr(agent.session, "interrupt"):
                                                agent.session.interrupt(force=True)
                                            agent.session.say(goodbye)
                                        
                                        async def delayed_disconnect():
                                            await asyncio.sleep(2.0 if goodbye else 0.5)
                                            if agent.ctx and agent.ctx.room:
                                                await agent.ctx.room.disconnect()
                                        asyncio.create_task(delayed_disconnect())
                                        return "Call is ending."
                                        
                                    elif cat == "transfer_call":
                                        try:
                                            resolved = await resolve_transfer_config(
                                                tool=t,
                                                config=cfg,
                                                arguments=kwargs,
                                                call_context_vars={
                                                    "phone_number": called_number,
                                                    "customer_contact": participant.identity,
                                                    "client_id": client_id,
                                                    "room_name": room_name
                                                },
                                                gathered_context_vars={},
                                                client_id=client_id
                                            )
                                            dest = resolved.destination
                                        except Exception as err:
                                            return f"Transfer resolution failed: {str(err)}"
                                        
                                        # Play message
                                        if resolved.message:
                                            agent.session.say(resolved.message)
                                        else:
                                            msg_type = cfg.get("messageType", "none")
                                            if msg_type == "custom":
                                                custom_msg = cfg.get("customMessage", "")
                                                if custom_msg:
                                                    agent.session.say(custom_msg)
                                        
                                        # Handoff/transfer call
                                        try:
                                            from livekit import api as lk_api
                                            lk_client = lk_api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
                                            transfer_req = lk_api.TransferSIPParticipantRequest(
                                                participant_identity=participant.identity,
                                                room_name=room_name,
                                                transfer_to=dest,
                                                play_dialtone=True
                                            )
                                            await lk_client.sip.transfer_sip_participant(transfer_req)
                                            await lk_client.aclose()
                                            
                                            async def delayed_disconnect():
                                                await asyncio.sleep(4.0)
                                                if agent.ctx and agent.ctx.room:
                                                    await agent.ctx.room.disconnect()
                                            asyncio.create_task(delayed_disconnect())
                                            return f"Transferring call to {dest}."
                                        except Exception as err:
                                            logger.error(f"SIP transfer failed: {err}")
                                            return f"Failed to transfer call: {str(err)}"
                                            
                                    elif cat == "mcp":
                                        url = cfg.get("url")
                                        if not url:
                                            return json.dumps({"status": "error", "error": "MCP server URL not configured"})
                                        
                                        # Resolve credential
                                        cred = None
                                        cred_uuid = cfg.get("credential_uuid")
                                        if cred_uuid and client_id:
                                            from api.modules.credentials.repositories import CredentialRepository
                                            cred = await CredentialRepository().find_by_uuid(cred_uuid, client_id)
                                        
                                        # Execute MCP call
                                        res = await call_mcp_tool(
                                            url=url,
                                            tool_name=t["name"],
                                            arguments=kwargs,
                                            credential=cred,
                                            config=cfg
                                        )
                                        return json.dumps(res)
                                        
                                    return "Tool not executed."
                                return tool_callback
                            
                            # Create RawFunctionTool wrapper using livekit function_tool helper
                            raw_tool = function_tool(
                                make_callback(tool, config, category),
                                raw_schema=schema["function"]
                            )
                            dynamic_tools.append(raw_tool)
                            logger.info(f"Dynamically registered custom tool: {func_name}")
                        except Exception as e:
                            logger.exception(f"Failed to initialize custom tool {tool.get('name')}: {e}")
        except Exception as e:
            logger.exception(f"Error fetching dynamic tools for agent {agent_id}: {e}")

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
        out_of_credits=out_of_credits,
        custom_prompt=custom_prompt,
        agent_name=agent_name,
        unassigned_number=unassigned_number,
        client_id=client_id,
        tools=dynamic_tools
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
    try:
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
        
        # Start recording AFTER session setup as a background task
        if getattr(agent.settings, "enable_recording", True):
            async def start_recording_task():
                try:
                    logger.info(f"Starting recording for room: {room_name}, participant: {participant.identity}")
                    egress_id, filename = await recording_service.start_room_recording(room_name)
                    agent.egress_id = egress_id
                    agent.recording_filename = filename
                    if egress_id:
                        logger.info(f"Recording started: egress_id={egress_id}, filename={filename}, room={room_name}")
                except Exception as e:
                    logger.error(f"Recording startup error for room {room_name}: {e}", exc_info=True)
            
            agent._recording_task = asyncio.create_task(start_recording_task())

        await session.start(room=ctx.room, agent=agent)
        logger.info("SESSION STARTED")
        await shutdown_event.wait()
    finally:
        shutdown_event.set()
        await cleanup_on_disconnect(session, session_manager)
        logger.info("Entrypoint exiting")


async def cleanup_on_disconnect(session, session_manager):
    """Async cleanup function called when participant disconnects."""
    try:
        if session:
            await session.aclose()
    except Exception as e:
        logger.warning(f"Error closing agent session: {e}")
        
    try:
        session_manager.clear_all_sessions()
    except Exception as e:
        logger.warning(f"Redis cleanup failed (may not be running): {e}")
    
    logger.info("SESSION CLEANED")


async def validate_worker_dependencies():
    """Validate all external dependencies before accepting LiveKit jobs."""
    settings = get_settings()
    logger.info("[Startup] Validating worker dependencies...")

    # 1. Validate BACKEND_URL format
    backend_url = settings.backend_url
    parsed = urlparse(backend_url)
    if not parsed.scheme or not parsed.netloc:
        logger.error(f"[Startup] Invalid BACKEND_URL: {backend_url}")
        sys.exit(1)

    # 2. Verify backend is reachable and database is healthy
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{backend_url}/health", timeout=10.0)
            logger.info(f"[Startup] Backend health response: {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"[Startup] Backend not healthy: {resp.status_code} {resp.text}")
                sys.exit(1)
            try:
                health_data = resp.json()
                db_status = health_data.get("data", {}).get("services", {}).get("database", {}).get("status")
                if db_status != "UP":
                    logger.error(f"[Startup] Backend database not UP: {db_status}")
                    sys.exit(1)
                logger.info("[Startup] Backend database is UP")
            except Exception as e:
                logger.warning(f"[Startup] Could not parse backend health DB status: {e}")
    except Exception as e:
        logger.error(f"[Startup] Backend is not reachable at {backend_url}: {e}")
        sys.exit(1)

    # 3. Verify LiveKit connection
    try:
        sip_status = await livekit_sip_service.get_sip_status()
        if not sip_status.get("connected"):
            logger.error(f"[Startup] LiveKit is not connected: {sip_status}")
            sys.exit(1)
        logger.info("[Startup] LiveKit is connected")
    except Exception as e:
        logger.error(f"[Startup] LiveKit connection check failed: {e}")
        sys.exit(1)

    # 4. Verify Redis connection (optional; SessionManager falls back to in-memory)
    try:
        redis_client = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=3, socket_timeout=3
        )
        redis_client.ping()
        redis_client.close()
        logger.info("[Startup] Redis is reachable")
    except Exception as e:
        logger.warning(f"[Startup] Redis is not reachable at {settings.redis_url}: {e}. Continuing with in-memory fallback.")

    logger.info("[Startup] All worker dependencies validated successfully")


if __name__ == "__main__":
    asyncio.run(validate_worker_dependencies())
    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            agent_name=settings.livekit_agent_name,
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
