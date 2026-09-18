"""
Unit tests for call persistence lifecycle, bounded registration, JSON serialization, S3 verification, and idempotency.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, date, timezone, timedelta
from uuid import UUID, uuid4
from enum import Enum
import asyncio
import json


class SampleEnum(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class TestCallPersistence(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.backend_url = "http://localhost:8000/api/v1"
        self.mock_settings.enable_transcripts = True
        self.mock_settings.enable_recording = True
        self.mock_settings.aws_access_key_id = "test_key"
        self.mock_settings.aws_secret_access_key = "test_secret"
        self.mock_settings.aws_region = "us-east-1"
        self.mock_settings.s3_bucket_name = "test-bucket"

    def _create_mock_agent(self, call_started=True, room_name="test-room-123"):
        from agent import VoiceAgent
        agent = MagicMock(spec=VoiceAgent)
        agent.settings = self.mock_settings
        agent.room_name = room_name
        agent.participant_id = "+1234567890"
        agent.agent_name = "Support Agent"
        agent.agent_id = UUID("907f4d4a-5d34-41b3-82f1-5aebdf9db582")
        agent.client_id = UUID("c18360db-7ec5-48d2-9a34-d2fe9502a985")
        agent.transcript_session_id = "tx-session-123"
        agent.captured_caller_name = "Alice"
        agent.egress_id = "EG_12345"
        agent.recording_filename = "test-room-123_rec.mp4"
        agent._recording_task = None
        agent._cleanup_lock = asyncio.Lock()
        agent._cleanup_completed = False
        agent._cleanup_in_progress = False
        agent._call_registered = False
        agent._call_registering = False
        agent.session_manager = MagicMock()
        agent.session = MagicMock()
        
        if call_started:
            agent.call_start = datetime.now(timezone.utc) - timedelta(seconds=45)
        else:
            agent.call_start = None

        return agent

    # -------------------------------------------------------------------------
    # JSON SAFE SERIALIZATION TESTS (1-6)
    # -------------------------------------------------------------------------

    def test_1_uuid_agent_id_serializes_to_string(self):
        """Test 1: UUID agentId serializes to string."""
        from agent import make_json_safe
        agent_uuid = UUID("907f4d4a-5d34-41b3-82f1-5aebdf9db582")
        payload = {"agentId": agent_uuid}
        safe = make_json_safe(payload)
        self.assertIsInstance(safe["agentId"], str)
        self.assertEqual(safe["agentId"], "907f4d4a-5d34-41b3-82f1-5aebdf9db582")
        json.dumps(safe)  # Must not raise

    def test_2_uuid_client_id_serializes_to_string(self):
        """Test 2: UUID clientId serializes to string."""
        from agent import make_json_safe
        client_uuid = UUID("c18360db-7ec5-48d2-9a34-d2fe9502a985")
        payload = {"clientId": client_uuid}
        safe = make_json_safe(payload)
        self.assertIsInstance(safe["clientId"], str)
        self.assertEqual(safe["clientId"], "c18360db-7ec5-48d2-9a34-d2fe9502a985")
        json.dumps(safe)

    def test_3_nested_uuid_serializes_correctly(self):
        """Test 3: Nested UUID inside list and dictionary serializes correctly."""
        from agent import make_json_safe
        u1 = uuid4()
        u2 = uuid4()
        payload = {
            "metadata": {
                "ids": [u1, u2],
                "details": {"primary_id": u1}
            }
        }
        safe = make_json_safe(payload)
        self.assertEqual(safe["metadata"]["ids"], [str(u1), str(u2)])
        self.assertEqual(safe["metadata"]["details"]["primary_id"], str(u1))
        json.dumps(safe)

    def test_4_datetime_payload_remains_json_serializable(self):
        """Test 4: datetime and date payloads are converted to ISO strings."""
        from agent import make_json_safe
        now = datetime(2026, 9, 19, 0, 30, 0, tzinfo=timezone.utc)
        d = date(2026, 9, 19)
        payload = {
            "created_at": now,
            "call_date": d,
            "enum_val": SampleEnum.RESOLVED
        }
        safe = make_json_safe(payload)
        self.assertEqual(safe["created_at"], "2026-09-19T00:30:00+00:00")
        self.assertEqual(safe["call_date"], "2026-09-19")
        self.assertEqual(safe["enum_val"], "resolved")
        json.dumps(safe)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_5_httpx_receives_json_safe_payload(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 5: httpx POST receives JSON-safe payload containing string IDs."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True)
        # Give agent native UUID objects for agent_id and client_id
        agent.agent_id = UUID("907f4d4a-5d34-41b3-82f1-5aebdf9db582")
        agent.client_id = UUID("c18360db-7ec5-48d2-9a34-d2fe9502a985")

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "OK", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=20)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        self.assertTrue(agent._call_registered)
        call_args = mock_http_client.post.call_args
        sent_json = call_args[1]["json"]
        self.assertIsInstance(sent_json["agentId"], str)
        self.assertIsInstance(sent_json["clientId"], str)
        # json.dumps must succeed without TypeError
        json.dumps(sent_json)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_6_urllib_fallback_receives_json_safe_payload(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 6: urllib fallback also receives and serializes JSON-safe payload without UUID error."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True)
        agent.agent_id = UUID("907f4d4a-5d34-41b3-82f1-5aebdf9db582")
        agent.client_id = UUID("c18360db-7ec5-48d2-9a34-d2fe9502a985")

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "OK", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        # Make httpx raise RuntimeError to trigger urllib fallback
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=RuntimeError("Event loop shutting down"))
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 201
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            start_time = datetime.now(timezone.utc) - timedelta(seconds=15)
            end_time = datetime.now(timezone.utc)
            await register_call_with_backend(agent, start_time, end_time)

            self.assertTrue(agent._call_registered)
            mock_urlopen.assert_called_once()
            req = mock_urlopen.call_args[0][0]
            # Ensure the request body was successfully decoded from json bytes
            body_dict = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body_dict["agentId"], "907f4d4a-5d34-41b3-82f1-5aebdf9db582")
            self.assertEqual(body_dict["clientId"], "c18360db-7ec5-48d2-9a34-d2fe9502a985")

    # -------------------------------------------------------------------------
    # IDEMPOTENT CLEANUP & RECORDING TESTS (7-10)
    # -------------------------------------------------------------------------

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_7_duplicate_cleanup_stops_recording_only_once(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 7: Duplicate on_exit/cleanup stops recording only once."""
        from agent import VoiceAgent

        agent = self._create_mock_agent(call_started=True)
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Done", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        # Call on_exit twice
        await VoiceAgent.on_exit(agent)
        await VoiceAgent.on_exit(agent)

        # stop_recording must be called exactly once
        self.assertEqual(mock_rec_service.stop_recording.await_count, 1)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_8_duplicate_cleanup_saves_transcript_only_once(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 8: Duplicate on_exit/cleanup saves transcript to S3 only once."""
        from agent import VoiceAgent

        agent = self._create_mock_agent(call_started=True)
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Done", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        await VoiceAgent.on_exit(agent)
        await VoiceAgent.on_exit(agent)

        self.assertEqual(mock_tx_service.save_transcript_to_s3.await_count, 1)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_9_duplicate_cleanup_persists_only_once(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 9: Duplicate on_exit/cleanup triggers /conversations/register POST only once."""
        from agent import VoiceAgent

        agent = self._create_mock_agent(call_started=True)
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Done", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        await VoiceAgent.on_exit(agent)
        await VoiceAgent.on_exit(agent)

        self.assertEqual(mock_http_client.post.await_count, 1)

    async def test_10_already_complete_egress_is_treated_as_finalized(self):
        """Test 10: LiveKit 412 / EGRESS_COMPLETE error during stop_recording returns True (finalized)."""
        from recording_service import RecordingService

        rec_srv = RecordingService()
        rec_srv.settings = self.mock_settings

        with patch.object(rec_srv, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.egress.stop_egress = AsyncMock(
                side_effect=Exception("status=412, EGRESS_COMPLETE cannot be stopped")
            )
            mock_client.aclose = AsyncMock()
            mock_get_client.return_value = mock_client

            result = await rec_srv.stop_recording("EG_ALREADY_DONE_123")
            self.assertTrue(result)

    # -------------------------------------------------------------------------
    # S3 VERIFICATION RETRY & BACKOFF TESTS (11-12)
    # -------------------------------------------------------------------------

    async def test_11_temporary_s3_verification_failure_retries(self):
        """Test 11: Initial S3 HeadObject failure (403/404) retries before giving up."""
        from recording_service import RecordingService

        rec_srv = RecordingService()
        rec_srv.settings = self.mock_settings

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            # Attempt 1 and 2 fail, attempt 3 fails
            mock_s3.head_object.side_effect = [
                Exception("403 Forbidden"),
                Exception("403 Forbidden"),
                Exception("403 Forbidden")
            ]
            mock_boto.return_value = mock_s3

            # Set max_retries=3, retry_delay=0.01 for fast unit testing
            result = await rec_srv.verify_s3_upload("recordings/test.mp4", max_retries=3, retry_delay=0.01)
            self.assertFalse(result)
            self.assertEqual(mock_s3.head_object.call_count, 3)

    async def test_12_later_s3_verification_success_is_accepted(self):
        """Test 12: Initial S3 HeadObject 403 followed by subsequent success is accepted."""
        from recording_service import RecordingService

        rec_srv = RecordingService()
        rec_srv.settings = self.mock_settings

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            # Attempt 1 fails (403), Attempt 2 succeeds
            mock_s3.head_object.side_effect = [
                Exception("403 Forbidden"),
                {"ContentLength": 54321}
            ]
            mock_boto.return_value = mock_s3

            result = await rec_srv.verify_s3_upload("recordings/test.mp4", max_retries=3, retry_delay=0.01)
            self.assertTrue(result)
            self.assertEqual(mock_s3.head_object.call_count, 2)

    # -------------------------------------------------------------------------
    # INBOUND, OUTBOUND, & RECORDING RECORD ROW TESTS (13-15)
    # -------------------------------------------------------------------------

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_13_one_inbound_call_creates_one_conversation(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 13: One inbound call produces exactly one conversation registration."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True, room_name="inbound-room-101")
        agent.participant_id = "sip:+19876543210"

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Inbound call", "sentiment": "positive", "sentimentScore": 0.6,
            "intent": "support", "leadScore": 70, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=50)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        self.assertTrue(agent._call_registered)
        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["customerContact"], "sip:+19876543210")
        self.assertEqual(payload["duration"], 50)
        self.assertEqual(mock_http_client.post.await_count, 1)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_14_one_outbound_call_creates_one_conversation(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 14: One outbound call produces exactly one conversation registration."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True, room_name="outbound-room-202")
        agent.participant_id = "+919381408134"

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Outbound call", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "sales", "leadScore": 80, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=75)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        self.assertTrue(agent._call_registered)
        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["customerContact"], "+919381408134")
        self.assertEqual(payload["duration"], 75)
        self.assertEqual(mock_http_client.post.await_count, 1)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_15_one_real_call_creates_one_recording_payload(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 15: Recording payload structure is preserved with filename, duration, size, s3_key."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True)
        agent.recording_filename = "rec_call_2026.mp4"
        agent.egress_id = "EG_RECORDING_15"

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Completed", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=40)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        rec = payload["recording"]
        self.assertIsNotNone(rec)
        self.assertEqual(rec["filename"], "rec_call_2026.mp4")
        self.assertEqual(rec["duration"], 40)
        self.assertEqual(rec["s3_key"], "recordings/rec_call_2026.mp4")
        self.assertIn("size", rec)


if __name__ == "__main__":
    unittest.main()
