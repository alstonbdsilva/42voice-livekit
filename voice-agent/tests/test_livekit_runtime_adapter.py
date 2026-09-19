"""
Unit tests for RealtimeRuntime protocol and LiveKitRuntimeAdapter.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from realtime.base import RealtimeRuntime
from realtime.livekit_runtime import LiveKitRuntimeAdapter


class TestLiveKitRuntimeAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_01_protocol_conformance(self):
        """Verify LiveKitRuntimeAdapter implements the RealtimeRuntime protocol."""
        mock_agent = MagicMock()
        mock_session = MagicMock()
        mock_room = MagicMock()
        adapter = LiveKitRuntimeAdapter(agent=mock_agent, session=mock_session, room=mock_room)
        self.assertIsInstance(adapter, RealtimeRuntime)

    async def test_02_update_instructions_delegation(self):
        """Verify update_instructions delegates directly to active agent."""
        mock_agent = MagicMock()
        mock_agent.update_instructions = AsyncMock()
        adapter = LiveKitRuntimeAdapter(agent=mock_agent)

        await adapter.update_instructions("New system instructions")
        mock_agent.update_instructions.assert_awaited_once_with("New system instructions")

    async def test_03_update_tools_delegation(self):
        """Verify update_tools delegates directly to active agent."""
        mock_agent = MagicMock()
        mock_agent.update_tools = AsyncMock()
        adapter = LiveKitRuntimeAdapter(agent=mock_agent)

        tools = ["tool_a", "tool_b"]
        await adapter.update_tools(tools)
        mock_agent.update_tools.assert_awaited_once_with(tools)

    async def test_04_say_delegation(self):
        """Verify say delegates to active session."""
        mock_session = MagicMock()
        mock_session.say = AsyncMock(return_value="speech_handle_123")
        adapter = LiveKitRuntimeAdapter(agent=MagicMock(), session=mock_session)

        handle = await adapter.say("Hello caller!", allow_interruptions=False)
        self.assertEqual(handle, "speech_handle_123")
        mock_session.say.assert_awaited_once_with("Hello caller!", allow_interruptions=False)

    async def test_05_wait_for_playout_delegation(self):
        """Verify wait_for_playout awaits speech handle playout."""
        mock_handle = MagicMock()
        mock_handle.wait_for_playout = AsyncMock()
        adapter = LiveKitRuntimeAdapter(agent=MagicMock())

        await adapter.wait_for_playout(mock_handle)
        mock_handle.wait_for_playout.assert_awaited_once()

    async def test_06_adapter_does_not_own_cleanup_or_lifecycle(self):
        """Verify adapter does not expose or trigger on_exit, CALL_PERSIST, recording, or disconnect."""
        adapter = LiveKitRuntimeAdapter(agent=MagicMock(), session=MagicMock(), room=MagicMock())
        self.assertFalse(hasattr(adapter, "on_exit"))
        self.assertFalse(hasattr(adapter, "stop_recording"))
        self.assertFalse(hasattr(adapter, "register_call"))
        self.assertFalse(hasattr(adapter, "CALL_PERSIST"))


if __name__ == "__main__":
    unittest.main()
