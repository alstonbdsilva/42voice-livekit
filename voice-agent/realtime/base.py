"""
Realtime runtime abstraction protocol.
Isolates the generic workflow engine from concrete transport and agent framework APIs.
"""

from typing import Protocol, Sequence, Any, Optional, runtime_checkable


@runtime_checkable
class RealtimeRuntime(Protocol):
    """
    Minimal async protocol for realtime communication and runtime manipulation
    required by the workflow execution engine.
    """

    async def update_instructions(self, instructions: str) -> None:
        """Update active agent system instructions/prompt in-place."""
        ...

    async def update_tools(self, tools: Sequence[Any]) -> None:
        """Update active agent available tools in-place."""
        ...

    async def say(self, text: str, *, allow_interruptions: bool = True) -> Any:
        """Speak an utterance to the participant."""
        ...

    async def wait_for_playout(self, speech_handle: Any) -> None:
        """Wait for an in-flight speech utterance to complete playing out."""
        ...
