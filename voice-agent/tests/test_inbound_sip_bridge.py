import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from api.modules.telephony_configs import inbound_sip_bridge


def _room(name):
    return SimpleNamespace(name=name)


class TestDiscoverInboundSipRoom(unittest.IsolatedAsyncioTestCase):

    def _mock_lk(self, list_rooms_return, participants_return=None):
        mock_lk = MagicMock()
        mock_lk.room.list_rooms = AsyncMock(return_value=list_rooms_return)
        if participants_return is None:
            participants_return = SimpleNamespace(participants=[])
        mock_lk.room.list_participants = AsyncMock(return_value=participants_return)
        return mock_lk

    async def test_discover_returns_inbound_sip_room_for_caller(self):
        mock_lk = self._mock_lk(
            SimpleNamespace(rooms=[
                _room("call-abc123"),
                _room("sip-_+6498736772_k3x9"),
            ])
        )
        room = await inbound_sip_bridge.discover_inbound_sip_room(
            mock_lk, "+6498736772", max_attempts=3, poll_interval=0.01
        )
        self.assertEqual(room, "sip-_+6498736772_k3x9")

    async def test_discover_confirms_via_sip_participant_attributes(self):
        mock_lk = MagicMock()
        mock_lk.room.list_rooms = AsyncMock(
            return_value=SimpleNamespace(rooms=[
                _room("sip-_+6498736772_confirmed"),
                _room("sip-_+6498736772_other-call"),
            ])
        )
        confirmed = SimpleNamespace(identity="sip_+6498736772", attributes={"sip.trunkPhoneNumber": "+6498736772"})
        other = SimpleNamespace(identity="sip_+64211234567", attributes={"sip.trunkPhoneNumber": "+64211234567"})

        async def participants_for(room):
            if room == "sip-_+6498736772_confirmed":
                return SimpleNamespace(participants=[confirmed])
            return SimpleNamespace(participants=[other])

        mock_lk.room.list_participants = AsyncMock(side_effect=participants_for)
        room = await inbound_sip_bridge.discover_inbound_sip_room(
            mock_lk, "+6498736772", max_attempts=3, poll_interval=0.01
        )
        self.assertEqual(room, "sip-_+6498736772_confirmed")

    async def test_discover_retries_until_room_appears(self):
        mock_lk = MagicMock()
        mock_lk.room.list_rooms = AsyncMock(
            side_effect=[
                SimpleNamespace(rooms=[]),
                SimpleNamespace(rooms=[]),
                SimpleNamespace(rooms=[_room("sip-_+6498736772_abc")]),
            ]
        )
        mock_lk.room.list_participants = AsyncMock(return_value=SimpleNamespace(participants=[]))
        room = await inbound_sip_bridge.discover_inbound_sip_room(
            mock_lk, "+6498736772", max_attempts=5, poll_interval=0.01
        )
        self.assertEqual(room, "sip-_+6498736772_abc")
        self.assertEqual(mock_lk.room.list_rooms.await_count, 3)

    async def test_discover_ignores_rooms_for_other_callers(self):
        mock_lk = self._mock_lk(
            SimpleNamespace(rooms=[
                _room("sip-_+64211234567_zzz"),
                _room("sip-_+64987369999_yyy"),
            ])
        )
        room = await inbound_sip_bridge.discover_inbound_sip_room(
            mock_lk, "+6498736772", max_attempts=3, poll_interval=0.01
        )
        self.assertIsNone(room)
        self.assertEqual(mock_lk.room.list_rooms.await_count, 3)

    async def test_discover_returns_none_when_no_room_ever_appears(self):
        mock_lk = self._mock_lk(SimpleNamespace(rooms=[_room("call-abc123")]))
        room = await inbound_sip_bridge.discover_inbound_sip_room(
            mock_lk, "+6498736772", max_attempts=2, poll_interval=0.01
        )
        self.assertIsNone(room)
        self.assertEqual(mock_lk.room.list_rooms.await_count, 2)


class TestEnsureAgentDispatchForRoom(unittest.IsolatedAsyncioTestCase):

    ROOM = "sip-_+6498736772_abc123"

    def _mock_lk(self, existing_dispatches=(), participants=()):
        mock_lk = MagicMock()
        mock_lk.agent_dispatch.list_dispatch = AsyncMock(return_value=list(existing_dispatches))
        mock_lk.room.list_participants = AsyncMock(
            return_value=SimpleNamespace(participants=list(participants))
        )
        mock_lk.agent_dispatch.create_dispatch = AsyncMock(
            return_value=SimpleNamespace(id="DISPATCH_NEW_001")
        )
        return mock_lk

    async def test_creates_dispatch_into_actual_sip_room_with_metadata(self):
        mock_lk = self._mock_lk()
        dispatch_id = await inbound_sip_bridge.ensure_agent_dispatch_for_room(
            mock_lk, self.ROOM, "inbound-agent", '{"agent_id": "ag-1"}'
        )
        self.assertEqual(dispatch_id, "DISPATCH_NEW_001")
        mock_lk.agent_dispatch.create_dispatch.assert_awaited_once()
        request = mock_lk.agent_dispatch.create_dispatch.call_args[0][0]
        self.assertEqual(request.room, self.ROOM)
        self.assertEqual(request.agent_name, "inbound-agent")
        self.assertEqual(request.metadata, '{"agent_id": "ag-1"}')

    async def test_skips_duplicate_when_dispatch_rule_already_dispatched(self):
        existing = SimpleNamespace(
            id="DISPATCH_RULE_1",
            agent_name="inbound-agent",
            state=SimpleNamespace(deleted_at=0, jobs=[]),
        )
        mock_lk = self._mock_lk(existing_dispatches=[existing])
        dispatch_id = await inbound_sip_bridge.ensure_agent_dispatch_for_room(
            mock_lk, self.ROOM, "inbound-agent", ""
        )
        self.assertEqual(dispatch_id, "DISPATCH_RULE_1")
        mock_lk.agent_dispatch.create_dispatch.assert_not_awaited()

    async def test_wrong_agent_dispatch_falls_back_to_create_correct_dispatch(self):
        wrong_agent = SimpleNamespace(
            id="DISPATCH_WRONG_AGT",
            agent_name="some-other-agent",
            state=SimpleNamespace(deleted_at=0, jobs=[]),
        )
        mock_lk = self._mock_lk(existing_dispatches=[wrong_agent])
        dispatch_id = await inbound_sip_bridge.ensure_agent_dispatch_for_room(
            mock_lk, self.ROOM, "inbound-agent", ""
        )
        self.assertEqual(dispatch_id, "DISPATCH_NEW_001")
        mock_lk.agent_dispatch.create_dispatch.assert_awaited_once()
        request = mock_lk.agent_dispatch.create_dispatch.call_args[0][0]
        self.assertEqual(request.agent_name, "inbound-agent")

    async def test_skips_when_agent_already_present_in_room(self):
        agent = SimpleNamespace(identity="inbound-agent", attributes={})
        mock_lk = self._mock_lk(participants=[agent])
        dispatch_id = await inbound_sip_bridge.ensure_agent_dispatch_for_room(
            mock_lk, self.ROOM, "inbound-agent", ""
        )
        self.assertIsNone(dispatch_id)
        mock_lk.agent_dispatch.create_dispatch.assert_not_awaited()

    async def test_creates_dispatch_when_existing_one_was_deleted(self):
        deleted = SimpleNamespace(
            id="DISPATCH_OLD",
            agent_name="inbound-agent",
            state=SimpleNamespace(deleted_at=12345678, jobs=[]),
        )
        mock_lk = self._mock_lk(existing_dispatches=[deleted])
        dispatch_id = await inbound_sip_bridge.ensure_agent_dispatch_for_room(
            mock_lk, self.ROOM, "inbound-agent", ""
        )
        self.assertEqual(dispatch_id, "DISPATCH_NEW_001")
        mock_lk.agent_dispatch.create_dispatch.assert_awaited_once()


class TestEnsureInboundSipAgentDispatch(unittest.IsolatedAsyncioTestCase):

    async def test_end_to_end_dispatch_targets_discovered_sip_room(self):
        with patch("livekit.api.LiveKitAPI") as mock_ctor, patch(
            "api.modules.telephony_configs.inbound_sip_bridge.get_settings"
        ) as mock_settings:
            mock_lk = MagicMock()
            mock_ctor.return_value = mock_lk
            mock_lk.aclose = AsyncMock()
            mock_lk.room.list_rooms = AsyncMock(
                return_value=SimpleNamespace(rooms=[_room("sip-_+6498736772_abc")])
            )
            mock_lk.room.list_participants = AsyncMock(
                return_value=SimpleNamespace(
                    participants=[
                        SimpleNamespace(identity="sip_+6498736772", attributes={"sip.trunkPhoneNumber": "+6498736772"})
                    ]
                )
            )
            mock_lk.agent_dispatch.list_dispatch = AsyncMock(return_value=[])
            mock_lk.agent_dispatch.create_dispatch = AsyncMock(
                return_value=SimpleNamespace(id="DISPATCH_FALLBACK_1")
            )

            settings_obj = MagicMock()
            settings_obj.livekit_url = "wss://ws.42voice.com"
            settings_obj.livekit_api_key = "key"
            settings_obj.livekit_api_secret = "secret"
            settings_obj.livekit_agent_name = "inbound-agent"
            mock_settings.return_value = settings_obj

            dispatch_id = await inbound_sip_bridge.ensure_inbound_sip_agent_dispatch(
                caller_id="+6498736772",
                metadata='{"agent_id": "ag-1", "dest_number": "+61400111222"}',
            )

            self.assertEqual(dispatch_id, "DISPATCH_FALLBACK_1")
            request = mock_lk.agent_dispatch.create_dispatch.call_args[0][0]
            self.assertEqual(request.room, "sip-_+6498736772_abc")
            self.assertEqual(request.agent_name, "inbound-agent")
            self.assertIn("ag-1", request.metadata)
            mock_lk.aclose.assert_awaited_once()

    async def test_no_dispatch_when_rule_dispatched_first(self):
        with patch("livekit.api.LiveKitAPI") as mock_ctor, patch(
            "api.modules.telephony_configs.inbound_sip_bridge.get_settings"
        ) as mock_settings:
            mock_lk = MagicMock()
            mock_ctor.return_value = mock_lk
            mock_lk.aclose = AsyncMock()
            mock_lk.room.list_rooms = AsyncMock(
                return_value=SimpleNamespace(rooms=[_room("sip-_+6498736772_abc")])
            )
            mock_lk.room.list_participants = AsyncMock(
                return_value=SimpleNamespace(participants=[])
            )
            mock_lk.agent_dispatch.list_dispatch = AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="DISPATCH_FROM_RULE",
                        agent_name="inbound-agent",
                        state=SimpleNamespace(deleted_at=0, jobs=[]),
                    )
                ]
            )
            mock_lk.agent_dispatch.create_dispatch = AsyncMock(
                return_value=SimpleNamespace(id="SHOULD_NOT_HAPPEN")
            )

            settings_obj = MagicMock()
            settings_obj.livekit_url = "wss://ws.42voice.com"
            settings_obj.livekit_api_key = "key"
            settings_obj.livekit_api_secret = "secret"
            settings_obj.livekit_agent_name = "inbound-agent"
            mock_settings.return_value = settings_obj

            dispatch_id = await inbound_sip_bridge.ensure_inbound_sip_agent_dispatch(
                caller_id="+6498736772", metadata=""
            )

            self.assertEqual(dispatch_id, "DISPATCH_FROM_RULE")
            mock_lk.agent_dispatch.create_dispatch.assert_not_awaited()

    async def test_skips_when_livekit_not_configured(self):
        with patch(
            "api.modules.telephony_configs.inbound_sip_bridge.get_settings"
        ) as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_agent_name = "inbound-agent"
            mock_settings.return_value = settings_obj

            result = await inbound_sip_bridge.ensure_inbound_sip_agent_dispatch(
                caller_id="+6498736772", metadata=""
            )
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()