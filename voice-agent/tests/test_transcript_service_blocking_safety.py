import io, os, sys, threading, unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

import transcript_service as tsmod
from transcript_service import TranscriptService

MAIN_IDENT = threading.main_thread().ident


class _FakeS3:
    """Real-shaped fakes: record the thread each blocking boto3 call would run on."""

    def __init__(self):
        self.put_thr = None
        self.get_thr = None
        self.read_thr = None
        self.raise_put = None
        self.raise_get = None
        self.raise_read = None
        self.stored = {"session_id": "sess-1", "room_name": "room-1", "participant_id": "p1", "message": "hello"}
        self.put_calls = 0

    def put_object(self, **kwargs):
        self.put_calls += 1
        self.put_thr = threading.current_thread().ident
        if self.raise_put is not None:
            raise self.raise_put
        return {}

    def get_object(self, **kwargs):
        self.get_thr = threading.current_thread().ident
        if self.raise_get is not None:
            raise self.raise_get
        return {"Body": self}

    def read(self, *a, **k):
        self.read_thr = threading.current_thread().ident
        if self.raise_read is not None:
            raise self.raise_read
        import json
        return json.dumps(self.stored).encode("utf-8")


class _StubSettings:
    s3_bucket_name = "test-transcript-bucket"
    s3_region = "us-east-1"
    s3_access_key_id = "test"
    s3_secret_access_key = "test"
    aws_region = "us-east-1"
    aws_access_key_id = "test"
    aws_secret_access_key = "test"
    s3_bucket_key_prefix = "transcripts"
    s3_endpoint_url = None


def _make_service(fake):
    svc = TranscriptService()
    svc.settings = _StubSettings()
    svc._get_s3_client = MagicMock(return_value=fake)
    return svc


class TestTranscriptServiceBlockingSafety(IsolatedAsyncioTestCase):
    """
    P1-15: transcript upload/retrieval must keep blocking boto3 OFF the async
    event loop (thread-ident != runner loop thread), and S3 failures must be
    OBSERVABLE as False/None -- never fake success, never fabricated data.
    """

    async def test_1_put_object_runs_in_worker_thread_not_on_event_loop(self):
        fake = _FakeS3()
        svc = _make_service(fake)
        loop_ident = threading.current_thread().ident
        ok = await svc.save_transcript_to_s3(
            "sess-1",
            {"session_id": "sess-1", "room_name": "room-1", "participant_id": "p1", "message": "hello"},
        )
        self.assertTrue(ok)
        self.assertIsNotNone(fake.put_thr, "put_object must have been invoked via to_thread")
        self.assertNotEqual(
            fake.put_thr, loop_ident,
            "P1-15 regression: blocking boto3 put_object ran directly on the event loop",
        )

    async def test_2_get_object_and_body_read_run_in_worker_thread(self):
        fake = _FakeS3()
        svc = _make_service(fake)
        loop_ident = threading.current_thread().ident
        data = await svc.get_transcript_from_s3("sess-1", date="20260101")
        self.assertIsNotNone(data)
        self.assertEqual(data["session_id"], "sess-1")
        self.assertIsNotNone(fake.get_thr)
        self.assertIsNotNone(fake.read_thr)
        self.assertNotEqual(fake.get_thr, loop_ident, "get_object ran on the event loop")
        self.assertNotEqual(fake.read_thr, loop_ident, "Body.read ran on the event loop")

    async def test_3_save_failure_observable_returns_false_not_fake_ok(self):
        from botocore.exceptions import ClientError
        fake = _FakeS3()
        fake.raise_put = ClientError({"Error": {"Code": "SlowDown", "Message": "s3 down"}}, "put_object")
        svc = _make_service(fake)
        result = await svc.save_transcript_to_s3(
            "sess-1",
            {"session_id": "sess-1", "room_name": "room-1", "participant_id": "p1", "message": "hello"},
        )
        self.assertIs(result, False, "S3 failure must be observable as False, never faked True")

    async def test_4_retrieval_failure_returns_none_never_fabricates(self):
        from botocore.exceptions import ClientError
        fake = _FakeS3()
        fake.raise_get = ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "get_object")
        svc = _make_service(fake)
        out = await svc.get_transcript_from_s3("does-not-exist", date="20260101")
        self.assertIsNone(out, "missing transcript must be None, never fabricated dict")

    async def test_5_retry_after_failure_recovers_and_saves_exactly_once_more(self):
        from botocore.exceptions import ClientError
        fake = _FakeS3()
        svc = _make_service(fake)
        payload = {"session_id": "sess-1", "room_name": "room-1", "participant_id": "p1", "message": "hello"}
        fake.raise_put = ClientError({"Error": {"Code": "ConnectionError", "Message": "boom"}}, "put_object")
        first = await svc.save_transcript_to_s3("sess-1", payload)
        self.assertIs(first, False)
        fake.raise_put = None
        second = await svc.save_transcript_to_s3("sess-1", payload)
        self.assertTrue(second)
        self.assertEqual(fake.put_calls, 2, "exactly two uploads: one failed + one retried, no duplication on success")

    async def test_6_saved_transcript_not_marked_success_on_failure(self):
        from botocore.exceptions import ClientError
        fake = _FakeS3()
        fake.raise_put = ClientError({"Error": {"Code": "SlowDown", "Message": "s3 down"}}, "put_object")
        svc = _make_service(fake)
        await svc.save_transcript_to_s3(
            "sess-fail",
            {"session_id": "sess-fail", "room_name": "room-1", "participant_id": "p1", "message": "hello"},
        )
        saved = svc.sessions.get("sess-fail", {})
        self.assertNotIn("s3_url", saved, "failed save must NOT fabricate a success s3_url marker")


if __name__ == "__main__":
    unittest.main()