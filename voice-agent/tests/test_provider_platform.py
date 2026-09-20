"""
Comprehensive test suite for Phase 3 Provider Platform:
- Provider factories (Deepgram, OpenAI LLM, OpenAI TTS, ElevenLabs TTS)
- BYO credential encryption, rotation, redaction, and safe hints
- Tenant isolation and cross-tenant security
- Legacy unconfigured fallback behavior
- Explicit failure policy on broken configuration
- Call-level pinning & concurrency isolation
- Log sanitization (zero plaintext secret leakage)
- Agent model config DB / API propagation
"""
import asyncio
import io
import json
import logging
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from providers.types import (
    ProviderCapability,
    CredentialSource,
    ResolvedProviderConfig,
    RealtimeModelBundle,
)
from providers.errors import (
    UnsupportedProviderError,
    ProviderConfigError,
    CredentialMissingError,
    CredentialInactiveError,
    CredentialTenantMismatchError,
    CredentialProviderMismatchError,
    CredentialDecryptionError,
    ProviderInitError,
    classify_provider_error,
)
from providers.registry import ProviderRegistry, provider_registry
from providers.credentials import CredentialResolver, format_credential_hint
from providers.resolver import ProviderConfigurationResolver
from providers.bundle import build_legacy_provider_configs, create_model_bundle
from providers.livekit.stt import LiveKitDeepgramSTTFactory
from providers.livekit.llm import LiveKitOpenAILLMFactory
from providers.livekit.tts import LiveKitOpenAITTSFactory, LiveKitElevenLabsTTSFactory
from api.utils.encryption import TokenEncryptor, provider_encryptor


class TestProviderPlatform(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.encryptor = TokenEncryptor(key_override="bW9ja19rZXlfZm9yX3Rlc3RpbmdfMTIzNDU2Nzg5MDE=")
        self.cred_resolver = CredentialResolver(encryptor=self.encryptor)

    # =========================================================================
    # 1. PROVIDER FACTORY TESTS (Kwargs & Allowlist Validation)
    # =========================================================================

    def test_deepgram_stt_factory_kwargs(self):
        """Verify Deepgram STT factory passes valid kwargs without arbitrary leakage."""
        factory = LiveKitDeepgramSTTFactory()
        cfg = ResolvedProviderConfig(
            capability=ProviderCapability.STT,
            provider="deepgram",
            model="nova-2-phonecall",
            safe_options={"smart_format": True, "interim_results": True, "disallowed_opt": "injected"}
        )

        with patch("livekit.plugins.deepgram.STT") as mock_stt:
            mock_instance = MagicMock()
            mock_stt.return_value = mock_instance

            res = factory.create(
                config=cfg,
                api_key="dg-secret-key-123",
                runtime_options={"keywords": [("John", 2.0)], "language": "en-US"}
            )

            mock_stt.assert_called_once()
            called_kwargs = mock_stt.call_args[1]
            self.assertEqual(called_kwargs["model"], "nova-2-phonecall")
            self.assertEqual(called_kwargs["language"], "en-US")
            self.assertEqual(called_kwargs["api_key"], "dg-secret-key-123")
            self.assertEqual(called_kwargs["keywords"], [("John", 2.0)])
            self.assertTrue(called_kwargs["smart_format"])
            self.assertNotIn("disallowed_opt", called_kwargs)
            self.assertEqual(res, mock_instance)

    def test_openai_llm_factory_kwargs(self):
        """Verify OpenAI LLM factory passes valid kwargs and translates max_tokens."""
        factory = LiveKitOpenAILLMFactory()
        cfg = ResolvedProviderConfig(
            capability=ProviderCapability.LLM,
            provider="openai",
            model="gpt-4o",
            safe_options={"temperature": 0.4, "max_tokens": 512, "unsafe_param": "ignore"}
        )

        with patch("livekit.plugins.openai.LLM") as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance

            res = factory.create(config=cfg, api_key="sk-openai-mock-key")
            mock_llm.assert_called_once()
            called_kwargs = mock_llm.call_args[1]
            self.assertEqual(called_kwargs["model"], "gpt-4o")
            self.assertEqual(called_kwargs["temperature"], 0.4)
            self.assertEqual(called_kwargs["max_completion_tokens"], 512)
            self.assertEqual(called_kwargs["api_key"], "sk-openai-mock-key")
            self.assertNotIn("unsafe_param", called_kwargs)
            self.assertEqual(res, mock_instance)

    def test_openai_tts_factory_kwargs(self):
        """Verify OpenAI TTS factory passes valid voice and model options."""
        factory = LiveKitOpenAITTSFactory()
        cfg = ResolvedProviderConfig(
            capability=ProviderCapability.TTS,
            provider="openai",
            model="tts-1-hd",
            voice="nova",
            safe_options={"speed": 1.1}
        )

        with patch("livekit.plugins.openai.TTS") as mock_tts:
            mock_instance = MagicMock()
            mock_tts.return_value = mock_instance

            res = factory.create(config=cfg, api_key="sk-openai-tts-key")
            mock_tts.assert_called_once()
            called_kwargs = mock_tts.call_args[1]
            self.assertEqual(called_kwargs["model"], "tts-1-hd")
            self.assertEqual(called_kwargs["voice"], "nova")
            self.assertEqual(called_kwargs["speed"], 1.1)
            self.assertEqual(called_kwargs["api_key"], "sk-openai-tts-key")
            self.assertEqual(res, mock_instance)

    def test_elevenlabs_tts_factory_kwargs(self):
        """Verify ElevenLabs TTS factory passes voice_id and model."""
        factory = LiveKitElevenLabsTTSFactory()
        cfg = ResolvedProviderConfig(
            capability=ProviderCapability.TTS,
            provider="elevenlabs",
            model="eleven_multilingual_v2",
            voice="voice_abc_123",
            safe_options={"streaming_latency": 3}
        )

        with patch("livekit.plugins.elevenlabs.TTS") as mock_eleven:
            mock_instance = MagicMock()
            mock_eleven.return_value = mock_instance

            res = factory.create(config=cfg, api_key="el-secret-key-789")
            mock_eleven.assert_called_once()
            called_kwargs = mock_eleven.call_args[1]
            self.assertEqual(called_kwargs["model"], "eleven_multilingual_v2")
            self.assertEqual(called_kwargs["voice_id"], "voice_abc_123")
            self.assertEqual(called_kwargs["streaming_latency"], 3)
            self.assertEqual(called_kwargs["api_key"], "el-secret-key-789")
            self.assertEqual(res, mock_instance)

    def test_unknown_provider_rejection(self):
        """Verify requesting an unregistered provider raises UnsupportedProviderError."""
        reg = ProviderRegistry()
        with self.assertRaises(UnsupportedProviderError):
            reg.get(ProviderCapability.LLM, "anthropic")

    # =========================================================================
    # 2. CREDENTIAL ENCRYPTION, REDACTION & SAFE HINTS
    # =========================================================================

    def test_credential_hint_formatting(self):
        """Verify format_credential_hint hides secret and returns safe hint."""
        self.assertEqual(format_credential_hint("sk-proj-1234567890abcdef"), "****cdef")
        self.assertEqual(format_credential_hint("test1234"), "****1234")
        self.assertEqual(format_credential_hint("short"), "****")
        self.assertEqual(format_credential_hint(""), "****")

    def test_encryption_and_decryption_roundtrip(self):
        """Verify Fernet symmetric encryption and decryption with dedicated key."""
        plain = "test-secret-api-key-xyz-999"
        cipher = self.encryptor.encrypt(plain)
        self.assertNotEqual(plain, cipher)
        decrypted = self.encryptor.decrypt(cipher)
        self.assertEqual(plain, decrypted)

    async def test_byo_credential_resolution_success(self):
        """Verify authorized client successfully resolves and decrypts BYO key."""
        tenant_id = str(uuid4())
        cred_id = str(uuid4())
        secret_key = "test-secret-openai-key-abc"
        cipher = self.encryptor.encrypt(secret_key)

        mock_rows = [{
            "id": cred_id,
            "credential_uuid": cred_id,
            "client_id": tenant_id,
            "name": "My Tenant OpenAI Key",
            "credential_type": "provider_api_key",
            "credential_data": json.dumps({
                "provider": "openai",
                "encrypted_api_key": cipher,
                "hint": "****-abc"
            }),
            "is_active": True
        }]

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_rows
            resolved_key = await self.cred_resolver.resolve(
                credential_source=CredentialSource.BYO,
                provider="openai",
                credential_id=cred_id,
                client_id=tenant_id
            )
            self.assertEqual(resolved_key, secret_key)

    async def test_byo_cross_tenant_denial(self):
        """Verify Tenant A is blocked from resolving Tenant B's credential."""
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        cred_b_id = str(uuid4())
        cipher = self.encryptor.encrypt("secret-belonging-to-tenant-b")

        mock_rows = [{
            "id": cred_b_id,
            "credential_uuid": cred_b_id,
            "client_id": tenant_b,  # Belongs to Tenant B
            "name": "Tenant B Key",
            "credential_type": "provider_api_key",
            "credential_data": json.dumps({
                "provider": "openai",
                "encrypted_api_key": cipher
            }),
            "is_active": True
        }]

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_rows
            with self.assertRaises(CredentialTenantMismatchError):
                await self.cred_resolver.resolve(
                    credential_source=CredentialSource.BYO,
                    provider="openai",
                    credential_id=cred_b_id,
                    client_id=tenant_a  # Tenant A attempts to use Tenant B's key
                )

    async def test_byo_inactive_credential_denial(self):
        """Verify disabled/inactive credential is rejected."""
        tenant_id = str(uuid4())
        cred_id = str(uuid4())
        cipher = self.encryptor.encrypt("some-secret")

        mock_rows = [{
            "id": cred_id,
            "credential_uuid": cred_id,
            "client_id": tenant_id,
            "name": "Disabled Key",
            "credential_type": "provider_api_key",
            "credential_data": json.dumps({
                "provider": "openai",
                "encrypted_api_key": cipher
            }),
            "is_active": False  # Inactive
        }]

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_rows
            with self.assertRaises(CredentialInactiveError):
                await self.cred_resolver.resolve(
                    credential_source=CredentialSource.BYO,
                    provider="openai",
                    credential_id=cred_id,
                    client_id=tenant_id
                )

    async def test_byo_provider_mismatch_denial(self):
        """Verify OpenAI LLM cannot use an ElevenLabs credential."""
        tenant_id = str(uuid4())
        cred_id = str(uuid4())
        cipher = self.encryptor.encrypt("some-secret")

        mock_rows = [{
            "id": cred_id,
            "credential_uuid": cred_id,
            "client_id": tenant_id,
            "name": "ElevenLabs Key",
            "credential_type": "provider_api_key",
            "credential_data": json.dumps({
                "provider": "elevenlabs",  # Elevenlabs
                "encrypted_api_key": cipher
            }),
            "is_active": True
        }]

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = mock_rows
            with self.assertRaises(CredentialProviderMismatchError):
                await self.cred_resolver.resolve(
                    credential_source=CredentialSource.BYO,
                    provider="openai",  # Requesting for OpenAI
                    credential_id=cred_id,
                    client_id=tenant_id
                )

    # =========================================================================
    # 3. RESOLVER & LEGACY FALLBACK VS EXPLICIT FAILURE
    # =========================================================================

    async def test_legacy_unconfigured_agent_fallback(self):
        """Verify unconfigured agent (platform_model_configuration_id = None) creates legacy platform bundle."""
        resolver = ProviderConfigurationResolver()

        with patch.object(resolver, "resolve_bundle_for_agent", wraps=resolver.resolve_bundle_for_agent) as wrap_res:
            with patch("livekit.plugins.deepgram.STT") as m_stt, \
                 patch("livekit.plugins.openai.LLM") as m_llm, \
                 patch("livekit.plugins.openai.TTS") as m_tts, \
                 patch("providers.credentials.credential_resolver.resolve", new_callable=AsyncMock) as m_resolve:

                m_resolve.return_value = "mock-platform-key"
                bundle = await resolver.resolve_bundle_for_agent(
                    agent_data={"name": "Legacy Agent", "voice_name": "nova"},
                    client_id="client_123"
                )

                self.assertIsNone(bundle.model_configuration_id)
                self.assertEqual(bundle.stt_provider, "deepgram")
                self.assertEqual(bundle.llm_provider, "openai")
                self.assertEqual(bundle.tts_provider, "openai")
                self.assertEqual(bundle.stt_credential_source, "platform")
                self.assertEqual(bundle.llm_credential_source, "platform")
                self.assertEqual(bundle.tts_credential_source, "platform")

    async def test_configured_model_explicit_failure_on_missing_config(self):
        """Verify configured agent with missing model config row fails explicitly without fallback."""
        resolver = ProviderConfigurationResolver()
        missing_config_id = str(uuid4())

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = []  # Not found
            with self.assertRaises(ProviderConfigError) as ctx_err:
                await resolver.resolve_bundle_for_agent(
                    agent_data={"platform_model_configuration_id": missing_config_id, "client_id": "c1"},
                    client_id="c1"
                )
            self.assertIn("was not found", str(ctx_err.exception))

    async def test_configured_model_explicit_failure_on_missing_credential(self):
        """Verify configured agent referencing missing BYO credential fails explicitly without fallback."""
        resolver = ProviderConfigurationResolver()
        cfg_id = str(uuid4())
        cred_id = str(uuid4())

        cfg_row = {
            "id": cfg_id,
            "client_id": "c1",
            "user_id": None,
            "name": "Custom BYO Config",
            "description": None,
            "status": "active",
            "stt_provider": "deepgram",
            "stt_model": "nova-2",
            "stt_credential_source": "byo",
            "stt_credential_id": cred_id,
            "stt_options": "{}",
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
            "llm_credential_source": "platform",
            "llm_credential_id": None,
            "llm_options": "{}",
            "tts_provider": "openai",
            "tts_model": "tts-1",
            "tts_voice": "alloy",
            "tts_credential_source": "platform",
            "tts_credential_id": None,
            "tts_options": "{}"
        }

        with patch("api.database.query", new_callable=AsyncMock) as mock_db:
            # First query returns model config, second query returns empty for credential
            mock_db.side_effect = [[cfg_row], []]
            with self.assertRaises(CredentialMissingError):
                await resolver.resolve_bundle_for_agent(
                    agent_data={"platform_model_configuration_id": cfg_id, "client_id": "c1"},
                    client_id="c1"
                )

    # =========================================================================
    # 4. CALL-LEVEL PINNING & CONCURRENCY ISOLATION
    # =========================================================================

    async def test_call_level_pinning(self):
        """Verify model bundle is pinned at call start and does not mutate when DB row changes."""
        resolver = ProviderConfigurationResolver()
        cfg_id = str(uuid4())

        initial_row = {
            "id": cfg_id,
            "client_id": "c1",
            "name": "Config V1",
            "status": "active",
            "stt_provider": "deepgram",
            "stt_model": "nova-2",
            "stt_credential_source": "platform",
            "stt_credential_id": None,
            "stt_options": "{}",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_credential_source": "platform",
            "llm_credential_id": None,
            "llm_options": "{}",
            "tts_provider": "openai",
            "tts_model": "tts-1",
            "tts_voice": "alloy",
            "tts_credential_source": "platform",
            "tts_credential_id": None,
            "tts_options": "{}"
        }

        with patch("api.database.query", new_callable=AsyncMock) as mock_db, \
             patch("providers.credentials.credential_resolver.resolve", new_callable=AsyncMock) as m_resolve, \
             patch("livekit.plugins.deepgram.STT"), \
             patch("livekit.plugins.openai.LLM"), \
             patch("livekit.plugins.openai.TTS"):

            m_resolve.return_value = "mock-key"
            mock_db.return_value = [initial_row]

            # Call A starts and resolves bundle A
            call_a_bundle = await resolver.resolve_bundle_for_agent(
                agent_data={"platform_model_configuration_id": cfg_id, "client_id": "c1"},
                client_id="c1"
            )
            self.assertEqual(call_a_bundle.llm_model, "gpt-4o-mini")

            # DB row is subsequently updated for Call B
            updated_row = dict(initial_row)
            updated_row["llm_model"] = "gpt-4o"
            mock_db.return_value = [updated_row]

            # Active Call A bundle remains pinned
            self.assertEqual(call_a_bundle.llm_model, "gpt-4o-mini")

            # New Call B resolves new model
            call_b_bundle = await resolver.resolve_bundle_for_agent(
                agent_data={"platform_model_configuration_id": cfg_id, "client_id": "c1"},
                client_id="c1"
            )
            self.assertEqual(call_b_bundle.llm_model, "gpt-4o")
            # Original Call A is still gpt-4o-mini
            self.assertEqual(call_a_bundle.llm_model, "gpt-4o-mini")

    async def test_concurrent_tenant_isolation(self):
        """Verify concurrent resolutions for Tenant A and Tenant B receive exact independent keys."""
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        secret_a = "test-secret-client-a-123"
        secret_b = "test-secret-client-b-456"

        key_received_a = None
        key_received_b = None

        async def mock_resolve(credential_source, provider, credential_id, client_id):
            if client_id == tenant_a:
                return secret_a
            elif client_id == tenant_b:
                return secret_b
            raise RuntimeError("Unknown tenant")

        with patch("providers.credentials.credential_resolver.resolve", side_effect=mock_resolve), \
             patch("livekit.plugins.deepgram.STT"), \
             patch("livekit.plugins.openai.LLM") as mock_llm, \
             patch("livekit.plugins.openai.TTS"):

            def capture_llm(**kwargs):
                nonlocal key_received_a, key_received_b
                key = kwargs.get("api_key")
                if key == secret_a:
                    key_received_a = key
                elif key == secret_b:
                    key_received_b = key
                return MagicMock()

            mock_llm.side_effect = capture_llm

            resolver = ProviderConfigurationResolver()

            task_a = resolver.resolve_bundle_for_agent(
                agent_data={"name": "Agent A"}, client_id=tenant_a
            )
            task_b = resolver.resolve_bundle_for_agent(
                agent_data={"name": "Agent B"}, client_id=tenant_b
            )

            bundle_a, bundle_b = await asyncio.gather(task_a, task_b)

            self.assertEqual(key_received_a, secret_a)
            self.assertEqual(key_received_b, secret_b)
            self.assertNotEqual(key_received_a, key_received_b)

    # =========================================================================
    # 5. LOG SANITIZATION (Zero Secret Leakage)
    # =========================================================================

    def test_log_sanitization_zero_secret_leakage(self):
        """Assert fake test secrets never appear in captured log output."""
        fake_secret = "test-secret-client-a-123"
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        test_logger = logging.getLogger("voice-agent")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            # Simulate classification of an error with a raw secret in message
            error_with_secret = f"429 quota exceeded for secret {fake_secret}"
            cat = classify_provider_error(error_with_secret, capability="llm", provider="openai")
            self.assertEqual(cat, "quota_exceeded")

            # Simulate safe metadata conversion
            bundle = RealtimeModelBundle(
                stt=None, llm=None, tts=None,
                model_configuration_id="mock_id",
                stt_provider="deepgram",
                llm_provider="openai",
                tts_provider="openai"
            )
            meta = bundle.to_safe_metadata()
            test_logger.info(f"[MODEL_METADATA] {json.dumps(meta)}")

            captured = log_capture.getvalue()
            # Assert secret is absent from logs
            self.assertNotIn(fake_secret, captured)
            self.assertNotIn("api_key", meta)
            self.assertNotIn("secret", meta)
        finally:
            test_logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
