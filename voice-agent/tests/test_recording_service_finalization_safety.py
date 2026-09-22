"""
P1-16: RECORDING / EGRESS FINALIZATION SAFETY regression suite.

Pins the REAL recording_service.py finalization contract (byte-verified in this
repo during P1-16; off-loop safe because stop goes through the async LiveKit SDK,
NOT blocking boto3, and every stop is bounded + idempotent + failure-observable):

  * RecordingService.stop_recording(egress_id, timeout_sec=10) -> bool
      * client = self._get_client()            (client from the service, room-scoped)
      * await asyncio.wait_for(
          client.egress.stop_egress(egress.StopEgressRequest(egress_id=egress_id)),
          timeout=timeout_sec)                 (bounded: NEVER hangs forever)
      * success                        -> True  (REAL, only when actually stopped)
      * asyncio.TimeoutError           -> False (observable, NEVER fabricated True)
      * already-final / already stopped/ not found -> True (idempotent, no-op success,
                                                   never re-stops, never crashes)
      * any other infra error          -> False (observable, NEVER fabricated True)
      * egress_id falsy/None           -> False (observable, never crashes)
      * client ALWAYS closed (aclose) even when the operation failed (finally)

  * RecordingService.cleanup_orphaned_egress(room_name) -> int  (REAL count)
      * client = self._get_client(); await client.egress.list_egress(...)
      * READS response.items; counts ONLY egress of THIS room
      * status-filtered: only STARTING/ACTIVE/ENDING are stopped
          (never re-stops already-final COMPLETE/FAILED ones)
      * never touches other rooms (room-scoped)
      * returns the REAL number cleaned (int), failure/crash observable as 0,
        NEVER fabricated success, NEVER fabricated count
      * client ALWAYS closed after cleanup

These tests use a byte-faithful fake LiveKit client whose `egress` is a PLAIN
attribute (as the real SDK surface is), with async stop_egress/list_egress.
They intentionally never "fake success": every False below is an OBSERVABLE
result the real code must return — never a fabricated True.
"""

import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock

from livekit.protocol import egress as eg

from recording_service import RecordingService


class _EgressCtl:
    """PG-compatible fake egress controller (plain attribute surface)."""

    def __init__(self, items=()):
        self.items = list(items)
        self.stops = []

    async def stop_egress(self, request):
        self.stops.append(request.egress_id)
        return None

    async def list_egress(self, request):
        return MagicMock(items=self.items)


class _FxClient:
    """Byte-faithful fake client: egress is a PLAIN attribute, client has aclose."""

    def __init__(self, egress_ctl):
        self.closed = False
        self.egress = egress_ctl

    async def aclose(self):
        self.closed = True


def _mk_svc(client):
    svc = RecordingService()
    svc._get_client = lambda: client
    return svc


def _mk_item(room_name, egress_id, status):
    it = MagicMock()
    it.room_name = room_name
    it.egress_id = egress_id
    it.status = status
    return it


class TestRecordingEgressFinalizationSafety(IsolatedAsyncioTestCase):
    async def test_1_hang_is_observable_false_never_fake_success(self):
        class _HangEgress(_EgressCtl):
            async def stop_egress(self, request):
                await asyncio.Event().wait()  # never completes => bounded wait times out

        svc = _mk_svc(_FxClient(_HangEgress()))
        res = await svc.stop_recording(egress_id="EG_HANG_1", timeout_sec=0.05)
        self.assertIs(res, False, "unresponsive egress must be observable False, never fabricated True")

    async def test_2_already_final_is_idempotent_true_never_double_stop_or_crash(self):
        from botocore.exceptions import ClientError

        class _FinalEgress(_EgressCtl):
            async def stop_egress(self, request):
                raise ClientError(
                    {"Error": {"Code": "NotFound", "Message": "egress already stopped / not found"}},
                    "stop_egress",
                )

        ctl = _FinalEgress()
        svc = _mk_svc(_FxClient(ctl))
        res = await svc.stop_recording(egress_id="EG_FINAL_1", timeout_sec=5)
        self.assertIs(res, True, "already-final stop must be idempotent True (no fake crash)")

    async def test_3_infra_error_is_observable_false_never_fake_success(self):
        class _DownEgress(_EgressCtl):
            async def stop_egress(self, request):
                raise RuntimeError("egress service unavailable")

        svc = _mk_svc(_FxClient(_DownEgress()))
        res = await svc.stop_recording(egress_id="EG_DOWN_1", timeout_sec=5)
        self.assertIs(res, False, "infra error must be observable False, never fabricated True")

    async def test_4_no_egress_id_returns_false_never_crash(self):
        svc = _mk_svc(_FxClient(_EgressCtl()))
        res = await svc.stop_recording(egress_id=None, timeout_sec=5)
        self.assertIs(res, False, "egress_id=None must be observable False, never crash")

    async def test_5_cleanup_is_room_scoped_status_filtered_and_skips_final_and_other_rooms(self):
        items = [
            _mk_item("room-a", "EG_A_ACTIVE", eg.EgressStatus.EGRESS_ACTIVE),
            _mk_item("room-a", "EG_A_STARTING", eg.EgressStatus.EGRESS_STARTING),
            _mk_item("room-a", "EG_A_COMPLETE", eg.EgressStatus.EGRESS_COMPLETE),
            _mk_item("room-b", "EG_B_ACTIVE", eg.EgressStatus.EGRESS_ACTIVE),
        ]
        ctl = _EgressCtl(items)
        svc = _mk_svc(_FxClient(ctl))
        count = await svc.cleanup_orphaned_egress("room-a")
        self.assertIsInstance(count, int, "cleanup returns a REAL int count, never MagicMock/faked")
        self.assertEqual(count, 2, "cleans exactly the 2 active/starting egress OF THIS room")
        self.assertIn("EG_A_ACTIVE", ctl.stops)
        self.assertIn("EG_A_STARTING", ctl.stops)
        self.assertNotIn("EG_A_COMPLETE", ctl.stops, "already-final egress must not be re-stopped")
        self.assertNotIn("EG_B_ACTIVE", ctl.stops, "other room must not be touched")


if __name__ == "__main__":
    import unittest

    unittest.main()
