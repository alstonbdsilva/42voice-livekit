import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# Import the sync provisioning helper directly
from api.modules.telephony_configs.routes import _sync_provision_twilio_user_sip_trunk


class TestTwilioSdkProvisioning(unittest.TestCase):
    
    @patch("api.modules.telephony_configs.routes.Client")
    def test_fresh_twilio_onboarding(self, mock_client_cls):
        """Test fresh onboarding when no trunk or credential list exists."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # Mock trunk list & create
        mock_client.trunking.v1.trunks.list.return_value = []
        mock_trunk = MagicMock()
        mock_trunk.sid = "TK_fresh_123"
        mock_trunk.domain_name = "42v-fresh.pstn.twilio.com"
        mock_client.trunking.v1.trunks.create.return_value = mock_trunk
        
        # Mock credential list & create
        mock_client.sip.credential_lists.list.return_value = []
        mock_cl = MagicMock()
        mock_cl.sid = "CL_fresh_123"
        mock_client.sip.credential_lists.create.return_value = mock_cl
        
        input_creds = {
            "account_sid": "AC_test_account_sid",
            "auth_token": "test_auth_token_123"
        }
        
        res = _sync_provision_twilio_user_sip_trunk("twilio", input_creds)
        
        self.assertEqual(res["account_sid"], "AC_test_account_sid")
        self.assertEqual(res["twilio_trunk_sid"], "TK_fresh_123")
        self.assertEqual(res["sip_domain"], "42v-fresh.pstn.twilio.com")
        self.assertEqual(res["sip_credential_list_sid"], "CL_fresh_123")
        self.assertTrue(res["sip_username"].startswith("lk_"))
        self.assertTrue(len(res["auth_token"]) > 0)
        self.assertTrue(len(res["sip_password"]) > 0)
        
        # Assert SDK calls were made
        mock_client.trunking.v1.trunks.create.assert_called_once_with(friendly_name="LiveKit-SIP-Trunk")
        mock_client.sip.credential_lists.create.assert_called_once()

    @patch("api.modules.telephony_configs.routes.Client")
    def test_existing_tk_cl_reuse(self, mock_client_cls):
        """Test reusing existing TK... trunk and CL... credential list on PUT/update."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        trunk_mock = MagicMock()
        trunk_mock.sid = "TK_existing_999"
        trunk_mock.domain_name = "42v-existing.pstn.twilio.com"
        mock_client.trunking.v1.trunks.side_effect = lambda sid=None: trunk_mock
        trunk_mock.fetch.return_value = trunk_mock
        trunk_mock.credentials_lists.list.return_value = [MagicMock(sid="CL_existing_999")]
        
        cl_mock = MagicMock()
        cl_mock.sid = "CL_existing_999"
        creds_mock = MagicMock()
        cl_mock.credentials = creds_mock
        mock_client.sip.credential_lists.side_effect = lambda sid=None: cl_mock
        cl_mock.fetch.return_value = cl_mock
        
        mock_cred = MagicMock()
        mock_cred.username = "lk_existing_user"
        creds_mock.list.return_value = [mock_cred]
        
        existing_creds = {
            "account_sid": "AC_existing_acc",
            "auth_token": "gAAAAABn_mock_encrypted_token",
            "twilio_trunk_sid": "TK_existing_999",
            "sip_domain": "42v-existing.pstn.twilio.com",
            "sip_credential_list_sid": "CL_existing_999",
            "sip_username": "lk_existing_user",
            "sip_password": "gAAAAABn_mock_encrypted_pass"
        }
        
        input_creds = {
            "account_sid": "****acc",
            "auth_token": "****token"
        }
        
        res = _sync_provision_twilio_user_sip_trunk("twilio", input_creds, existing_credentials=existing_creds)
        
        self.assertEqual(res["twilio_trunk_sid"], "TK_existing_999")
        self.assertEqual(res["sip_credential_list_sid"], "CL_existing_999")
        self.assertEqual(res["sip_username"], "lk_existing_user")
        
        # Ensure create calls were NOT made (idempotence)
        mock_client.trunking.v1.trunks.create.assert_not_called()
        mock_client.sip.credential_lists.create.assert_not_called()
        creds_mock.create.assert_not_called()

    @patch("api.modules.telephony_configs.routes.Client")
    def test_missing_sip_credential_recreation(self, mock_client_cls):
        """Test recreating SIP credential if it was deleted on Twilio."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        trunk_mock = MagicMock()
        trunk_mock.sid = "TK_existing_888"
        trunk_mock.domain_name = "42v-888.pstn.twilio.com"
        mock_client.trunking.v1.trunks.side_effect = lambda sid=None: trunk_mock
        trunk_mock.fetch.return_value = trunk_mock
        trunk_mock.credentials_lists.list.return_value = [MagicMock(sid="CL_existing_888")]
        
        cl_mock = MagicMock()
        cl_mock.sid = "CL_existing_888"
        creds_mock = MagicMock()
        cl_mock.credentials = creds_mock
        mock_client.sip.credential_lists.side_effect = lambda sid=None: cl_mock
        cl_mock.fetch.return_value = cl_mock
        
        # Credential list returns empty (credential deleted on Twilio)
        creds_mock.list.return_value = []
        
        existing_creds = {
            "account_sid": "AC_acc_888",
            "auth_token": "token_888",
            "twilio_trunk_sid": "TK_existing_888",
            "sip_domain": "42v-888.pstn.twilio.com",
            "sip_credential_list_sid": "CL_existing_888",
            "sip_username": "lk_old_user",
            "sip_password": "old_password"
        }
        
        input_creds = {
            "account_sid": "****888"
        }
        
        res = _sync_provision_twilio_user_sip_trunk("twilio", input_creds, existing_credentials=existing_creds)
        
        # Verify credentials.create was called to recreate credential
        creds_mock.create.assert_called_once()
        self.assertEqual(res["twilio_trunk_sid"], "TK_existing_888")

    @patch("api.modules.telephony_configs.routes.Client")
    def test_invalid_twilio_credentials(self, mock_client_cls):
        """Test invalid Account SID/Auth Token throws HTTP 400 error."""
        from twilio.base.exceptions import TwilioRestException
        
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # Mock TwilioRestException 401
        err = TwilioRestException(status=401, uri="/Trunks", msg="Authenticate failed", code=20003)
        mock_client.trunking.v1.trunks.side_effect = err
        
        input_creds = {
            "account_sid": "AC_invalid",
            "auth_token": "invalid_token"
        }
        
        with self.assertRaises(HTTPException) as ctx:
            _sync_provision_twilio_user_sip_trunk("twilio", input_creds)
            
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Authentication failed", ctx.exception.detail)


class TestTwilioInboundRoutingProvisioning(unittest.TestCase):

    @patch("api.modules.telephony_configs.routes.Client")
    def test_fresh_inbound_number_routing(self, mock_client_cls):
        """Test resolving PN... SID, associating with TK... trunk, and creating Origination URL."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock phone number resolution
        pn_mock = MagicMock()
        pn_mock.sid = "PN_fresh_999"
        pn_mock.phone_number = "+111111111"
        pn_mock.trunk_sid = None
        mock_client.incoming_phone_numbers.list.return_value = [pn_mock]

        # Mock trunk phone numbers association check (empty)
        mock_client.trunking.v1.trunks.return_value.phone_numbers.list.return_value = []
        # Mock origination URLs check (empty)
        orig_mock = MagicMock()
        orig_mock.sid = "OU_fresh_999"
        orig_mock.sip_url = "sip:187.52.120.31:5060;transport=tcp"
        mock_client.trunking.v1.trunks.return_value.origination_urls.create.return_value = orig_mock
        mock_client.trunking.v1.trunks.return_value.origination_urls.list.return_value = []

        creds = {
            "account_sid": "AC_user_a",
            "auth_token": "token_user_a",
            "twilio_trunk_sid": "TK_user_a"
        }

        res = _sync_provision_twilio_inbound_number(
            credentials=creds,
            phone_number="+111111111",
            origination_uri="sip:187.52.120.31:5060;transport=tcp"
        )

        self.assertEqual(res["twilio_phone_number_sid"], "PN_fresh_999")
        self.assertEqual(res["twilio_origination_url_sid"], "OU_fresh_999")
        self.assertEqual(res["twilio_trunk_sid"], "TK_user_a")

    @patch("api.modules.telephony_configs.routes.Client")
    def test_missing_livekit_sip_public_uri(self, mock_client_cls):
        """Test throwing HTTP 400 when LIVEKIT_SIP_PUBLIC_URI is missing or None."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        creds = {"account_sid": "AC_uri", "auth_token": "token_uri", "twilio_trunk_sid": "TK_uri"}

        with self.assertRaises(HTTPException) as ctx:
            _sync_provision_twilio_inbound_number(credentials=creds, phone_number="+111111111", origination_uri=None)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("LIVEKIT_SIP_PUBLIC_URI is not configured", ctx.exception.detail)

    @patch("api.modules.telephony_configs.routes.Client")
    def test_pn_already_on_different_tk_conflict(self, mock_client_cls):
        """Test throwing HTTP 409 CONFLICT when phone number is already assigned to a different TK trunk."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        pn_mock = MagicMock()
        pn_mock.sid = "PN_conflict_999"
        pn_mock.phone_number = "+111111111"
        pn_mock.trunk_sid = "TK_DIFFERENT_TRUNK"
        mock_client.incoming_phone_numbers.list.return_value = [pn_mock]

        creds = {"account_sid": "AC_user_conflict", "auth_token": "token_conflict", "twilio_trunk_sid": "TK_MY_TRUNK"}

        with self.assertRaises(HTTPException) as ctx:
            _sync_provision_twilio_inbound_number(
                credentials=creds,
                phone_number="+111111111",
                origination_uri="sip:187.52.120.31:5060;transport=tcp"
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("already assigned to a different Twilio Elastic SIP Trunk", ctx.exception.detail)

    @patch("api.modules.telephony_configs.routes.Client")
    def test_idempotent_inbound_routing(self, mock_client_cls):
        """Test that existing PN association and Origination URL do NOT create duplicates on repeat call."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        pn_mock = MagicMock()
        pn_mock.sid = "PN_idem_888"
        pn_mock.phone_number = "+222222222"
        pn_mock.trunk_sid = "TK_user_b"
        mock_client.incoming_phone_numbers.list.return_value = [pn_mock]

        assoc_mock = MagicMock()
        assoc_mock.sid = "PN_idem_888"
        assoc_mock.phone_number = "+222222222"
        mock_client.trunking.v1.trunks.return_value.phone_numbers.list.return_value = [assoc_mock]

        orig_mock = MagicMock()
        orig_mock.sid = "OU_existing_888"
        orig_mock.sip_url = "sip:187.52.120.31:5060;transport=tcp"
        mock_client.trunking.v1.trunks.return_value.origination_urls.list.return_value = [orig_mock]

        creds = {
            "account_sid": "AC_user_b",
            "auth_token": "token_user_b",
            "twilio_trunk_sid": "TK_user_b"
        }

        res = _sync_provision_twilio_inbound_number(
            credentials=creds,
            phone_number="+222222222",
            origination_uri="sip:187.52.120.31:5060;transport=tcp"
        )

        self.assertEqual(res["twilio_phone_number_sid"], "PN_idem_888")
        self.assertEqual(res["twilio_origination_url_sid"], "OU_existing_888")
        mock_client.trunking.v1.trunks.return_value.phone_numbers.create.assert_not_called()
        mock_client.trunking.v1.trunks.return_value.origination_urls.create.assert_not_called()

    @patch("api.modules.telephony_configs.routes.Client")
    def test_missing_origination_url_repair(self, mock_client_cls):
        """Test that missing Origination URL is recreated during repair when PN association exists."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        pn_mock = MagicMock()
        pn_mock.sid = "PN_repair_777"
        pn_mock.phone_number = "+333333333"
        pn_mock.trunk_sid = "TK_user_c"
        mock_client.incoming_phone_numbers.list.return_value = [pn_mock]

        assoc_mock = MagicMock()
        assoc_mock.sid = "PN_repair_777"
        mock_client.trunking.v1.trunks.return_value.phone_numbers.list.return_value = [assoc_mock]

        mock_client.trunking.v1.trunks.return_value.origination_urls.list.return_value = []
        new_ou_mock = MagicMock()
        new_ou_mock.sid = "OU_recreated_777"
        mock_client.trunking.v1.trunks.return_value.origination_urls.create.return_value = new_ou_mock

        creds = {
            "account_sid": "AC_user_c",
            "auth_token": "token_user_c",
            "twilio_trunk_sid": "TK_user_c"
        }

        res = _sync_provision_twilio_inbound_number(
            credentials=creds,
            phone_number="+333333333",
            origination_uri="sip:187.52.120.31:5060;transport=tcp"
        )

        self.assertEqual(res["twilio_phone_number_sid"], "PN_repair_777")
        self.assertEqual(res["twilio_origination_url_sid"], "OU_recreated_777")
        mock_client.trunking.v1.trunks.return_value.phone_numbers.create.assert_not_called()
        mock_client.trunking.v1.trunks.return_value.origination_urls.create.assert_called_once()

    @patch("api.modules.telephony_configs.routes.Client")
    def test_phone_number_not_in_account(self, mock_client_cls):
        """Test throwing HTTP 400 when phone number is not found in user's Twilio account."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_inbound_number

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.incoming_phone_numbers.list.return_value = []

        creds = {
            "account_sid": "AC_user_d",
            "auth_token": "token_user_d",
            "twilio_trunk_sid": "TK_user_d"
        }

        with self.assertRaises(HTTPException) as ctx:
            _sync_provision_twilio_inbound_number(
                credentials=creds,
                phone_number="+999999999",
                origination_uri="sip:187.52.120.31:5060;transport=tcp"
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not found in this Twilio account", ctx.exception.detail)


class TestMultiUserIsolationAndTrunkAuth(unittest.IsolatedAsyncioTestCase):

    @patch("api.modules.telephony_configs.routes.Client")
    def test_multi_user_isolation(self, mock_client_cls):
        """Test User A and User B resource provisioning operate independently."""
        from api.modules.telephony_configs.routes import _sync_provision_twilio_user_sip_trunk

        client_a = MagicMock()
        client_b = MagicMock()
        mock_client_cls.side_effect = lambda sid, token: client_a if sid == "AC_UserA" else client_b

        trunk_a = MagicMock(sid="TK_UserA", domain_name="42v-usera.pstn.twilio.com")
        client_a.trunking.v1.trunks.list.return_value = []
        client_a.trunking.v1.trunks.create.return_value = trunk_a
        cl_a = MagicMock(sid="CL_UserA")
        client_a.sip.credential_lists.list.return_value = []
        client_a.sip.credential_lists.create.return_value = cl_a

        trunk_b = MagicMock(sid="TK_UserB", domain_name="42v-userb.pstn.twilio.com")
        client_b.trunking.v1.trunks.list.return_value = []
        client_b.trunking.v1.trunks.create.return_value = trunk_b
        cl_b = MagicMock(sid="CL_UserB")
        client_b.sip.credential_lists.list.return_value = []
        client_b.sip.credential_lists.create.return_value = cl_b

        res_a = _sync_provision_twilio_user_sip_trunk("twilio", {"account_sid": "AC_UserA", "auth_token": "tokenA"})
        res_b = _sync_provision_twilio_user_sip_trunk("twilio", {"account_sid": "AC_UserB", "auth_token": "tokenB"})

        self.assertEqual(res_a["twilio_trunk_sid"], "TK_UserA")
        self.assertEqual(res_b["twilio_trunk_sid"], "TK_UserB")
        self.assertNotEqual(res_a["twilio_trunk_sid"], res_b["twilio_trunk_sid"])
        self.assertEqual(res_a["sip_credential_list_sid"], "CL_UserA")
        self.assertEqual(res_b["sip_credential_list_sid"], "CL_UserB")
        self.assertNotEqual(res_a["sip_credential_list_sid"], res_b["sip_credential_list_sid"])

    @patch("api.modules.telephony_configs.db_service.database.query")
    async def test_cross_user_db_access_prevention(self, mock_db_query):
        """Test that User A cannot access or update User B's telephony configuration."""
        from api.modules.telephony_configs import db_service

        # DB query returns empty list when scoped to User A's client_id for User B's config_id
        mock_db_query.return_value = []

        config_b_id = "11111111-1111-1111-1111-111111111111"
        user_a_client_id = "22222222-2222-2222-2222-222222222222"

        res = await db_service.get_telephony_configuration(config_b_id, client_id=user_a_client_id)
        self.assertIsNone(res)

        updated = await db_service.update_telephony_configuration(config_b_id, name="Hacked Name", client_id=user_a_client_id)
        self.assertIsNone(updated)

        deleted = await db_service.delete_telephony_configuration(config_b_id, client_id=user_a_client_id)
        self.assertFalse(deleted)

    @patch("api.modules.phone_numbers.livekit_sip.lk_api")
    async def test_livekit_trunk_auth_split(self, mock_lk_api):
        """Test inbound trunk omits auth credentials completely for Twilio while outbound trunk includes digest auth."""
        from api.modules.phone_numbers.livekit_sip import livekit_sip_service

        sip_config = {
            "provider": "twilio",
            "sip_domain": "42v-test.pstn.twilio.com",
            "sip_username": "lk_user_test",
            "sip_password": "encrypted_password"
        }

        with patch.object(livekit_sip_service, "_get_client") as mock_get_client:
            mock_lk = MagicMock()
            mock_get_client.return_value = mock_lk
            mock_lk.sip.create_inbound_trunk = unittest.mock.AsyncMock(return_value=MagicMock(sip_trunk_id="ST_inbound_123"))
            mock_lk.sip.create_dispatch_rule = unittest.mock.AsyncMock(return_value=MagicMock(sip_dispatch_rule_id="DR_123"))
            mock_lk.sip.create_outbound_trunk = unittest.mock.AsyncMock(return_value=MagicMock(sip_trunk_id="ST_outbound_123"))
            mock_lk.aclose = unittest.mock.AsyncMock()

            # Provision inbound trunk
            inbound_id, dispatch_id, err = await livekit_sip_service.provision_inbound_trunk(
                number="+111111111",
                name="Test Line",
                sip_config=sip_config
            )

            # Inspect SIPInboundTrunkInfo passed to LiveKit - verify auth fields are completely omitted
            inbound_call_args = mock_lk_api.SIPInboundTrunkInfo.call_args[1]
            self.assertNotIn("auth_username", inbound_call_args)
            self.assertNotIn("auth_password", inbound_call_args)
            self.assertNotIn("auth_realm", inbound_call_args)

            # Provision outbound trunk
            outbound_id, err = await livekit_sip_service.provision_outbound_trunk(
                number="+111111111",
                name="Test Line",
                sip_config=sip_config
            )

            # Inspect SIPOutboundTrunkInfo passed to LiveKit - verify digest auth fields are present
            outbound_call_args = mock_lk_api.SIPOutboundTrunkInfo.call_args[1]
            self.assertEqual(outbound_call_args["auth_username"], "lk_user_test")
            self.assertTrue(len(outbound_call_args["auth_password"]) > 0)


if __name__ == "__main__":
    unittest.main()

