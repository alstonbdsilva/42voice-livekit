import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
import json
import asyncio

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
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
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

            # Verify TwiML bridges to LiveKit SIP endpoint, NOT Twilio PSTN termination domain
            twiml = call_kwargs["data"]["Twiml"]
            self.assertIn("<Dial><Sip>sip:+6498736772@187.52.120.31:5060;transport=tcp</Sip></Dial>", twiml)
            self.assertNotIn("42v-test.pstn.twilio.com", twiml)
            self.assertNotIn("42v-01dde021.pstn.twilio.com", twiml)

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
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
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

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_twiml_generation_bridges_to_livekit_sip_endpoint(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """Test 6 - TwiML generation bridges call to LiveKit SIP endpoint with caller_id and X-Agent-Id."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = [{"name": "E2E Voice Test Agent"}]

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_livekit_bridge"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+919381408134",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111",
                agent_id="86818021-5dcf-4ee5-b4fd-3b04e16f17c8"
            )

            res = await initiate_call(req, current_user=self.user_a)

            self.assertEqual(res.status_code, 200)
            mock_http_client.post.assert_called_once()
            call_kwargs = mock_http_client.post.call_args[1]

            data = call_kwargs["data"]
            self.assertEqual(data["To"], "+919381408134")
            self.assertEqual(data["From"], "+6498736772")

            expected_sip = "sip:+6498736772@187.52.120.31:5060;transport=tcp?X-Agent-Id=86818021-5dcf-4ee5-b4fd-3b04e16f17c8"
            expected_twiml = f"<Response><Dial><Sip>{expected_sip}</Sip></Dial></Response>"
            self.assertEqual(data["Twiml"], expected_twiml)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_twiml_generation_never_uses_twilio_pstn_domain(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """Test 7 - TwiML generation never uses Twilio PSTN termination domain as destination."""
        config_with_pstn = dict(self.mock_config)
        config_with_pstn["raw_credentials"] = dict(self.mock_config["raw_credentials"])
        config_with_pstn["raw_credentials"]["sip_domain"] = "42v-01dde021.pstn.twilio.com"

        mock_db_service.get_telephony_configuration = AsyncMock(return_value=config_with_pstn)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_check"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            settings_obj.twilio_sip_domain = "42voice.pstn.sydney.twilio.com"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+919381408134",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            res = await initiate_call(req, current_user=self.user_a)

            self.assertEqual(res.status_code, 200)
            call_kwargs = mock_http_client.post.call_args[1]
            twiml = call_kwargs["data"]["Twiml"]

            # Must NOT contain Twilio termination domains
            self.assertNotIn("42v-01dde021.pstn.twilio.com", twiml)
            self.assertNotIn("42voice.pstn.sydney.twilio.com", twiml)
            self.assertNotIn("sip:+919381408134@42v", twiml)
            # Must bridge to LiveKit SIP endpoint
            self.assertIn("<Dial><Sip>sip:+6498736772@187.52.120.31:5060;transport=tcp</Sip></Dial>", twiml)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_outbound_twilio_call_never_registers_status_callback_webhook(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """Test 8 - Twilio call state must NOT be exposed to an external, spoofable status-callback webhook.

        P1-12 hardening: outbound call outcome is owned entirely by the worker post-call flow.
        The Twilio REST CreateCall must therefore NEVER register StatusCallback /
        StatusCallbackEvent / StatusCallbackMethod (no forgeable URL), and the payload must
        not carry any 42voice backend webhook destination that a forged Twilio status POST
        could target to mutate call state.
        """
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_no_status_callback"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            settings_obj.twilio_sip_domain = "42voice.pstn.twilio.com"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+919381408134",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            res = await initiate_call(req, current_user=self.user_a)

            self.assertEqual(res.status_code, 200)
            call_kwargs = mock_http_client.post.call_args[1]
            data = call_kwargs["data"]

            # No spoofable Twilio status callback may ever be registered
            for forbidden_key in (
                "StatusCallback",
                "StatusCallbackEvent",
                "StatusCallbackMethod",
                "StatusCallbackUrl",
            ):
                self.assertNotIn(forbidden_key, data, f"payload must not register '{forbidden_key}'")

        # And the request URL must target the Twilio REST CreateCall endpoint
        # (no 42voice backend path that could receive a forged status POST).
        request_url = mock_http_client.post.call_args[0][0]
        self.assertIn("/2010-04-01/Accounts/", request_url)
        self.assertIn("/Calls.json", request_url)
        self.assertNotIn("42voice-livekit", request_url)

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    async def test_twiml_generation_missing_endpoint_fails_with_400(
        self, mock_db_query, mock_db_service
    ):
        """Test 8 - If LiveKit SIP endpoint cannot be resolved, initiate_call raises HTTP 400."""
        config_no_endpoint = dict(self.mock_config)
        config_no_endpoint["raw_credentials"] = {
            "account_sid": self.account_sid,
            "auth_token": self.encrypted_auth_token
            # No livekit_sip_uri, no twilio_trunk_sid
        }

        mock_db_service.get_telephony_configuration = AsyncMock(return_value=config_no_endpoint)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = None  # Not configured
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+919381408134",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            with self.assertRaises(HTTPException) as ctx:
                await initiate_call(req, current_user=self.user_a)

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("LiveKit SIP public endpoint is not configured", ctx.exception.detail)


    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.livekit_sip_service")
    @patch("api.modules.telephony_configs.routes.inbound_sip_bridge.ensure_inbound_sip_agent_dispatch")
    async def test_twilio_fallback_schedules_inbound_sip_bridge(
        self, mock_ensure_bridge, mock_lk_service, mock_db_query, mock_db_service
    ):
        """Wiring test - Twilio fallback success schedules the inbound SIP bridge task with the correct caller/agent/metadata."""
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
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            settings_obj.twilio_sip_domain = "42v-test.pstn.twilio.com"
            mock_settings.return_value = settings_obj

            with patch("livekit.api.LiveKitAPI") as mock_lk_cls:
                mock_lk = MagicMock()
                mock_lk_cls.return_value = mock_lk
                mock_lk.agent_dispatch.create_dispatch = AsyncMock()
                mock_lk.aclose = AsyncMock()
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
                    mock_response.json.return_value = {"sid": "CA_twilio_bridge_fallback"}
                    mock_http_client.post.return_value = mock_response
                    mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

                    agent_id = "86818021-5dcf-4ee5-b4fd-3b04e16f17c8"
                    req = InitiateCallRequest(
                        phone_number="+61400111222",
                        telephony_configuration_id="11111111-1111-1111-1111-111111111111",
                        agent_id=agent_id
                    )

                    res = await initiate_call(req, current_user=self.user_a)
                    self.assertEqual(res.status_code, 200)

                    # Let the fire-and-forget bridge task run
                    await asyncio.sleep(0.05)

                    mock_ensure_bridge.assert_awaited_once()
                    kwargs = mock_ensure_bridge.await_args.kwargs
                    self.assertEqual(kwargs["caller_id"], "+6498736772")
                    self.assertEqual(kwargs["agent_name"], "inbound-agent")
                    metadata = json.loads(kwargs["metadata"])
                    expected_agent_name = "Voice Agent"
                    self.assertEqual(metadata["agent_id"], agent_id)
                    self.assertEqual(metadata["agent_name"], expected_agent_name)
                    self.assertEqual(metadata["from_phone_number"], "+6498736772")
                    self.assertEqual(metadata["dest_number"], "+61400111222")

    @patch("api.modules.telephony_configs.routes.db_service")
    @patch("api.modules.telephony_configs.routes.database.query")
    @patch("api.modules.telephony_configs.routes.httpx.AsyncClient")
    async def test_inbound_sip_bridge_not_scheduled_without_livekit_creds(
        self, mock_httpx_cls, mock_db_query, mock_db_service
    ):
        """Wiring test - when LiveKit is not configured, no bridge task is scheduled (equal-loader fallback still works)."""
        mock_db_service.get_telephony_configuration = AsyncMock(return_value=self.mock_config)
        mock_db_service.list_phone_numbers = AsyncMock(return_value=[self.mock_phone])
        mock_db_query.return_value = []

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sid": "CA_twilio_call_nobridge"}
        mock_http_client.post.return_value = mock_response
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("api.modules.telephony_configs.routes.get_settings") as mock_settings:
            settings_obj = MagicMock()
            settings_obj.livekit_url = None
            settings_obj.livekit_api_key = None
            settings_obj.livekit_api_secret = None
            settings_obj.livekit_sip_public_uri = "sip:187.52.120.31:5060;transport=tcp"
            mock_settings.return_value = settings_obj

            req = InitiateCallRequest(
                phone_number="+61400111222",
                telephony_configuration_id="11111111-1111-1111-1111-111111111111"
            )

            with patch("api.modules.telephony_configs.routes._schedule_inbound_sip_bridge") as mock_schedule:
                res = await initiate_call(req, current_user=self.user_a)
                self.assertEqual(res.status_code, 200)
                mock_schedule.assert_not_called()


if __name__ == "__main__":
    unittest.main()
