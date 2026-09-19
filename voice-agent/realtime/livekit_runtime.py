"""
LiveKit runtime adapter implementing RealtimeRuntime.
Delegates in-call runtime mutations and utterances to the single active VoiceAgent and AgentSession.

IMPORTANT:
This adapter does NOT own:
- Recording / Egress lifecycle
- Transcript capture / persistence
- CALL_PERSIST backend registration
- VoiceAgent.on_exit() cleanup
- Disconnection / room teardown
"""

import logging
from typing import Any, Sequence, Optional
from realtime.base import RealtimeRuntime

logger = logging.getLogger("voice-agent.realtime.livekit")


class LiveKitRuntimeAdapter(RealtimeRuntime):
    """
    Thin adapter conforming the LiveKit Agents SDK (VoiceAgent + AgentSession + Room)
    to the generic RealtimeRuntime protocol.
    """

    def __init__(
        self,
        *,
        agent: Any,
        session: Any = None,
        room: Any = None,
    ):
        self.agent = agent
        self.session = session
        self.room = room

    async def update_instructions(self, instructions: str) -> None:
        """Update instructions on the single active VoiceAgent."""
        if hasattr(self.agent, "update_instructions"):
            await self.agent.update_instructions(instructions)
        else:
            logger.warning("[LIVEKIT_RUNTIME] Active agent does not support update_instructions")

    async def update_tools(self, tools: Sequence[Any]) -> None:
        """Update tools on the single active VoiceAgent."""
        if hasattr(self.agent, "update_tools"):
            await self.agent.update_tools(tools)
        else:
            logger.warning("[LIVEKIT_RUNTIME] Active agent does not support update_tools")

    async def say(self, text: str, *, allow_interruptions: bool = True) -> Any:
        """Utter speech through the active session or agent."""
        if self.session and hasattr(self.session, "say"):
            return await self.session.say(text, allow_interruptions=allow_interruptions)
        elif hasattr(self.agent, "say"):
            return await self.agent.say(text, allow_interruptions=allow_interruptions)
        logger.warning("[LIVEKIT_RUNTIME] Neither session nor agent supports say()")
        return None

    async def wait_for_playout(self, speech_handle: Any) -> None:
        """Wait for an active speech handle to finish playing out."""
        if speech_handle and hasattr(speech_handle, "wait_for_playout"):
            await speech_handle.wait_for_playout()
