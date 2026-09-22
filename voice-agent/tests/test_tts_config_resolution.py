import os
import unittest
from unittest.mock import MagicMock, patch
from config import get_settings
from agent import _build_tts


class TestTTSConfigResolution(unittest.TestCase):
    """Test suite verifying that UI/DB is the single source of truth for TTS configuration,
    with zero silent fallbacks and complete elimination of .env model/voice defaults.
    """

    def setUp(self):
        self.settings = get_settings()

    def test_01_config_does_not_have_model_or_voice_defaults(self):
        """Verify that Settings contains only credentials and no TTS model/voice defaults."""
        self.assertFalse(hasattr(self.settings, "elevenlabs_tts_model"), "elevenlabs_tts_model must not exist in config")
        self.assertFalse(hasattr(self.settings, "elevenlabs_tts_voice_id"), "elevenlabs_tts_voice_id must not exist in config")
        self.assertFalse(hasattr(self.settings, "cartesia_t5_model"), "cartesia_t5_model must not exist in config")
        self.assertFalse(hasattr(self.settings, "cartesia_voice_id"), "cartesia_voice_id must not exist in config")
        self.assertFalse(hasattr(self.settings, "tts_provider"), "tts_provider must not exist in config")

    def test_02_elevenlabs_resolves_db_model_and_voice(self):
        """Test A: provider=elevenlabs with Model A and Voice A."""
        agent_data = {
            "tts_provider": "elevenlabs",
            "tts_model": "eleven_turbo_v2_5",
            "tts_voice_id": "voice_alpha_123",
            "tts_voice_name": "Alpha Voice"
        }
        tts = _build_tts(self.settings, agent_data)
        self.assertEqual(tts._opts.model, "eleven_turbo_v2_5")
        self.assertEqual(tts._opts.voice_id, "voice_alpha_123")

    def test_03_elevenlabs_switching(self):
        """Test B: provider=elevenlabs switched to Model B and Voice B."""
        agent_data = {
            "tts_provider": "elevenlabs",
            "tts_model": "eleven_flash_v2_5",
            "tts_voice_id": "voice_beta_456",
            "tts_voice_name": "Beta Voice"
        }
        tts = _build_tts(self.settings, agent_data)
        self.assertEqual(tts._opts.model, "eleven_flash_v2_5")
        self.assertEqual(tts._opts.voice_id, "voice_beta_456")

    def test_04_cartesia_resolves_db_model_and_voice(self):
        """Test C: provider=cartesia with Model C and Voice C."""
        agent_data = {
            "tts_provider": "cartesia",
            "tts_model": "sonic-3",
            "tts_voice_id": "cartesia_voice_gamma_789",
            "tts_voice_name": "Gamma Voice"
        }
        tts = _build_tts(self.settings, agent_data)
        self.assertEqual(tts._opts.model, "sonic-3")
        self.assertEqual(tts._opts.voice, "cartesia_voice_gamma_789")

    def test_05_cartesia_switching(self):
        """Test D: provider=cartesia switched to Model D and Voice D."""
        agent_data = {
            "tts_provider": "cartesia",
            "tts_model": "sonic-preview",
            "tts_voice_id": "cartesia_voice_delta_999",
            "tts_voice_name": "Delta Voice"
        }
        tts = _build_tts(self.settings, agent_data)
        self.assertEqual(tts._opts.model, "sonic-preview")
        self.assertEqual(tts._opts.voice, "cartesia_voice_delta_999")

    def test_06_env_variables_are_not_read_or_used(self):
        """Verify that .env model/voice variables have zero effect on TTS construction."""
        agent_data = {
            "tts_provider": "elevenlabs",
            "tts_model": "eleven_multilingual_v2",
            "tts_voice_id": "db_voice_exact",
            "tts_voice_name": "Exact Voice"
        }
        with patch.dict(os.environ, {
            "ELEVENLABS_TTS_MODEL": "should_be_ignored",
            "ELEVENLABS_TTS_VOICE_ID": "should_be_ignored",
            "CARTESIA_T5_MODEL": "should_be_ignored",
            "TTS_PROVIDER": "cartesia"
        }):
            tts = _build_tts(self.settings, agent_data)
            self.assertEqual(tts._opts.model, "eleven_multilingual_v2")
            self.assertEqual(tts._opts.voice_id, "db_voice_exact")

    def test_07_missing_provider_fails_explicitly(self):
        """Verify that an agent with no TTS provider raises an explicit ValueError."""
        agent_data = {
            "tts_provider": None,
            "tts_model": "eleven_multilingual_v2",
            "tts_voice_id": "v123"
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("TTS provider is not configured", str(ctx.exception))

    def test_08_unsupported_provider_fails_explicitly(self):
        """Verify that an unsupported provider raises an explicit ValueError."""
        agent_data = {
            "tts_provider": "openai_tts",
            "tts_model": "tts-1",
            "tts_voice_id": "alloy"
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("Unsupported TTS provider", str(ctx.exception))

    def test_09_elevenlabs_missing_model_fails_explicitly(self):
        """Verify that ElevenLabs with missing model raises an explicit error."""
        agent_data = {
            "tts_provider": "elevenlabs",
            "tts_model": None,
            "tts_voice_id": "voice_123"
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("ElevenLabs TTS model is not configured", str(ctx.exception))

    def test_10_elevenlabs_missing_voice_fails_explicitly(self):
        """Verify that ElevenLabs with missing voice raises an explicit error."""
        agent_data = {
            "tts_provider": "elevenlabs",
            "tts_model": "eleven_multilingual_v2",
            "tts_voice_id": ""
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("ElevenLabs TTS voice_id is not configured", str(ctx.exception))

    def test_11_cartesia_missing_model_fails_explicitly(self):
        """Verify that Cartesia with missing model raises an explicit error."""
        agent_data = {
            "tts_provider": "cartesia",
            "tts_model": None,
            "tts_voice_id": "cartesia_voice_123"
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("Cartesia TTS model is not configured", str(ctx.exception))

    def test_12_cartesia_missing_voice_fails_explicitly(self):
        """Verify that Cartesia with missing voice raises an explicit error."""
        agent_data = {
            "tts_provider": "cartesia",
            "tts_model": "sonic-3",
            "tts_voice_id": None
        }
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, agent_data)
        self.assertIn("Cartesia TTS voice_id is not configured", str(ctx.exception))

    def test_13_missing_agent_data_fails_explicitly(self):
        """Verify that completely missing agent_data raises an explicit error."""
        with self.assertRaises(ValueError) as ctx:
            _build_tts(self.settings, None)
        self.assertIn("Agent configuration is missing or invalid", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
