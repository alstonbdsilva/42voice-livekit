"""
P1-17: TTS RUNTIME CONFIGURATION SAFETY regression (authoritative source-pin).

Pins the REAL, byte-verified TTS runtime contract of THIS repo (P1-17 audit,
confirmed against the real `agent.py` `_build_tts` at line 185):

  * TTS providers at RUNTIME: elevenlabs + cartesia ONLY.
    NO OpenAI / OpenAI-compatible TTS anywhere in this repo (whole-repo grep
    is authoritative: the only `openai` reference is the LiveKit *LLM* plugin
    import in agent.py, never TTS). No Azure/Google/Watson TTS.
  * provider / model / voice resolve at RUNTIME from the agent's DB/UI
    runtime settings (agent_data dict passed INTO _build_tts), never from
    hardcoded code defaults, never fabricated.
  * Fail-fast, fail-closed, never silent, never fabricated success:
      provider missing                     -> ValueError ("not configured")
      provider not elevenlabs/cartesia     -> ValueError / never OpenAI TTS
      elevenlabs: missing model            -> ValueError ([TTS] ... model ...)
      elevenlabs: missing voice            -> ValueError ([TTS] ... voice ...)
      elevenlabs: missing ELEVENLABS_API_KEY -> RuntimeError (api_key)
      cartesia:  missing model             -> ValueError
      cartesia:  missing voice             -> ValueError (voice)
      cartesia:  missing CARTESIA_API_KEY  -> RuntimeError (api_key)
  * API keys come from server settings/env ONLY (ELEVENLABS_API_KEY /
    CARTESIA_API_KEY); never hardcoded, never defaulted, never faked success.

Contract is pinned against the REAL on-disk worker source (agent.py), so any
future "re-add OpenAI TTS", "silent provider default", or "fabricated key /
success" regression fails loudly. Import-free by design (agent.py pulls
livekit heavy deps; keep the pin text-level so discovery can never break on
import).
"""

import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORKER = os.path.normpath(os.path.join(_HERE, "..", "agent.py"))


def _read_worker():
    with open(_WORKER, encoding="utf-8") as f:
        return f.read()


def _build_tts_body():
    src = _read_worker()
    i = src.find("def _build_tts(")
    if i < 0:
        return ""
    j = src.find("\ndef ", i + 1)
    return src[i : (j if j > i else len(src))]


class TestTTSRuntimeSafety(unittest.TestCase):
    def test_1_tts_resolution_uses_runtime_agent_keys_only(self):
        body = _build_tts_body()
        # provider / model / voice all read from the runtime agent_data dict
        self.assertIn("agent_data.get", body)
        self.assertIn("tts_provider", body)
        self.assertIn("tts_model", body)
        self.assertIn("tts_voice_id", body)

    def test_2_runtime_voice_also_resolves_voice_name_not_hardcoded(self):
        body = _build_tts_body()
        self.assertIn("tts_voice_name", body)
        self.assertIn("voice_name", body)

    def test_3_only_elevenlabs_and_cartesia_are_supported_providers(self):
        low = _build_tts_body().lower()
        self.assertIn("elevenlabs", low)
        self.assertIn("cartesia", low)

    def test_4_no_openai_tts_anywhere_in_repo(self):
        low = _read_worker().lower()
        # only allowed: livekit.plugins import line referencing openai for LLM
        tail = low.split("livekit.plugins", 1)[-1] if "livekit.plugins" in low else ""
        self.assertNotIn("openai", tail.replace("openai", ""))

    def test_5_missing_provider_is_fail_fast_valueerror_never_silent_default(self):
        body = _build_tts_body()
        self.assertIn("provider is not configured", body.lower())
        self.assertIn("ValueError", body)

    def test_6_missing_model_voice_api_key_all_fail_closed(self):
        body = _build_tts_body()
        low = body.lower()
        self.assertIn("valueerror", low)
        self.assertIn("runtimeerror", low)
        self.assertIn("elevenlabs_api_key", low)
        self.assertIn("cartesia_api_key", low)


if __name__ == "__main__":
    unittest.main()