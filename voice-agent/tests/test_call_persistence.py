"""
Unit tests for call persistence lifecycle, bounded registration, and idempotency in agent.py.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
import asyncio
import json


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
        agent.agent_id = "907f4d4a-5d34-41b3-82f1-5aebdf9db582"
        agent.client_id = "c18360db-7ec5-48d2-9a34-d2fe9502a985"
        agent.transcript_session_id = "tx-session-123"
        agent.captured_caller_name = "Alice"
        agent.egress_id = "EG_12345"
        agent.recording_filename = "test-room-123_rec.mp4"
        agent._recording_task = None
        agent._call_registered = False
        agent._call_registering = False
        agent.session_manager = MagicMock()
        agent.session = MagicMock()
        
        if call_started:
            agent.call_start = datetime.now(timezone.utc) - timedelta(seconds=45)
        else:
            agent.call_start = None

        return agent

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_register_coroutine_awaited_before_teardown_completes(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 1: Verify register_call_with_backend is awaited before on_exit / teardown finishes."""
        from agent import VoiceAgent, register_call_with_backend

        agent = self._create_mock_agent(call_started=True)
        mock_tx_service.finalize_transcript.return_value = {
            "lines": [{"speaker": "agent", "text": "Hello"}, {"speaker": "customer", "text": "Hi"}],
            "full_text": "Hello Hi"
        }
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Test summary",
            "sentiment": "positive",
            "sentimentScore": 0.8,
            "intent": "support",
            "leadScore": 75,
            "actionItems": ["Follow up"]
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        # Call on_exit directly
        await VoiceAgent.on_exit(agent)

        # Verify registration was completed before on_exit finished
        self.assertTrue(agent._call_registered)
        mock_http_client.post.assert_awaited_once()
        agent.session_manager.clear_all_sessions.assert_called_once()

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_simulated_process_cleanup_does_not_cancel_persistence(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 2: Verify cleanup_on_disconnect executes and awaits registration cleanly."""
        from agent import cleanup_on_disconnect, VoiceAgent

        agent = self._create_mock_agent(call_started=True)
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
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

        mock_session = AsyncMock()
        # session.aclose simulates invoking agent.on_exit()
        async def mock_aclose():
            await VoiceAgent.on_exit(agent)
        mock_session.aclose = AsyncMock(side_effect=mock_aclose)

        mock_sm = MagicMock()
        await cleanup_on_disconnect(mock_session, mock_sm, agent=agent)

        self.assertTrue(agent._call_registered)
        mock_http_client.post.assert_awaited_once()

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_inbound_creates_one_conversation_record(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 3: Inbound call creates exactly one registration payload and conversation."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True, room_name="inbound-room-999")
        agent.participant_id = "sip:+19876543210"
        
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Inbound inquiry", "sentiment": "positive", "sentimentScore": 0.5,
            "intent": "inquiry", "leadScore": 60, "actionItems": ["Send brochure"]
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        self.assertTrue(agent._call_registered)
        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["customerContact"], "sip:+19876543210")
        self.assertEqual(payload["duration"], 60)
        self.assertEqual(payload["agentName"], "Support Agent")

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_outbound_creates_one_conversation_record(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 4: Outbound call creates exactly one registration payload and conversation."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True, room_name="outbound-room-888")
        agent.participant_id = "+919381408134"
        
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Outbound sales call", "sentiment": "positive", "sentimentScore": 0.7,
            "intent": "sales", "leadScore": 85, "actionItems": ["Send contract"]
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        self.assertTrue(agent._call_registered)
        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["customerContact"], "+919381408134")
        self.assertEqual(payload["duration"], 120)
        self.assertEqual(payload["agentId"], "907f4d4a-5d34-41b3-82f1-5aebdf9db582")

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_recording_payload_persisted(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 5: Verify recording payload preserves filename, duration, size, and s3_key."""
        from agent import register_call_with_backend

        agent = self._create_mock_agent(call_started=True)
        agent.recording_filename = "rec_2026_room.mp4"
        agent.egress_id = "EG_RECORDS_99"

        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)
        mock_analyze.return_value = {
            "summary": "Call done", "sentiment": "neutral", "sentimentScore": 0.0,
            "intent": "general", "leadScore": 50, "actionItems": []
        }

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_post_resp)
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        start_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)

        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        rec = payload["recording"]
        self.assertIsNotNone(rec)
        self.assertEqual(rec["filename"], "rec_2026_room.mp4")
        self.assertEqual(rec["duration"], 30)
        self.assertEqual(rec["s3_key"], "recordings/rec_2026_room.mp4")
        self.assertIn("size", rec)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_duplicate_cleanup_does_not_create_duplicate_records(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 6: Multiple invocations of registration or on_exit are idempotent and do not duplicate."""
        from agent import register_call_with_backend, VoiceAgent

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

        # First exit / registration
        await VoiceAgent.on_exit(agent)
        self.assertTrue(agent._call_registered)
        self.assertEqual(mock_http_client.post.await_count, 1)

        # Second redundant exit call
        await VoiceAgent.on_exit(agent)
        # Should still be exactly 1 POST call
        self.assertEqual(mock_http_client.post.await_count, 1)

        # Direct redundant call to register_call_with_backend
        start_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        end_time = datetime.now(timezone.utc)
        await register_call_with_backend(agent, start_time, end_time)
        self.assertEqual(mock_http_client.post.await_count, 1)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_failed_pre_participant_outbound_room_creates_no_row(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 7: If call_start was never set (e.g. participant never connected), no registration is made."""
        from agent import VoiceAgent, register_call_with_backend

        agent = self._create_mock_agent(call_started=False)
        mock_tx_service.finalize_transcript.return_value = {"lines": [], "full_text": ""}
        mock_tx_service.save_transcript_to_s3 = AsyncMock(return_value=True)
        mock_rec_service.stop_recording = AsyncMock(return_value=True)
        mock_rec_service.verify_s3_upload = AsyncMock(return_value=False)

        mock_http_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        # on_exit with no call_start
        await VoiceAgent.on_exit(agent)
        mock_http_client.post.assert_not_called()
        self.assertFalse(agent._call_registered)

        # register_call_with_backend with None started_at
        await register_call_with_backend(agent, None, datetime.now(timezone.utc))
        mock_http_client.post.assert_not_called()
        self.assertFalse(agent._call_registered)

    @patch("agent.analyze_transcript_with_llm")
    @patch("agent.transcript_service")
    @patch("recording_service.recording_service")
    @patch("httpx.AsyncClient")
    async def test_backend_timeout_does_not_hang_shutdown(
        self, mock_httpx_cls, mock_rec_service, mock_tx_service, mock_analyze
    ):
        """Test 8: Explicit timeout prevents hanging if backend is slow or unresponsive."""
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

        # Mock hanging backend call with timeout
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=asyncio.TimeoutError("Backend timed out"))
        mock_httpx_cls.return_value.__aenter__.return_value = mock_http_client

        t0 = datetime.now()
        await VoiceAgent.on_exit(agent)
        elapsed = (datetime.now() - t0).total_seconds()

        # Should complete quickly without hanging
        self.assertLess(elapsed, 5.0)
        agent.session_manager.clear_all_sessions.assert_called_once()


if __name__ == "__main__":
    unittest.main()
