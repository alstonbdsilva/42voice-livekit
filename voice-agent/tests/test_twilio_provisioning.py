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


if __name__ == "__main__":
    unittest.main()
