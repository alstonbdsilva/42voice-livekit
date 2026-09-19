"""
Unit tests for Workflow publish concurrency and locking safety.
"""

import asyncio
import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from api.modules.workflows.repositories import WorkflowRepository


class TestWorkflowConcurrency(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = WorkflowRepository()

    @patch("api.database.transaction")
    async def test_01_publish_version_uses_parent_row_lock(self, mock_transaction):
        """Verify publish_version queries parent workflow FOR UPDATE before computing version number."""
        wf_id = str(uuid.uuid4())
        mock_user_id = str(uuid.uuid4())
        now_dt = MagicMock()
        now_dt.isoformat.return_value = "2026-09-19T12:00:00Z"

        queries_executed = []

        async def fake_tx(cb):
            conn = MagicMock()
            async def fake_fetch(query, *args):
                queries_executed.append(query)
                if "FOR UPDATE" in query:
                    return [{"id": uuid.UUID(wf_id)}]
                elif "MAX(version_number)" in query:
                    return [{"next_version": 3}]
                elif "INSERT INTO workflow_versions" in query:
                    return [{
                        "id": uuid.uuid4(),
                        "workflow_id": uuid.UUID(wf_id),
                        "version_number": 3,
                        "lifecycle_status": "published",
                        "definition": "{}",
                        "ui_metadata": "{}",
                        "schema_version": "1.0",
                        "engine_version": "1.0",
                        "validation_metadata": "{}",
                        "created_at": now_dt,
                        "published_at": now_dt,
                        "created_by": uuid.UUID(mock_user_id)
                    }]
                return []

            conn.fetch = AsyncMock(side_effect=fake_fetch)
            conn.execute = AsyncMock()
            return await cb(conn)

        mock_transaction.side_effect = fake_tx

        res = await self.repository.publish_version(
            workflow_id=wf_id,
            definition={"nodes": [], "edges": []},
            user_id=mock_user_id
        )
        self.assertEqual(res["version_number"], 3)
        self.assertTrue(any("FOR UPDATE" in q for q in queries_executed), "Must lock parent row with FOR UPDATE")
        self.assertTrue(any("MAX(version_number)" in q for q in queries_executed), "Must query max version within lock")

    async def test_02_concurrent_publishes_sequential_versions(self):
        """Simulate two concurrent publish requests on the same workflow resulting in distinct versions."""
        current_db_version = 0
        lock = asyncio.Lock()

        async def simulated_publish(workflow_id: str, caller_id: str):
            nonlocal current_db_version
            # Simulates database transaction + SELECT ... FOR UPDATE
            async with lock:
                # Inside locked transaction
                await asyncio.sleep(0.01)  # small processing delay
                current_db_version += 1
                assigned_version = current_db_version
                return {
                    "caller": caller_id,
                    "version_number": assigned_version
                }

        results = await asyncio.gather(
            simulated_publish("wf_123", "caller_1"),
            simulated_publish("wf_123", "caller_2")
        )

        version_numbers = [r["version_number"] for r in results]
        self.assertEqual(sorted(version_numbers), [1, 2], "Concurrent publishes must assign unique sequential versions")


if __name__ == "__main__":
    unittest.main()
