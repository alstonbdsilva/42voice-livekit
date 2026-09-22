"""
LiveKit Voice AI Agent Worker.
Listens for SIP room creation and manages the AI audio pipeline.
"""
import asyncio
import contextlib
import re
import logging
import sys
import time
import warnings
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=".*HMAC key is.*")
warnings.filterwarnings("ignore", category=UserWarning, module="jwt")

load_dotenv()

import json
import httpx
from uuid import UUID
from enum import Enum
from datetime import datetime, date, timezone
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
    stt,
    TurnHandlingOptions,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

from config import get_settings
from transcript_service import transcript_service

logger = logging.getLogger("voice-agent")

_shared_http_client: Optional[httpx.AsyncClient] = None
_shared_http_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_shared_http_client() -> httpx.AsyncClient:
    """Return a shared, connection-pooled AsyncClient for worker internal requests.
    Safely re-creates client if closed or if running on a new event loop.
    """
    global _shared_http_client, _shared_http_client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if (
        _shared_http_client is None
        or _shared_http_client.is_closed
        or _shared_http_client_loop != current_loop
    ):
        _shared_http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=300.0)
        )
        _shared_http_client_loop = current_loop
    return _shared_http_client



from name_service import build_stt_keywords, parse_caller_name, NameCaptureState


class _VoiceTiming:
    """Lightweight per-call monotonic timing for the live voice pipeline.

    Aggregates VAD / STT / LLM / TTS / playback milestones and emits a single
    [VOICE_TIMING] summary line per agent turn plus focused deltas. Lean by
    design: no per-frame or per-token logging.
    """

    def __init__(self) -> None:
        self._turn: Dict[str, Optional[float]] = {}
        self.last_user_speech_end: Optional[float] = None

    def mark(self, key: str) -> None:
        self._turn[key] = time.monotonic()

    def delta(self, key_a: str, key_b: str) -> Optional[int]:
        ta = self._turn.get(key_a)
        tb = self._turn.get(key_b)
        if ta is None or tb is None:
            return None
        return round((tb - ta) * 1000)

    def delta_from(self, key: str, base: Optional[float]) -> Optional[int]:
        if base is None:
            return None
        t = self._turn.get(key)
        if t is None:
            return None
        return round((t - base) * 1000)

    def reset_turn(self) -> None:
        self._turn = {}


def _fmt_ms(value: Optional[int]) -> str:
    return "n/a" if value is None else f"{value}ms"


def make_json_safe(obj: Any, parent_key: str = "") -> Any:
    """
    Recursively converts non-JSON-serializable types into JSON-safe primitives:
    - UUID -> str
    - datetime / date -> ISO 8601 string
    - Enum -> value
    - dict -> recursively convert values
    - list / tuple / set -> recursively convert entries
    - Primitive types (str, int, float, bool, None) -> returned as-is.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, UUID):
        if parent_key:
            logger.debug(f"[JSON_SAFE] field={parent_key} python_type=UUID")
        return str(obj)
    if isinstance(obj, (datetime, date)):
        if parent_key:
            logger.debug(f"[JSON_SAFE] field={parent_key} python_type={type(obj).__name__}")
        return obj.isoformat()
    if isinstance(obj, Enum):
        if parent_key:
            logger.debug(f"[JSON_SAFE] field={parent_key} python_type=Enum")
        return make_json_safe(obj.value, parent_key)
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v, str(k)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(x, parent_key) for x in obj]
    
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable by make_json_safe")


def sanitize_agent_prompt(prompt_text: Optional[str]) -> str:
    """
    Sanitize agent system prompt by removing stale VAPI instructions
    and aggressive spelling rules.
    """
    if not prompt_text:
        return ""
        
    cleaned = prompt_text
    # 1. Remove stale VAPI tool references
    vapi_patterns = [
        r"use\s+the\s+vapi[^\.\n]*[\.\n]?",
        r"vapi\.end_call[^\.\n]*[\.\n]?",
        r"endCall\s+function[^\.\n]*[\.\n]?",
        r"VAPI[^\.\n]*[\.\n]?"
    ]
    for pat in vapi_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        
    # 2. Remove aggressive spelling instructions
    spelling_patterns = [
        r"if\s+a\s+name\s+sounds\s+unfamiliar[^\.\n]*[\.\n]?",
        r"ask\s+for\s+spelling\s+on\s+any\s+name[^\.\n]*[\.\n]?",
        r"ask\s+for\s+spelling\s+before\s+storing[^\.\n]*[\.\n]?"
    ]
    for pat in spelling_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        
    return cleaned.strip()


def _build_tts(settings, agent_data: Optional[Dict[str, Any]] = None):
    """Build the configured TTS provider strictly from DB/UI agent configuration.

    The UI is the single source of truth for TTS provider, model, and voice.
    .env / settings contain ONLY API credentials (ELEVENLABS_API_KEY, CARTESIA_API_KEY).
    There are NO hidden defaults or silent fallbacks for provider, model, or voice.
    """
    if not agent_data or not isinstance(agent_data, dict):
        raise ValueError(
            "[TTS] Agent configuration is missing or invalid. TTS provider, model, and voice "
            "must be configured in the agent settings via the UI."
        )

    # 1. Resolve & Validate Provider
    raw_provider = agent_data.get("tts_provider")
    if not raw_provider or not str(raw_provider).strip():
        raise ValueError(
            "[TTS] TTS provider is not configured for this agent. "
            "Please select a TTS provider (ElevenLabs or Cartesia) in the agent settings."
        )
    provider = str(raw_provider).strip().lower()

    # 2. Resolve Model and Voice from agent_data
    agent_model = agent_data.get("tts_model")
    agent_voice_id = (
        agent_data.get("tts_voice_id")
        or agent_data.get("voice_id")
        or agent_data.get("voice")
        or agent_data.get("tts_voice")
    )
    agent_voice_name = agent_data.get("tts_voice_name") or agent_data.get("voice_name") or "default"

    if isinstance(agent_model, str):
        agent_model = agent_model.strip()
    if isinstance(agent_voice_id, str):
        agent_voice_id = agent_voice_id.strip()

    # 3. Provider-specific strict validation and construction
    if provider == "elevenlabs":
        if not agent_model:
            raise ValueError(
                "[TTS] ElevenLabs TTS model is not configured for this agent. "
                "Please select a model in the agent settings."
            )
        if not agent_voice_id:
            raise ValueError(
                "[TTS] ElevenLabs TTS voice_id is not configured for this agent. "
                "Please select a voice in the agent settings."
            )

        api_key = getattr(settings, "elevenlabs_api_key", None)
        if not api_key:
            raise RuntimeError(
                "[TTS] ELEVENLABS_API_KEY is not configured on the server. Set it in .env to use ElevenLabs TTS."
            )

        logger.info(
            f"[TTS_INIT] provider=elevenlabs model={agent_model} "
            f"voice_id={agent_voice_id} voice_name={agent_voice_name}"
        )

        return elevenlabs.TTS(
            api_key=api_key,
            voice_id=agent_voice_id,
            model=agent_model,
        )

    if provider == "cartesia":
        if not agent_model:
            raise ValueError(
                "[TTS] Cartesia TTS model is not configured for this agent. "
                "Please select a model in the agent settings."
            )
        if not agent_voice_id:
            raise ValueError(
                "[TTS] Cartesia TTS voice_id is not configured for this agent. "
                "Please select a voice in the agent settings."
            )

        cartesia_api_key = getattr(settings, "cartesia_api_key", None)
        if not cartesia_api_key:
            raise RuntimeError(
                "[TTS] CARTESIA_API_KEY is not configured on the server. Set it in .env to use Cartesia TTS."
            )

        logger.info(
            f"[TTS_INIT] provider=cartesia model={agent_model} "
            f"voice_id={agent_voice_id} voice_name={agent_voice_name}"
        )

        try:
            from livekit.plugins import cartesia as _cartesia
        except ImportError:
            raise RuntimeError(
                "[TTS] TTS provider is cartesia but 'livekit.plugins.cartesia' is not installed in this environment."
            )

        return _cartesia.TTS(
            api_key=cartesia_api_key,
            voice=agent_voice_id,
            model=agent_model,
        )

    raise ValueError(
        f"[TTS] Unsupported TTS provider '{provider}'. "
        f"Supported providers: 'elevenlabs', 'cartesia'. Configure the agent via the UI."
    )


class VoiceAgent(Agent):
    """Voice agent with orchestrator tools."""
    
    def __init__(self, session_manager, booking_agent, sales_agent, support_agent, settings, room_name: str, participant_id: str, ctx: JobContext, vad=None, out_of_credits: bool = False, custom_prompt: Optional[str] = None, agent_name: Optional[str] = None, unassigned_number: bool = False, client_id: Optional[str] = None, tools: Optional[list] = None, agent_data: Optional[Dict[str, Any]] = None):
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
        
        # Instantiate per-call NameCaptureState machine
        self.name_state = NameCaptureState(max_spelling_retries=2)
        self.captured_caller_name: Optional[str] = None

        # Transcript tracking
        self.transcript_session_id = None
        self.settings = get_settings()
        self.call_start = None
        self.agent_id = agent_data.get("id") if (agent_data and isinstance(agent_data, dict)) else None
        self._cleanup_lock = asyncio.Lock()
        self._cleanup_completed = False
        self._cleanup_in_progress = False
        self._call_registered = False
        self._call_registering = False
        self.egress_id = None
        self.recording_filename = None
        self._recording_task: Optional[asyncio.Task[Any]] = None
        
        # Build dynamic STT keyword hints from current agent configuration (known system entities only)
        stt_keywords = build_stt_keywords(agent_data)
        stt_lang = (agent_data.get("language") if agent_data and isinstance(agent_data, dict) and agent_data.get("language") else "en-US")

        logger.info(f"[STT_CONFIG_DEBUG] agent_data_keys={list(agent_data.keys()) if agent_data else []}")
        logger.info(f"[STT_CONFIG_DEBUG] resolved_agent_name={agent_data.get('name') or agent_data.get('agent_name') if agent_data else None}")
        logger.info(f"[STT_CONFIG_DEBUG] resolved_client_name={agent_data.get('client_name') if agent_data else None}")
        logger.info(f"[STT_CONFIG_DEBUG] generated_keywords={stt_keywords}")
        logger.info(f"[STT] Initializing Deepgram STT for agent '{self.agent_name}' (lang={stt_lang}) with {len(stt_keywords)} dynamic entity keywords: {stt_keywords}")
        
        # Use VAD from prewarm if provided, otherwise load it
        vad_instance = vad if vad else silero.VAD.load()
        
        clean_custom_prompt = sanitize_agent_prompt(custom_prompt)
        instructions = (
            "You are a billing notice voice. State that the account is out of credits and goodbye."
            if out_of_credits
            else (clean_custom_prompt if clean_custom_prompt else "You are the orchestrator agent. Start by asking how you can help the user today. Use your tools to route requests, handle booking, sales, and support, or end the call when the conversation is finished.")
        )
        
        # Append strict instructions for automatic call disconnection upon completion and name capture
        if not out_of_credits:
            instructions += (
                "\n\nCRITICAL CONVERSATION TERMINATION RULE:\n"
                "When the user indicates that the conversation is finished (e.g. saying 'thank you', 'goodbye', 'that's all', 'thanks a lot'), "
                "or immediately after you confirm/recap all details requested by the user, "
                "you MUST invoke the end_call tool to disconnect the call. Do NOT linger or ask repetitive questions once the user's request is resolved.\n\n"
                "### CALLER NAME CAPTURE RULES:\n"
                "- Capture the caller's name exactly as provided by the speech transcription.\n"
                "- Do not change, autocorrect, anglicize, or substitute a caller's name.\n"
                "- An unfamiliar name is NOT automatically an unclear name.\n"
                "- If the transcription clearly contains a name, accept it directly and continue.\n"
                "- Ask for spelling ONLY when the speech/transcription is genuinely ambiguous or incomplete.\n"
                "- When asking for spelling, request letters one at a time.\n"
                "- Retry spelling no more than twice. Never create an infinite spelling loop.\n"
                "- If spelling cannot be captured after the allowed retries, continue gracefully using the clearest available caller-provided name or omit it.\n"
                "- Never invent a spelling.\n"
                "- If the caller asks for a person whose name is unclear or differs from the configured recipient or team, ask a polite, neutral clarification question using the configured name. Do NOT assert or rewrite what the caller said."
            )

        # Filter dynamic tools to avoid duplicate function names with built-in @function_tool methods
        builtin_tool_names = {
            "end_call", "route_request", "handle_booking_request", "handle_sales_inquiry",
            "handle_support_request", "return_to_orchestrator", "handle_booking_confirmation",
            "handle_booking_cancellation", "provide_product_recommendation", "handle_pricing_inquiry",
            "escalate_to_human", "troubleshoot_issue", "handle_billing_inquiry", "escalate_issue",
            "confirm_resolution"
        }
        
        seen_names = set(builtin_tool_names)
        filtered_tools = []
        if tools:
            for t in tools:
                t_name = ""
                if hasattr(t, "info") and hasattr(t.info, "name"):
                    t_name = t.info.name
                elif hasattr(t, "name"):
                    t_name = t.name
                elif hasattr(t, "__name__"):
                    t_name = t.__name__
                
                if t_name and t_name not in seen_names:
                    seen_names.add(t_name)
                    filtered_tools.append(t)

        stt_kwargs: Dict[str, Any] = {
            "model": "nova-2-phonecall",
            "language": stt_lang,
            "smart_format": True,
            "interim_results": True,
            # Deepgram only closes an utterance (is_final/speech_final) after
            # this much trailing silence. The tiny 25ms default caused ordinary
            # word pauses inside a phrase (e.g. "This is Lopez.") to be
            # finalized as several separate utterances, producing multiple
            # user turns and duplicated transcript text per statement.
            "endpointing_ms": 500,
        }
        if stt_keywords:
            stt_kwargs["keywords"] = stt_keywords

        # Resolve TTS provider/model/voice (ElevenLabs or Cartesia) from
        # agent_data first, falling back to environment defaults.
        tts = _build_tts(self.settings, agent_data)
        super().__init__(
            vad=vad_instance,
            stt=deepgram.STT(**stt_kwargs),
            llm=openai.LLM(
                model=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                temperature=self.settings.openai_temperature,
            ),
            tts=tts,
            instructions=instructions,
            tools=filtered_tools
        )


        
        # Track if greeting has been sent to prevent duplicate greetings
        self._greeting_sent = False

        # Per-call voice pipeline timing harness (see _instrument_voice_timing)
        self._vt = _VoiceTiming()
    
    def stt_node(self, audio, model_settings):
        return self._filtered_stt_events(audio, model_settings)

    async def _filtered_stt_events(self, audio, model_settings):
        """Wrap the default STT node to fix two production issues:

        1. Deepgram emits one FINAL per endpointing silence window, so a
           phrase containing pauses over 25ms produced several FINAL events
           that were each accumulated into the user turn ("This This is This
           is Lopez.") and could commit multiple turns per statement. Finals
           are now coalesced per utterance and a single complete FINAL is
           emitted when the utterance ends.

        2. STT events produced while the agent is speaking (telco echo /
           crosstalk on the PSTN path) used to reach the activity's
           audio-activity interruption handler and pause or cancel the
           agent's TTS mid-sentence. Those events are now dropped while the
           agent is speaking; real barge-in is unaffected because it is
           driven by VAD interruption, not by STT events.
        """
        raw_res = Agent.default.stt_node(self, audio, model_settings)
        raw_generator = await raw_res if asyncio.iscoroutine(raw_res) else raw_res
        iterator = raw_generator.__aiter__()

        async def _fetch_next(it):
            return await it.__anext__()

        get_next = asyncio.create_task(_fetch_next(iterator))
        timer_task: Optional[asyncio.Task] = None
        pending_final: Optional[stt.SpeechEvent] = None
        utterance_interim_at: Optional[float] = None
        last_emitted_final_text: Optional[str] = None
        speech_ended: bool = False

        def _agent_speaking() -> bool:
            try:
                return self.session.agent_state == "speaking"
            except Exception:
                return False

        def _cancel_timer():
            nonlocal timer_task
            if timer_task is not None:
                timer_task.cancel()
                timer_task = None

        def _rearm_timer():
            nonlocal timer_task
            _cancel_timer()
            # 150ms debounce minimal coalescing delay for rapid trailing Deepgram finals
            timer_task = asyncio.create_task(asyncio.sleep(0.15))

        try:
            while True:
                wait_for = [get_next]
                if timer_task is not None:
                    wait_for.append(timer_task)
                done, _ = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

                if timer_task in done:
                    if pending_final is not None:
                        text = pending_final.alternatives[0].text.strip() if pending_final.alternatives else ""
                        logger.info(
                            f"[STT_FIX] final_flush timer elapsed=0.150s "
                            f"interim_delta={time.perf_counter() - (utterance_interim_at or time.perf_counter()):.3f}s "
                            f"text=\"{text}\""
                        )
                        last_emitted_final_text = text
                        yield pending_final
                        pending_final = None
                    _cancel_timer()
                    continue

                try:
                    ev = get_next.result()
                except StopAsyncIteration:
                    if pending_final is not None:
                        yield pending_final
                    break

                get_next = asyncio.create_task(_fetch_next(iterator))

                if not isinstance(ev, stt.SpeechEvent):
                    yield ev
                    continue

                speaking = _agent_speaking()

                if ev.type == stt.SpeechEventType.START_OF_SPEECH:
                    speech_ended = False
                    pending_final = None
                    last_emitted_final_text = None
                    utterance_interim_at = None
                    _cancel_timer()
                    if not speaking:
                        yield ev
                    continue

                if ev.type == stt.SpeechEventType.END_OF_SPEECH:
                    speech_ended = True
                    if not speaking and pending_final is not None:
                        text = pending_final.alternatives[0].text.strip() if pending_final.alternatives else ""
                        logger.info(f"[STT_FIX] immediate final_flush on END_OF_SPEECH text=\"{text}\"")
                        last_emitted_final_text = text
                        yield pending_final
                        pending_final = None
                    _cancel_timer()
                    if not speaking:
                        yield ev
                    continue

                if ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    if not ev.alternatives or not ev.alternatives[0].text.strip():
                        _cancel_timer()
                        continue
                    text = ev.alternatives[0].text.strip()
                    # Prevent duplicate final events from creating duplicate LLM requests
                    if text == last_emitted_final_text:
                        logger.debug(f"[STT_FIX] dropping duplicate final transcript: '{text}'")
                        _cancel_timer()
                        continue
                    if speaking:
                        pending_final = None
                        utterance_interim_at = None
                        _cancel_timer()
                    elif speech_ended:
                        logger.info(f"[STT_FIX] immediate final_flush (speech_ended) text=\"{text}\"")
                        last_emitted_final_text = text
                        pending_final = None
                        _cancel_timer()
                        yield ev
                    else:
                        pending_final = ev
                        _rearm_timer()
                    continue

                if ev.type == stt.SpeechEventType.INTERIM_TRANSCRIPT:
                    if not speaking:
                        if utterance_interim_at is None:
                            utterance_interim_at = time.perf_counter()
                            logger.info(
                                f"[STT_FIX] interim_first elapsed={time.perf_counter():.3f}s "
                                f"text=\"{ev.alternatives[0].text}\""
                            )
                        # Suppress duplicates if this final text has already been emitted for this utterance
                        cand_text = ev.alternatives[0].text.strip().lower() if ev.alternatives else ""
                        if last_emitted_final_text and cand_text == last_emitted_final_text:
                            pending_final = None
                            continue

                        # If speech has already ended, flush the final transcript immediately without delay
                        if speech_ended:
                            if timer_task is not None:
                                timer_task.cancel()
                                timer_task = None
                            last_emitted_final_text = cand_text
                            yield ev
                            pending_final = None
                        elif timer_task is None:
                            # 150ms debounce window while speech continues
                            timer_task = asyncio.create_task(asyncio.sleep(0.15))
        finally:
            if timer_task is not None:
                timer_task.cancel()
            get_next.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(get_next, return_exceptions=True)
                await raw_generator.aclose()

    async def llm_node(self, chat_ctx, tools, model_settings):
        """Thin timing wrapper over the default LLM node (behavior unchanged)."""
        raw_res = Agent.default.llm_node(self, chat_ctx, tools, model_settings)
        raw = await raw_res if asyncio.iscoroutine(raw_res) else raw_res
        vt = self._vt
        first = True
        try:
            async for chunk in raw:
                if first:
                    first = False
                    vt.mark("llm_first_token")
                    logger.info("[VOICE_TIMING] llm_first_token")
                yield chunk
            vt.mark("llm_complete")
            logger.info("[VOICE_TIMING] llm_complete")
        except Exception:
            logger.info("[VOICE_TIMING] llm_error")
            raise

    async def tts_node(self, text, model_settings):
        """Thin timing wrapper over the default TTS node (behavior unchanged)."""
        raw_res = Agent.default.tts_node(self, text, model_settings)
        raw = await raw_res if asyncio.iscoroutine(raw_res) else raw_res
        vt = self._vt
        first = True
        try:
            async for frame in raw:
                if first:
                    first = False
                    vt.mark("tts_first_audio")
                    logger.info("[VOICE_TIMING] tts_first_audio")
                yield frame
            vt.mark("tts_complete")
            logger.info("[VOICE_TIMING] tts_complete")
        except Exception:
            logger.info("[VOICE_TIMING] tts_error")
            raise

    def _instrument_voice_timing(self) -> None:
        """Wire lightweight [VOICE_TIMING] metrics to session events."""
        self._vt = _VoiceTiming()
        self.session.on("user_state_changed", self._on_user_state_changed_timing)
        self.session.on("agent_state_changed", self._on_agent_state_changed_timing)
        self.session.on("user_input_transcribed", self._on_user_input_transcribed_timing)
        self.session.on("agent_false_interruption", self._on_false_interruption_timing)

    def _on_user_state_changed_timing(self, ev) -> None:
        vt = self._vt
        if ev.new_state == "speaking":
            if ev.old_state != "speaking":
                vt.reset_turn()
            vt.mark("vad_start")
            vt.mark("speech_start")
            try:
                if self.session.agent_state == "speaking":
                    logger.info("[VOICE_TIMING] interruption_detected barge_in")
            except Exception:
                pass
        elif ev.old_state == "speaking":
            vt.mark("vad_end")
            vt.mark("speech_end")
            vt.last_user_speech_end = time.monotonic()
            logger.info("[VOICE_TIMING] user speech_end")

    def _on_agent_state_changed_timing(self, ev) -> None:
        vt = self._vt
        if ev.new_state == "thinking" and ev.old_state in ("listening", "idle"):
            vt.mark("llm_start")
            d = vt.delta_from("llm_start", vt.last_user_speech_end)
            logger.info(f"[VOICE_TIMING] llm_start speech_end_delta={_fmt_ms(d)}")
        elif ev.new_state == "speaking":
            vt.mark("playback_start")
            if vt.last_user_speech_end is not None:
                self._log_turn_summary(vt)
        elif ev.old_state == "speaking" and ev.new_state in ("listening", "idle"):
            vt.mark("playback_complete")
            logger.info("[VOICE_TIMING] playback_complete")

    def _on_user_input_transcribed_timing(self, ev) -> None:
        vt = self._vt
        if not ev.is_final:
            if vt._turn.get("stt_first_interim") is None:
                vt.mark("stt_first_interim")
                d = vt.delta_from("stt_first_interim", vt.last_user_speech_end)
                logger.info(f"[VOICE_TIMING] stt_first_interim speech_end_delta={_fmt_ms(d)}")
        else:
            vt.mark("stt_final")
            d = vt.delta_from("stt_final", vt.last_user_speech_end)
            logger.info(f"[VOICE_TIMING] stt_final speech_end_delta={_fmt_ms(d)} final=\"{ev.transcript}\"")

    def _on_false_interruption_timing(self, ev) -> None:
        logger.info(f"[VOICE_TIMING] interruption_detected false_interruption resumed={ev.resumed}")

    def _log_turn_summary(self, vt: _VoiceTiming) -> None:
        ttfa = vt.delta_from("playback_start", vt.last_user_speech_end)
        if ttfa is not None:
            if not hasattr(self, '_turn_latencies'):
                self._turn_latencies = []
            self._turn_latencies.append(ttfa)
        logger.info(
            f"[VOICE_TIMING] [session={self.room_name} agent={self.agent_id or self.agent_name}] "
            f"TTFA={_fmt_ms(ttfa)} | "
            f"speech_end_to_stt_final={_fmt_ms(vt.delta_from('stt_final', vt.last_user_speech_end))} | "
            f"stt_final_to_llm_start={_fmt_ms(vt.delta('stt_final', 'llm_start'))} | "
            f"llm_start_to_llm_first_token={_fmt_ms(vt.delta('llm_start', 'llm_first_token'))} | "
            f"llm_start_to_tts_first_audio={_fmt_ms(vt.delta('llm_start', 'tts_first_audio'))} | "
            f"tts_first_audio_to_playback_start={_fmt_ms(vt.delta('tts_first_audio', 'playback_start'))}"
        )

    # Note: before_llm_generation, after_llm_generation, before_tts_synthesis, 
    # after_tts_synthesis, on_user_speech_committed hooks are NOT available in 1.5.13
    # These were removed as they don't exist in this version
    
    async def on_enter(self):
        """Greet the user when the agent joins the room."""
        logger.info("on_enter called")
        from datetime import datetime, timezone
        self.call_start = datetime.now(timezone.utc)

        # Attach lightweight voice timing metrics (idempotent per call)
        self._instrument_voice_timing()
        
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
                logger.info("[Greeting] Sending greeting")
                greeting = f"Hello! I am {self.agent_name}. How can I assist you today?" if self.agent_name and self.agent_name != "unknown" else "Hello, how can I help you today?"
                self.session.say(greeting)
                
                # Broadcast greeting to live web client
                try:
                    if self.ctx.room and self.ctx.room.local_participant:
                        asyncio.create_task(self.ctx.room.local_participant.publish_data(
                            json.dumps({"type": "transcription", "speaker": "agent", "text": greeting}).encode("utf-8"),
                            topic="transcription"
                        ))
                except Exception as pub_err:
                    logger.warning(f"Could not publish greeting transcript packet: {pub_err}")

                self._greeting_sent = True
                logger.info(f"[Greeting] Greeting sent cleanly: {greeting}")
            except Exception as e:
                logger.error(f"Error in on_enter: {e}")

        else:
            logger.info("Greeting already sent, skipping")
    
    async def on_exit(self):
        """Clean up when the agent exits. Idempotent single execution per call."""
        room_name = getattr(self, 'room_name', 'unknown')
        
        async with self._cleanup_lock:
            if self._cleanup_completed or self._cleanup_in_progress:
                logger.info(f"[CALL_CLEANUP] skipped_duplicate room={room_name}")
                return
            self._cleanup_in_progress = True

        try:
            logger.info(f"[CALL_CLEANUP] starting room={room_name}")
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
                    # Recover orphaned egress. LiveKit may have created the Egress
                    # server-side even though the local startup task was cancelled
                    # before egress_id was assigned (e.g. teardown timeout on a slow
                    # self-hosted egress). Clean up by room so this call's Egress does
                    # not continue uploading to S3. Room-scoped: never touches another
                    # room's recording.
                    logger.warning("Recording never started locally (egress_id is None); checking for orphaned egress")
                    try:
                        cleaned = await recording_service.cleanup_orphaned_egress(room_name)
                        if cleaned:
                            logger.info(f"Cleaned up {cleaned} orphaned egress session(s) for room: {room_name}")
                        else:
                            logger.info(f"No orphaned egress found for room: {room_name}")
                    except Exception as orphan_err:
                        logger.error(f"Orphaned egress cleanup failed for room: {room_name} error={orphan_err}", exc_info=True)
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
                        "room_name": getattr(self.session, 'room_name', room_name),
                        "participant_id": getattr(self.session, 'participant_id', getattr(self, 'participant_id', 'unknown')),
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
            
            # Dynamically register call details in database (bounded await before cleanup)
            if self.call_start:
                from datetime import datetime, timezone
                call_end = datetime.now(timezone.utc)
                try:
                    await asyncio.wait_for(
                        register_call_with_backend(self, self.call_start, call_end),
                        timeout=25.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[CALL_PERSIST] timeout room={room_name} error=timeout_during_shutdown")
                    logger.error(f"[CALL_PERSIST] failed room={room_name} error=timeout_during_shutdown")
                except Exception as e:
                    logger.error(f"[CALL_PERSIST] failed room={room_name} error={e}")

            # Clear session manager state for this call (safely)
            if hasattr(self, 'session_manager'):
                try:
                    self.session_manager.clear_all_sessions()
                except Exception as e:
                    logger.warning(f"Redis cleanup failed (may not be running): {e}")
            logger.info("SESSION CLEANED")
        finally:
            self._cleanup_completed = True
            self._cleanup_in_progress = False
    
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
                speech_handle = self.session.say(goodbye_msg)
            except Exception as e:
                logger.error(f"Error saying goodbye message: {e}")
                speech_handle = None
        else:
            speech_handle = None
                
        async def delayed_disconnect():
            if speech_handle and hasattr(speech_handle, "wait_for_playout"):
                try:
                    logger.info("Waiting for farewell speech playout to complete...")
                    await asyncio.wait_for(speech_handle.wait_for_playout(), timeout=8.0)
                    logger.info("Farewell speech playout completed.")
                except Exception as wait_err:
                    logger.warning(f"Timeout or error waiting for farewell playout: {wait_err}")
            else:
                await asyncio.sleep(0.5)

            logger.info("Disconnecting room via end_call tool after farewell playout")
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
                        "model": settings.openai_model,
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
    room_name = getattr(agent, 'room_name', 'unknown')
    
    if not started_at:
        logger.warning(f"[CALL_PERSIST] skipped_no_start room={room_name}")
        return

    # Check idempotency
    if getattr(agent, '_call_registered', False) or getattr(agent, '_call_registering', False):
        logger.info(f"[CALL_PERSIST] skipped_duplicate room={room_name}")
        return
    
    agent._call_registering = True
    t_persist_start = time.perf_counter()
    logger.info(f"[CALL_PERSIST] start room={room_name}")
    
    try:
        import httpx
        from datetime import datetime
        
        duration = max(0, int((ended_at - started_at).total_seconds()))
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
            
        recording_enabled = getattr(agent.settings, "enable_recording", True)
        filename = getattr(agent, 'recording_filename', None)
        egress_id = getattr(agent, 'egress_id', None)
        s3_key = None
        size = 0
        
        llm_coro = analyze_transcript_with_llm(full_text, agent.settings)

        if recording_enabled and filename and egress_id:
            s3_key = f"recordings/{filename}"
            from recording_service import recording_service
            s3_coro = recording_service.verify_s3_upload(s3_key)
            ai_metrics, s3_result = await asyncio.gather(llm_coro, s3_coro)

            # Extract verification and size directly from verify_s3_upload without redundant head_object
            if hasattr(s3_result, "verified"):
                upload_verified = s3_result.verified
                size = s3_result.size if (upload_verified and s3_result.size > 0) else (duration * 16000)
            elif isinstance(s3_result, tuple):
                upload_verified = s3_result[0]
                size = s3_result[1] if (upload_verified and len(s3_result) > 1 and s3_result[1]) else (duration * 16000)
            else:
                upload_verified = bool(s3_result)
                size = duration * 16000 if upload_verified else 0

            if not upload_verified:
                logger.warning(f"S3 upload verification failed for {s3_key}")
                size = duration * 16000
        else:
            ai_metrics = await llm_coro
            
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
            "agentId": getattr(agent, 'agent_id', None),
            "clientId": getattr(agent, 'client_id', None),
            "roomName": room_name,
            "agentName": agent_name,
            "customerName": getattr(agent, 'captured_caller_name', None) or "Customer",
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
        
        safe_payload = make_json_safe(payload)
        backend_url = agent.settings.backend_url
        registered_success = False
        try:
            async with httpx.AsyncClient() as client:
                t_http_start = time.perf_counter()
                logger.info(f"[CALL_PERSIST] http_dispatch room={room_name}")
                response = await client.post(f"{backend_url}/conversations/register", json=safe_payload, timeout=20.0,
                                             headers={
                                                 "Authorization": f"Bearer {get_settings().internal_worker_token}" if get_settings().internal_worker_token else None
                                             })
                http_duration = time.perf_counter() - t_http_start
                logger.info(f"[CALL_PERSIST] http_response room={room_name} status={response.status_code} duration={http_duration:.3f}s")
                if response.status_code in [200, 201]:
                    registered_success = True
                    agent._call_registered = True
                    logger.info(f"[CALL_PERSIST] success room={room_name} status={response.status_code}")
                else:
                    logger.error(f"[CALL_PERSIST] failed room={room_name} status={response.status_code} error=status_{response.status_code}_{response.text}")
        except httpx.TimeoutException as te:
            logger.error(f"[CALL_PERSIST] timeout room={room_name} error=http_timeout_{te}")
            logger.error(f"[CALL_PERSIST] failed room={room_name} error=http_timeout")
        except Exception as exec_err:
            logger.error(f"[CALL_PERSIST] failed room={room_name} error={exec_err}")

        logger.info(f"[CALL_PERSIST] completed room={room_name} elapsed={time.perf_counter() - t_persist_start:.3f}s success={registered_success}")
        
        if agent.transcript_session_id:
            transcript_service.clear_session(agent.transcript_session_id)
                
    except Exception as e:
        logger.error(f"[CALL_PERSIST] failed room={room_name} error={e}", exc_info=True)
    finally:
        agent._call_registering = False



def prewarm(proc: JobProcess):
    """Preload VAD model to reduce startup time."""
    t0 = time.perf_counter()
    proc.userdata["vad"] = silero.VAD.load()
    logger.info(f"[CALL_TIMING] prewarm_vad_loaded elapsed={time.perf_counter() - t0:.3f}s")


async def entrypoint(ctx: JobContext):
    """Entry point for LiveKit agent jobs."""
    t_start = time.perf_counter()
    settings = get_settings()
    room_name = ctx.room.name
    job_id = getattr(getattr(ctx, 'job', None), 'id', room_name)
    logger.info(f"[CALL_TIMING] job={job_id} stage=T6_agent_entrypoint_started room={room_name} elapsed=0.000s")
    
    db_init_task = None
    current_loop = asyncio.get_running_loop()
    if database.pool is None or (hasattr(database.pool, "_loop") and (database.pool._loop.is_closed() or database.pool._loop != current_loop)):
        db_init_task = asyncio.create_task(database.init_pool())

    t_conn_start = time.perf_counter()
    logger.info(f"Connecting to room {room_name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"[CALL_TIMING] job={job_id} stage=room_connect_done total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_conn_start:.3f}s")
    
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
    t_imp = time.perf_counter()
    from session_manager import SessionManager
    from agents.booking_agent import BookingAgent
    from agents.sales_agent import SalesAgent
    from agents.support_agent import SupportAgent
    from recording_service import recording_service
    logger.info(f"[CALL_TIMING] job={job_id} stage=imports_done total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_imp:.3f}s")
    
    # Wait for the first participant to connect
    t_part_wait = time.perf_counter()
    try:
        participant = await ctx.wait_for_participant()
    except Exception as e:
        logger.warning(f"No participant connected to room {room_name}: {e}")
        return

    logger.info(f"[CALL_TIMING] job={job_id} stage=T7_participant_connected total_elapsed={time.perf_counter() - t_start:.3f}s wait_step={time.perf_counter() - t_part_wait:.3f}s participant={participant.identity}")
    
    # 1. Resolve the called phone number from SIP participant attributes
    backend_url = settings.backend_url
    out_of_credits = False
    custom_prompt = None
    agent_name = None  # Must be explicitly set from phone number lookup
    unassigned_number = False
    client_id = None
    agent_id = None
    # Full agent row loaded once per call and reused for tool loading, STT
    # keyword hints and TTS selection (avoids duplicate agents/clients reads).
    agent_config_data: Dict[str, Any] = {}
    
    # Check metadata first (passed during outbound call dispatches or Web calls)
    call_metadata = {}
    try:
        if participant.metadata:
            call_metadata = json.loads(participant.metadata)
        elif hasattr(ctx, 'job') and getattr(ctx.job, 'metadata', None):
            call_metadata = json.loads(ctx.job.metadata)
    except Exception as meta_err:
        logger.warning(f"[Metadata] Failed to parse metadata: {meta_err}")

    target_agent_id = (
        call_metadata.get("agent_id")
        or (participant.attributes.get("sip.header.X-Agent-Id") if hasattr(participant, "attributes") and participant.attributes else None)
        or (participant.attributes.get("sip.header.x-agent-id") if hasattr(participant, "attributes") and participant.attributes else None)
    )
    
    called_number = (
        participant.attributes.get("sip.trunkPhoneNumber") or
        participant.attributes.get("sip.toUser") or
        participant.attributes.get("sip.to") or
        participant.attributes.get("sip.phoneNumber")
    )
    logger.info("[SIP] Participant Connected")
    logger.info(f"[SIP] Participant identity: {participant.identity}")
    logger.info(f"[SIP] Participant attributes: {participant.attributes}")
    logger.info(f"[SIP] Resolved called_number: {called_number}, target_agent_id in metadata: {target_agent_id}")
    
    t_db = time.perf_counter()
    if db_init_task is not None:
        try:
            await db_init_task
        except Exception as e:
            logger.warning(f"Error awaiting concurrent DB pool init: {e}")
    elif database.pool is None or (hasattr(database.pool, "_loop") and (database.pool._loop.is_closed() or database.pool._loop != current_loop)):
        await database.init_pool()
    logger.info(f"[CALL_TIMING] job={job_id} stage=db_ready total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_db:.3f}s")

    # Case A: Explicit agent_id provided in metadata (Outbound call or Web Agent session)
    t_agent_cfg = time.perf_counter()
    if target_agent_id:
        logger.info(f"[Agent] Target agent_id '{target_agent_id}' provided in metadata. Loading agent configuration directly...")
        try:
            agent_rows = await database.query(
                "SELECT a.*, c.name AS client_name "
                "FROM agents a LEFT JOIN clients c ON c.id = a.client_id "
                "WHERE a.id = $1::uuid",
                [target_agent_id]
            )
            if agent_rows:
                ag_data = agent_rows[0]
                # Reuse the full row for tools/STT keywords/TTS instead of refetching it later
                agent_config_data = dict(ag_data)
                agent_id = str(ag_data.get("id"))
                agent_name = ag_data.get("name", "Voice Agent")
                use_case = ag_data.get("use_case", "")
                activity_desc = ag_data.get("activity_description", "")
                custom_guardrails = ag_data.get("custom_guardrails", "")
                knowledge_items = ag_data.get("knowledge_items", [])
                if isinstance(knowledge_items, str):
                    try:
                        knowledge_items = json.loads(knowledge_items)
                    except Exception:
                        knowledge_items = []
                client_id = str(ag_data.get("client_id")) if ag_data.get("client_id") else None

                prompt_parts = [f"You are {agent_name}, an AI voice assistant."]
                if use_case:
                    prompt_parts.append(f"Use Case: {use_case}")
                if activity_desc:
                    prompt_parts.append(f"System Instructions:\n{activity_desc}")
                if custom_guardrails:
                    prompt_parts.append(f"Guardrails:\n{custom_guardrails}")
                if knowledge_items and isinstance(knowledge_items, list):
                    kb_lines = [f"- {k.get('label', '')}: {k.get('value', '')}" for k in knowledge_items if isinstance(k, dict)]
                    if kb_lines:
                        prompt_parts.append("Knowledge Base:\n" + "\n".join(kb_lines))

                custom_prompt = "\n\n".join(prompt_parts)
                unassigned_number = False
                logger.info(f"[Agent] Successfully loaded configuration for agent '{agent_name}' ({agent_id})")
            else:
                logger.error(f"[Agent] Target agent ID '{target_agent_id}' not found in database.")
                raise RuntimeError(f"[Agent] Target agent ID '{target_agent_id}' not found in database.")
        except Exception as db_err:
            logger.critical(f"[Agent] Database error fetching agent '{target_agent_id}': {db_err}")
            raise RuntimeError(f"[Agent] Database error fetching agent '{target_agent_id}': {db_err}") from db_err
            
    # Case B: Inbound call to a phone number (Lookup assigned agent via called_number)
    elif called_number:
        logger.info(f"[Backend] Starting routing lookup for inbound call to {called_number} at {backend_url}/phone-numbers/lookup")
        try:
            http_client = get_shared_http_client()
            lookup_resp = await http_client.get(
                f"{backend_url}/phone-numbers/lookup",
                params={"number": called_number},
                timeout=10.0
            )
            logger.info(f"[INBOUND_DEBUG] lookup_status={lookup_resp.status_code} called_number={called_number}")

            if lookup_resp.status_code == 200:
                lookup_data = lookup_resp.json()
                logger.info(f"[INBOUND_DEBUG] lookup_success: {lookup_data}")
                client_id = lookup_data.get("client_id")
                target_agent_id = lookup_data.get("agent_id")
                
                if not lookup_data.get("has_credits", True):
                    logger.warning(f"[Credits] Insufficient credits for {called_number}")
                    out_of_credits = True
                elif lookup_data.get("agent_status") != "active":
                    logger.warning(f"[Agent] Assigned agent is not active (status={lookup_data.get('agent_status')})")
                    unassigned_number = True
                    custom_prompt = "The assigned agent is currently unavailable. Please try again later."
                elif not target_agent_id:
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
                    agent_id = target_agent_id
                    agent_config_data = dict(lookup_data)
                    agent_config_data["id"] = target_agent_id
                    client_id = lookup_data.get("client_id")
                    logger.info(f"[INBOUND_DEBUG] Loaded agent '{agent_name}' for {called_number} (ID={agent_id})")
            elif lookup_resp.status_code == 404:
                logger.warning(f"[INBOUND_DEBUG] PHONE_NUMBER_NOT_FOUND: {called_number}")
                unassigned_number = True
                try:
                    detail = lookup_resp.json().get("detail", {})
                    custom_prompt = detail.get("prompt", "This phone number is not configured in the system.")
                except Exception:
                    custom_prompt = "This phone number is not configured in the system."
            elif lookup_resp.status_code == 409:
                logger.warning(f"[INBOUND_DEBUG] PHONE_NOT_ASSIGNED: {called_number}")
                unassigned_number = True
                try:
                    detail = lookup_resp.json().get("detail", {})
                    custom_prompt = detail.get("prompt", "Welcome to 42 voice and we will get back to you.")
                except Exception:
                    custom_prompt = "Welcome to 42 voice and we will get back to you."
            elif lookup_resp.status_code == 403:
                logger.warning(f"[INBOUND_DEBUG] INSUFFICIENT_CREDITS: {called_number}")
                out_of_credits = True
            else:
                logger.error(f"[INBOUND_DEBUG] Lookup failed: status={lookup_resp.status_code}, body={lookup_resp.text}")
                unassigned_number = True
                custom_prompt = "An error occurred while processing your call. Please try again later."
        except Exception as e:
            logger.exception(f"[INBOUND_DEBUG] Exception during phone number lookup for {called_number}: {e}")
            unassigned_number = True
            custom_prompt = "An error occurred while processing your call. Please try again later."
    else:
        logger.warning("[Routing] Neither agent_id metadata nor called_number found.")
        unassigned_number = True
        custom_prompt = "This call cannot be routed. Please dial a configured phone number or select an agent."

    # Load the full agent row once (inbound path) so tool_ids, STT keyword hints
    # and TTS configuration all come from a single query instead of the previous
    # tool_ids + full-agent + client_name sequence.
    if agent_id and not agent_config_data:
        try:
            ag_rows = await database.query(
                "SELECT a.*, c.name AS client_name "
                "FROM agents a LEFT JOIN clients c ON c.id = a.client_id "
                "WHERE a.id = $1::uuid",
                [agent_id]
            )
            if ag_rows:
                agent_config_data = dict(ag_rows[0])
        except Exception as ag_err:
            logger.warning(f"[AgentConfig] Warning loading agent_config_data for STT keywords: {ag_err}")
    logger.info(f"[CALL_TIMING] job={job_id} stage=agent_config_ready total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_agent_cfg:.3f}s")

    # Validate required voice service configuration is present
    if not settings.deepgram_api_key or not settings.openai_api_key:
        logger.error("[Runtime] Missing required voice API keys (deepgram/openai)")
        unassigned_number = True
        custom_prompt = "Voice service configuration is incomplete. Please contact support."

    t_redis = time.perf_counter()
    session_manager = SessionManager()
    booking_agent = BookingAgent(session_manager)
    sales_agent = SalesAgent(session_manager)
    support_agent = SupportAgent(session_manager)
    logger.info(f"[CALL_TIMING] job={job_id} stage=redis_ready total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_redis:.3f}s")

    # Dynamic tools loading from database
    t_tools = time.perf_counter()
    dynamic_tools = []
    if agent_id:
        try:
            # Reuse tool_ids from the already-loaded agent row (no extra query)
            tool_ids = (agent_config_data.get("tool_ids") if isinstance(agent_config_data, dict) else None) or []
            if isinstance(tool_ids, str):
                try:
                    tool_ids = json.loads(tool_ids)
                except Exception:
                    tool_ids = []
                
            if tool_ids and isinstance(tool_ids, list):
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

    logger.info(f"[CALL_TIMING] job={job_id} stage=tools_loaded total_elapsed={time.perf_counter() - t_start:.3f}s step={time.perf_counter() - t_tools:.3f}s")

    # Create agent session with VAD from prewarm (aggressive low latency settings)
    logger.info("Creating AgentSession")
    session: AgentSession = AgentSession(
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            interruption={
                "mode": "vad",
                "min_duration": 0.4,
                "resume_false_interruption": True,
            },
            endpointing={
                "min_delay": 0.3,
            }
        ),
    )
    
    logger.info(f"[CALL_TIMING] job={job_id} stage=agent_session_created total_elapsed={time.perf_counter() - t_start:.3f}s")

    # Ensure the client display name is resolved for STT keyword hints when the
    # agent row was loaded without it (Case A). agent_config_data is already
    # fully populated from a single query on the inbound path - no re-fetch.
    if isinstance(agent_config_data, dict) and agent_config_data and "client_name" not in agent_config_data:
        try:
            c_id = agent_config_data.get("client_id")
            if c_id:
                c_rows = await database.query("SELECT name FROM clients WHERE id = $1::uuid", [c_id])
                if c_rows:
                    agent_config_data["client_name"] = c_rows[0].get("name")
        except Exception as ag_err:
            logger.warning(f"[AgentConfig] Warning loading client_name for STT keywords: {ag_err}")

    # Explicitly validate that agent configuration is loaded before constructing VoiceAgent
    if not agent_config_data or not isinstance(agent_config_data, dict):
        raise RuntimeError(
            f"[Agent] Failed to initialize VoiceAgent for room '{ctx.room.name}': "
            f"Agent configuration could not be loaded from database."
        )

    # Fallback to lookup data fields if agent_config_data keys are missing
    if agent_name and "name" not in agent_config_data and "agent_name" not in agent_config_data:
        agent_config_data["agent_name"] = agent_name
    if client_id and "client_id" not in agent_config_data:
        agent_config_data["client_id"] = client_id

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
        tools=dynamic_tools,
        agent_data=agent_config_data
    )
    
    # Safe, non-blocking prewarming of TTS connection while session initializes.
    # Cartesia TTS uses an internal connection pool with official .prewarm() support.
    # ElevenLabs TTS establishes a persistent WebSocket connection via ._current_connection().
    # Note: VoiceAgent and TTS instances are allocated fresh per call, so no audio state
    # or voice configuration is shared between concurrent calls.
    if hasattr(agent, "tts") and agent.tts:
        if hasattr(agent.tts, "_pool") and hasattr(agent.tts._pool, "prewarm"):
            try:
                agent.tts._pool.prewarm()
                logger.info("[TTS_PREWARM] Triggered non-blocking Cartesia TTS connection pool prewarm")
            except Exception as e:
                logger.warning(f"[TTS_PREWARM] Failed to prewarm Cartesia TTS: {e}")
        elif hasattr(agent.tts, "_current_connection"):
            try:
                asyncio.create_task(agent.tts._current_connection())
                logger.info("[TTS_PREWARM] Triggered non-blocking ElevenLabs TTS connection prewarm")
            except Exception as e:
                logger.warning(f"[TTS_PREWARM] Failed to prewarm ElevenLabs TTS: {e}")

    # Initialize recording state
    agent.egress_id = None
    agent.recording_filename = None
    agent._recording_task = None  # Track recording startup task for synchronization

    # Subscribe to speech/message events to build transcripts and publish live UI updates
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        if event.is_final and event.transcript.strip():
            # Process caller name capture state machine
            before_state = agent.name_state.state
            result = agent.name_state.process_utterance(event.transcript)
            logger.info(
                f"[NAME_STATE] before={before_state} input=\"{event.transcript}\" "
                f"action={result.get('action')} captured_name={agent.name_state.captured_name} "
                f"retry_count={agent.name_state.spelling_retries}"
            )
            if result.get("name"):
                agent.captured_caller_name = result["name"]

            # Format rich STT diagnostics if available
            conf = getattr(event, 'confidence', None)
            words = getattr(event, 'words', None)
            words_info = ""
            if words and isinstance(words, list):
                words_info = f" words={[{'w': getattr(w, 'word', str(w)), 'c': getattr(w, 'confidence', None)} for w in words[:5]]}"

            logger.info(
                f"[STT_DEBUG] final_text=\"{event.transcript}\" is_final={event.is_final} "
                f"confidence={conf} language={getattr(event, 'language', None)} "
                f"speaker_id={getattr(event, 'speaker_id', None)}{words_info}"
            )
            logger.info(f"User speech transcribed: {event.transcript}")
            if agent.settings.enable_transcripts and agent.transcript_session_id:
                transcript_service.add_transcript_entry(
                    agent.transcript_session_id,
                    speaker="customer",
                    text=event.transcript
                )
            try:
                if ctx.room and ctx.room.local_participant:
                    asyncio.create_task(ctx.room.local_participant.publish_data(
                        json.dumps({"type": "transcription", "speaker": "user", "text": event.transcript.strip()}).encode("utf-8"),
                        topic="transcription"
                    ))
            except Exception as pub_err:
                logger.warning(f"Failed to publish user transcript data packet: {pub_err}")

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
                try:
                    if ctx.room and ctx.room.local_participant:
                        asyncio.create_task(ctx.room.local_participant.publish_data(
                            json.dumps({"type": "transcription", "speaker": "agent", "text": content_text.strip()}).encode("utf-8"),
                            topic="transcription"
                        ))
                except Exception as pub_err:
                    logger.warning(f"Failed to publish agent transcript data packet: {pub_err}")

    logger.info("Starting session")
    try:

        
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

        logger.info(f"[CALL_TIMING] job={job_id} stage=T11_AgentSession_starting total_elapsed={time.perf_counter() - t_start:.3f}s")
        await session.start(room=ctx.room, agent=agent)
        logger.info(f"[CALL_TIMING] job={job_id} stage=T11_AgentSession_started total_elapsed={time.perf_counter() - t_start:.3f}s")
        logger.info("SESSION STARTED")
        await shutdown_event.wait()
    finally:
        shutdown_event.set()
        await cleanup_on_disconnect(session, session_manager, agent=agent)
        logger.info("Entrypoint exiting")


async def cleanup_on_disconnect(session, session_manager, agent=None):
    """Async cleanup function called when participant disconnects."""
    try:
        if session:
            await session.aclose()
    except Exception as e:
        logger.warning(f"Error closing agent session: {e}")

    # Fallback to ensure agent.on_exit executed if not invoked by session
    if agent and hasattr(agent, 'on_exit'):
        try:
            await agent.on_exit()
        except Exception as e:
            logger.warning(f"Error executing agent on_exit fallback: {e}")
        
    try:
        if session_manager:
            session_manager.clear_all_sessions()
    except Exception as e:
        logger.warning(f"Redis cleanup failed (may not be running): {e}")
    
    logger.info("SESSION CLEANED")


def validate_worker_dependencies():
    """Validate all external dependencies synchronously before launching LiveKit worker."""
    settings = get_settings()
    logger.info("[Startup] Validating worker dependencies...")

    # 1. Validate BACKEND_URL format
    backend_url = settings.backend_url
    parsed = urlparse(backend_url)
    if not parsed.scheme or not parsed.netloc:
        logger.error(f"[Startup] Invalid BACKEND_URL: {backend_url}")
        sys.exit(1)

    # 2. Verify backend is reachable and database is healthy (synchronously via httpx.Client)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{backend_url}/health")
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

    # 3. Verify LiveKit connection (HTTP reachability probe)
    try:
        lk_http_url = settings.livekit_url.replace("wss://", "https://").replace("ws://", "http://")
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(lk_http_url)
            logger.info(f"[Startup] LiveKit server reachable (HTTP {resp.status_code})")
    except Exception as e:
        logger.warning(f"[Startup] LiveKit reachability probe: {e}")

    # 4. Warm the shared Redis client for SessionManager (synchronous)
    from session_manager import warm_redis
    try:
        if warm_redis() is not None:
            logger.info("[Startup] Redis is reachable (shared SessionManager client warmed)")
        else:
            logger.warning(f"[Startup] Redis is not reachable at {settings.redis_url}. Continuing with in-memory fallback.")
    except Exception as e:
        logger.warning(f"[Startup] Redis is not reachable at {settings.redis_url}: {e}. Continuing with in-memory fallback.")

    logger.info("[Startup] All worker dependencies validated successfully")


if __name__ == "__main__":
    validate_worker_dependencies()
    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            agent_name=settings.livekit_agent_name,
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
