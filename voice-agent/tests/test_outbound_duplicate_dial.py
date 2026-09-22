import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

import asyncio
from fastapi import HTTPException

from api.modules.telephony_configs.routes import initiate_call, _outbound_dial_guard
from api.modules.telephony_configs.schemas import InitiateCallRequest
from api.utils.encryption import token_encryptor


class TestOutboundDuplicateDial(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await _outbound_dial_guard.clear()
        self.encrypted_auth_token = token_encryptor.encrypt("valid_twilio_auth_token_32chars!")
        self.mock_config = {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Production Twilio",
            "provider": "twilio",
            "is_default_outbound": True,
            "raw_credentials": {
                "account_sid": "AC_test_account_sid_1234567890",
                "auth_token": self.encrypted_auth_token,
                "sip_domain": "42v-test.pstn.twilio.com",
                "sip_username": "lk_user_test",
                "sip_password": token_encryptor.encrypt("sip_pass_123")
            }
        }
        self.mock_phone = {
            "id": "22222222-2222-2222-2222-222222222222",
            "telephony_configuration_id": "11111111-1111-1111-1111-111111111111",
            "address": "+6498736772",
            "label": "Test Line",
            "is_active": True,
            "is_default_caller_id": True,
            "lk_sip_trunk_id": "ST_inbound_permanent_123",
            "lk_outbound_sip_trunk_id": "ST_outbound_stale_999",
            "lk_sip_dispatch_rule_id": "SDR_inbound_permanent_123"
        }
        self.user_a = {"client_id": "user_a_client_id", "role": "USER"}
        self.req = InitiateCallRequest(
            phone_number="+61400111222",
            telephony_configuration_id=self.mock_config["id"]
        )

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    async def test_concurrent_duplicate_dial_suppressed(
        self, mock_db_query, mock_db_service
    ):
        """P1-9 - A duplicate concurrent dial for the same destination is suppressed (no double call)."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_dispatch(**kwargs):
            started.set()
            await release.wait()
            return "dialed once"

        with patch("api.modules.telephony_configs.routes._dispatch_outbound_call") as mock_dispatch:
            mock_dispatch.side_effect = slow_dispatch

            # First dial enters the guard (holds it while "dialing")
            first = asyncio.create_task(initiate_call(self.req, current_user=self.user_a))
            await asyncio.wait_for(started.wait(), timeout=1.0)

            # Duplicate concurrent request must be suppressed, not dialed again
            second = asyncio.create_task(initiate_call(self.req, current_user=self.user_a))
            res2 = await asyncio.wait_for(second, timeout=1.0)
            self.assertEqual(res2.status_code, 200)
            body2 = json.loads(res2.body)
            self.assertIn("already in progress", body2.get("message", ""))
            self.assertEqual(mock_dispatch.call_count, 1)

            # Let the first dial finish; the guard is released afterwards
            release.set()
            res1 = await asyncio.wait_for(first, timeout=1.0)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(mock_dispatch.call_count, 1)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_completed_dial_allows_next_request(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """P1-9 - after a dial completes, a later request for the same number dials again (guard released)."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_123"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            mock_settings.return_value = settings_obj

            res1 = await initiate_call(self.req, current_user=self.user_a)
            res2 = await initiate_call(self.req, current_user=self.user_a)

            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(mock_http_client.post.call_count, 2)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_different_destinations_not_suppressed(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """P1-9 - concurrent calls to different destinations are both dialed."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_123"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            mock_settings.return_value = settings_obj

            req_b = InitiateCallRequest(
                phone_number="+15551234567",
                telephony_configuration_id=self.mock_config["id"]
            )

            res_a, res_b = await asyncio.gather(
                initiate_call(self.req, current_user=self.user_a),
                initiate_call(req_b, current_user=self.user_a),
            )

            self.assertEqual(res_a.status_code, 200)
            self.assertEqual(res_b.status_code, 200)
            self.assertEqual(mock_http_client.post.call_count, 2)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_agent_dispatch_failure_aborts_before_dialing(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """P1-10 - if the agent cannot be dispatched, the call is NOT placed (LiveKit or Twilio)."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[dict(self.mock_phone)])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        config_with_trunk = dict(self.mock_config)
        config_with_trunk["raw_credentials"] = dict(self.mock_config["raw_credentials"])
        config_with_trunk["raw_credentials"]["twilio_sip_trunk_id"] = "ST_outbound_999"
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=config_with_trunk)

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = "wss://ws.42voice.com"
            settings_obj.livekit_api_key = "key"
            settings_obj.livekit_api_secret = "secret"
            settings_obj.livekit_agent_name = "inbound-agent"
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            mock_settings.return_value = settings_obj

            with patch("livekit.api.LiveKitAPI") as mock_lk_cls:
                mock_lk = MagicMock()
                mock_lk_cls.return_value = mock_lk
                mock_lk.agent_dispatch.create_dispatch = AsyncMock(
                    side_effect=Exception("worker unavailable: dispatch rejected")
                )
                mock_lk.sip.create_sip_participant = AsyncMock(
                    return_value=MagicMock(participant_id="PA_never")
                )
                mock_lk.aclose = AsyncMock()

                with self.assertRaises(HTTPException) as ctx:
                    await initiate_call(self.req, current_user=self.user_a)

                self.assertEqual(ctx.exception.status_code, 502)
                self.assertIn("was NOT placed", ctx.exception.detail)
                # The phone was never dialed through either provider
                mock_lk.sip.create_sip_participant.assert_not_called()
                mock_http_client.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()