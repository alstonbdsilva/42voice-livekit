import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
import json

from api.modules.telephony_configs.routes import initiate_call
from api.modules.telephony_configs.schemas import InitiateCallRequest
from api.utils.encryption import token_encryptor


class TestOutboundInitiateCall(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.plain_auth_token = "valid_twilio_auth_token_32chars!"
        self.encrypted_auth_token = token_encryptor.encrypt(self.plain_auth_token)
        self.account_sid = "AC_test_account_sid_1234567890"

        self.mock_config = {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Production Twilio",
            "provider": "twilio",
            "is_default_outbound": True,
            "raw_credentials": {
                "account_sid": self.account_sid,
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
        self.user_b = {"client_id": "user_b_client_id", "role": "USER"}

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_encrypted_token_decrypted_before_twilio_rest(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """Test 1 - DB encrypted auth_token is properly decrypted before being sent to Twilio REST API."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        # Mock httpx response
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_123"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        # Mock settings to have no LiveKit connection so it proceeds directly to Twilio REST fallback
        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.twilio_sip_domain = "42v-test.pstn.twilio.com"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+61400111222",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            res = await initiate_call(req, current_user=self.user_a)

            self.assertEqual(res.status_code, 200)
            mock_http_client.post.assert_called_once()
            call_kwargs = mock_http_client.post.call_args[1]

            # Verify HTTP Basic Auth received decrypted token, NOT encrypted ciphertext
            auth_tuple = call_kwargs["auth"]
            self.assertEqual(auth_tuple[0], self.account_sid)
            self.assertEqual(auth_tuple[1], self.plain_auth_token)
            self.assertNotEqual(auth_tuple[1], self.encrypted_auth_token)

    @patch("api.modules.telephony_configs.routes.db_service")
    async def test_no_env_settings_fallback_when_config_missing(
        self, mock_db_service
    ):
        """Test 2 - If DB config has no credentials, code raises 400 and does NOT fallback to env settings."""
        empty_config = {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Empty Twilio",
            "provider": "twilio",
            "raw_credentials": {}  # Missing account_sid and auth_token
        }
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=empty_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.twilio_account_sid = "AC_env_fallback_leak"
            settings_obj.twilio_auth_token = "env_token_leak"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+61400111222",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            with self.assertRaises(HTTPException) as ctx:
                await initiate_call(req, current_user=self.user_a)

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("missing Account SID or Auth Token", ctx.exception.detail)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.livekit_sip_service")
    async def test_outbound_repair_preserves_inbound_trunk_and_dispatch_rule(
        self, mock_lk_service, mock_db_query, mock_db_service
    ):
        """Test 3 - Outbound repair updates only lk_outbound_sip_trunk_id and preserves inbound trunk & rule."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[dict(self.mock_phone)])
        mock_db_query.return_value = []

        # Mock LiveKit SIP client dispatch
        mock_lk_service.reconcile_outbound_trunk = AsyncMock(return_value=("ST_outbound_repaired_888", None))

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = "wss://ws.42voice.com"
            settings_obj.livekit_api_key = "key"
            settings_obj.livekit_api_secret = "secret"
            settings_obj.livekit_agent_name = "inbound-agent"
            mock_settings.return_value = settings_obj

            with patch("livekit.api.LiveKitAPI") as mock_lk_cls:
                mock_lk = MagicMock()
                mock_lk_cls.return_value = mock_lk
                mock_lk.agent_dispatch.create_dispatch = AsyncMock()
                mock_lk.aclose = AsyncMock()

                # First call fails with 404 trunk not found
                # Second call (retry) succeeds
                res_mock = MagicMock(participant_id="PA_repaired_participant")
                mock_lk.sip.create_sip_participant = AsyncMock(
                    side_effect=[Exception("requested sip trunk does not exist status=404"), res_mock]
                )

                req = InitiateCallRequest(
                    phone_number="+61400111222",
                    telephony_configuration_id="11111111-1111-1111-1111-111111111111"
                )

                res = await initiate_call(req, current_user=self.user_a)

                self.assertEqual(res.status_code, 200)
                body = json.loads(res.body)
                self.assertIn("PA_repaired_participant", body.get("message", ""))

                # Verify reconcile_outbound_trunk was called (which only manages outbound trunk)
                mock_lk_service.reconcile_outbound_trunk.assert_called_once()
                # Verify inbound trunk / dispatch rule provisioning methods were NEVER called
                mock_lk_service.provision_inbound_trunk.assert_not_called()
                mock_lk_service.update_inbound_trunk.assert_not_called()
                mock_lk_service.update_dispatch_rule.assert_not_called()

                # Verify database update ONLY touched lk_outbound_sip_trunk_id
                db_updates = [call[0][0] for call in mock_db_query.call_args_list if "UPDATE" in str(call[0][0])]
                self.assertTrue(any("lk_outbound_sip_trunk_id" in q for q in db_updates))
                self.assertFalse(any("lk_sip_trunk_id" in q for q in db_updates))
                self.assertFalse(any("lk_sip_dispatch_rule_id" in q for q in db_updates))

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.livekit_sip_service")
    async def test_only_one_retry_on_trunk_not_found(
        self, mock_lk_service, mock_db_query, mock_db_service
    ):
        """Test 4 - If LiveKit dispatch fails with trunk-not-found, exactly ONE retry occurs."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[dict(self.mock_phone)])
        mock_db_query.return_value = []

        mock_lk_service.reconcile_outbound_trunk = AsyncMock(return_value=("ST_outbound_repaired_888", None))

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = "wss://ws.42voice.com"
            settings_obj.livekit_api_key = "key"
            settings_obj.livekit_api_secret = "secret"
            settings_obj.livekit_agent_name = "inbound-agent"
            settings_obj.twilio_sip_domain = "42v-test.pstn.twilio.com"
            mock_settings.return_value = settings_obj

            with patch("livekit.api.LiveKitAPI") as mock_lk_cls:
                mock_lk = MagicMock()
                mock_lk_cls.return_value = mock_lk
                mock_lk.agent_dispatch.create_dispatch = AsyncMock()
                mock_lk.aclose = AsyncMock()

                # Both initial attempt and retry fail
                mock_lk.sip.create_sip_participant = AsyncMock(
                    side_effect=[
                        Exception("requested sip trunk does not exist status=404"),
                        Exception("requested sip trunk does not exist status=404")
                    ]
                )

                # Twilio fallback succeeds
                with patch("api.modules.telephony_configs.routes.httpx.AsyncClient") as mock_httpx_cls:
                    mock_http_client = AsyncMock()
                    mock_response = MagicMock()
                    mock_response.status_code = 201
                    mock_response.headers = {"content-type": "application/json"}
                    mock_response.json.return_value = {"sid": "CA_twilio_fallback_call"}
                    mock_http_client.post.return_value = mock_response
                    mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

                    req = InitiateCallRequest(
                        phone_number="+61400111222",
                        telephony_configuration_id="11111111-1111-1111-1111-111111111111"
                    )

                    res = await initiate_call(req, current_user=self.user_a)

                    # Exactly 2 LiveKit SIP attempts (1 initial + 1 retry)
                    self.assertEqual(mock_lk.sip.create_sip_participant.call_count, 2)
                    # Exactly 1 reconciliation call
                    mock_lk_service.reconcile_outbound_trunk.assert_called_once()
                    # Twilio fallback executed
                    mock_http_client.post.assert_called_once()
                    self.assertEqual(res.status_code, 200)
                    body = json.loads(res.body)
                    self.assertIn("CA_twilio_fallback_call", body.get("message", ""))

    @patch("api.modules.telephony_configs.routes.db_service")
    async def test_multi_user_configs_isolation(
        self, mock_db_service
    ):
        """Test 5 - User B attempting to initiate call with User A's config returns 404."""
        # get_telephony_configuration scoped to User B returns None
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=None)

        req = InitiateCallRequest(
            phone_number="+61400111222",
            telephony_configuration_id="11111111-1111-1111-1111-111111111111"
        )

        with self.assertRaises(HTTPException) as ctx:
            await initiate_call(req, current_user=self.user_b)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Selected telephony configuration not found", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
