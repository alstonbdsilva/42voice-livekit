"""
Tests for Model Configurations API, Credential API, and Agent Model Config Integration.
"""
import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app
from api.middlewares.auth import get_current_user


class TestModelConfigsApi(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client_id = str(uuid4())
        self.user_id = str(uuid4())
        self.test_user = {
            "id": self.user_id,
            "client_id": self.client_id,
            "email": "test@tenant.com",
            "role": "CLIENT_ADMIN"
        }
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_model_config_success(self):
        """Test creating a valid platform model configuration."""
        payload = {
            "name": "Production Voice Bundle",
            "description": "Deepgram Nova-2 + GPT-4o-mini + OpenAI TTS",
            "stt_provider": "deepgram",
            "stt_model": "nova-2-phonecall",
            "stt_credential_source": "platform",
            "stt_options": {"smart_format": True},
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_credential_source": "platform",
            "llm_options": {"temperature": 0.5},
            "tts_provider": "openai",
            "tts_model": "tts-1",
            "tts_voice": "nova",
            "tts_credential_source": "platform",
            "tts_options": {"speed": 1.05}
        }

        mock_created_row = {
            "id": str(uuid4()),
            "client_id": self.client_id,
            "user_id": self.user_id,
            "name": payload["name"],
            "description": payload["description"],
            "status": "active",
            "stt_provider": "deepgram",
            "stt_model": "nova-2-phonecall",
            "stt_credential_source": "platform",
            "stt_credential_id": None,
            "stt_options": json.dumps({"smart_format": True}),
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_credential_source": "platform",
            "llm_credential_id": None,
            "llm_options": json.dumps({"temperature": 0.5}),
            "tts_provider": "openai",
            "tts_model": "tts-1",
            "tts_voice": "nova",
            "tts_credential_source": "platform",
            "tts_credential_id": None,
            "tts_options": json.dumps({"speed": 1.05}),
            "created_at": "2026-09-19T23:30:00Z",
            "updated_at": "2026-09-19T23:30:00Z",
        }

        with patch("api.modules.model_configs.repositories.ModelConfigRepository.create", new_callable=AsyncMock) as m_create:
            m_create.return_value = mock_created_row
            resp = self.client.post("/api/v1/model-configs", json=payload)
            self.assertEqual(resp.status_code, 201)
            data = resp.json()["data"]
            self.assertEqual(data["name"], "Production Voice Bundle")
            self.assertEqual(data["stt_provider"], "deepgram")
            self.assertEqual(data["llm_provider"], "openai")
            self.assertEqual(data["tts_voice"], "nova")

    def test_create_model_config_unsupported_provider_rejected(self):
        """Test creating model config with unsupported provider returns 400."""
        payload = {
            "name": "Invalid Provider Config",
            "stt_provider": "unsupported_stt",
            "llm_provider": "openai",
            "tts_provider": "openai"
        }
        resp = self.client.post("/api/v1/model-configs", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported STT provider", resp.json().get("message", ""))

    def test_create_model_config_byo_missing_credential_id_rejected(self):
        """Test specifying byo without credential_id returns 400."""
        payload = {
            "name": "BYO without Credential",
            "stt_provider": "deepgram",
            "llm_provider": "openai",
            "llm_credential_source": "byo",
            "llm_credential_id": None,  # Missing
            "tts_provider": "openai"
        }
        resp = self.client.post("/api/v1/model-configs", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("requires a valid 'credential_id'", resp.json().get("message", ""))

    def test_create_byo_credential_encrypts_and_redacts_response(self):
        """Test creating provider_api_key credential encrypts secret and returns safe hint only."""
        payload = {
            "name": "Tenant BYO OpenAI Key",
            "credential_type": "provider_api_key",
            "credential_data": {
                "provider": "openai",
                "api_key": "sk-proj-secret-token-12345678"
            }
        }

        mock_created_cred = {
            "id": str(uuid4()),
            "credential_uuid": str(uuid4()),
            "client_id": self.client_id,
            "name": "Tenant BYO OpenAI Key",
            "description": None,
            "credential_type": "provider_api_key",
            "credential_data": {
                "provider": "openai",
                "encrypted_api_key": "gAAAAABmockCiphertext...",
                "hint": "****5678"
            },
            "is_active": True,
            "created_at": "2026-09-19T23:30:00Z",
            "updated_at": "2026-09-19T23:30:00Z"
        }

        with patch("api.modules.credentials.repositories.CredentialRepository.create", new_callable=AsyncMock) as m_create:
            m_create.return_value = mock_created_cred
            resp = self.client.post("/api/v1/credentials", json=payload)
            self.assertEqual(resp.status_code, 201)
            data = resp.json()["data"]
            self.assertEqual(data["name"], "Tenant BYO OpenAI Key")
            self.assertEqual(data["provider"], "openai")
            self.assertEqual(data["credentialHint"], "****5678")
            # Assert plaintext and encrypted secrets are NEVER returned in response
            self.assertNotIn("api_key", data)
            self.assertNotIn("encrypted_api_key", data)
            self.assertNotIn("credential_data", data)
            self.assertNotIn("secret", data)


if __name__ == "__main__":
    unittest.main()
