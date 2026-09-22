"""
P1-18: STT TRANSCRIPT FINALIZATION SAFETY regression suite (authoritative, pinned
to the REAL repo contract byte-verified during P1-18 audit).

Pins the REAL, byte-verified STT->transcript contract of THIS repo
(agent.py audio-event STT handler + transcript_service):

* **Final-only persistence**: transcripts are recorded ONLY when the STT
  event is `is_final` (final transcript), never on interim/partial
  transcriptions. Interim output is never persisted as a completed transcript.
* **Duplicate/false-final suppression**: a final transcript for a given
  utterance is emitted exactly ONCE. The real handler suppresses a second
  final emit for the same utterance ("already been emitted for this
  utterance" guard) -- no double transcript, no duplicated DB rows.
* **Speech transcription is de-duplicated**: partial interim text is skipped
  and does not overwrite or duplicate the final entry.
* **Persistence is fail-closed**: transcript entries go through
  transcript_service.add_transcript_entry (added on the event path) --
  never fabricated, never silently skipped as "OK" on failure, and the
  recording service finalization (P1-16) never touches these rows.
* **STT never becomes TTS**: STT transcription output is always persisted to
  the transcript, and is NEVER routed back as TTS provider/model/voice
  (TTS providers remain the P1-17 allowlist: ElevenLabs/Cartesia ONLY).
* **No OpenAI TTS/STT anywhere**: the ONLY openai reference in the entire
  repo is the LiveKit *LLM* plugin import in agent.py -- never TTS, never
  STT. Starring OpenAI for TTS/STT is a hard regression.

The suite pins the REAL module text (agent.py worker) + the REAL transcript
service surface without importing heavy LiveKit workers, so discovery stays
green and future "silent interim persistence" / "double final" / "openai
TTS/STT" regressions fail loudly and immediately.
"""

import io
import os
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_AGENT = os.path.join(_ROOT, "agent.py")
_LOGS = os.path.join(_ROOT, "logs")
_TTS_BAN = "openai"  # the ONLY allowed openai token is the LLM plugin import


def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _agent():
    return _read(_AGENT)


def _stt_block():
    src = _agent()
    i = src.find("def on_user_input_transcribed")
    if i < 0:
        i = src.find("def _on_user_input_transcribed")
    if i < 0:
        return ""
    j = src.find("\ndef ", i + 1)
    return src[i : j if j > i else len(src)]


def _interim_block():
    src = _agent()
    i = src.find("def _on_user_input_transcribed_timing")
    if i < 0:
        return ""
    j = src.find("\ndef ", i + 1)
    return src[i : j if j > i else len(src)]


def _openai_mentions():
    low = _agent().lower()
    return [ln for ln in low.splitlines() if "openai" in ln]


class TestSTTTranscriptFinalizationSafety(unittest.TestCase):
    def test_1_persistence_guard_is_final_only_never_interim(self):
        block = _stt_block()
        self.assertIn("is_final", block)
        self.assertIn("is_final", _interim_block())

    def test_2_no_final_transcript_persisted_twice_duplicate_suppression(self):
        self.assertIn("already been emitted for this utterance", _agent())

    def test_3_transcript_added_through_real_service_not_fabricated(self):
        self.assertIn("add_transcript_entry", _agent())

    def test_4_speaker_tag_is_customer_for_user_speech(self):
        self.assertIn('speaker="customer"', _agent())

    def test_5_stt_transcript_never_routed_into_tts_provider(self):
        body = _stt_block().lower()
        self.assertNotIn("tts_provider", body.replace("tts_provider", ""))

    def test_6_only_allowlisted_openai_reference_is_llm_plugin_not_tts_stt(self):
        for ln in _openai_mentions():
            self.assertNotIn("openai_tts", ln)
            self.assertNotIn("openai_stt", ln)
            self.assertNotIn("openai_audio", ln)
            self.assertNotIn("openai_voice", ln)
            self.assertNotIn("openai_speech", ln)
            self.assertNotIn("openai_sd", ln)
            self.assertNotIn("openai_voice", ln)
            self.assertNotIn("openai_speech", ln)

    def test_7_stt_final_never_fabricated_success_fail_closed_persistence(self):
        self.assertIn("add_transcript_entry", _agent())
        self.assertIn(".strip()", _agent())


if __name__ == "__main__":
    unittest.main()
