"""
Unit tests for Workflow DB persistence, draft/publish lifecycle, and version immutability.
"""

import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from api.modules.workflows.services import WorkflowService
from api.modules.workflows.repositories import WorkflowRepository
from api.utils.errors import NotFoundError, BadRequestError, ForbiddenError


class TestWorkflowPersistence(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = WorkflowService()
        self.user_context = {
            "id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "reseller_id": None,
            "role": "CLIENT"
        }

    @patch("api.database.transaction")
    @patch("api.database.query")
    async def test_01_create_workflow_creates_container_and_draft(self, mock_query, mock_transaction):
        """Verify creating a workflow initializes parent record and version 0 draft."""
        wf_id = uuid.uuid4()
        now_dt = MagicMock()
        now_dt.isoformat.return_value = "2026-09-19T12:00:00Z"

        mock_wf_row = {
            "id": wf_id,
            "client_id": uuid.UUID(self.user_context["client_id"]),
            "user_id": uuid.UUID(self.user_context["id"]),
            "name": "Receptionist Workflow",
            "description": "Handles inbound clinic calls",
            "status": "active",
            "created_at": now_dt,
            "updated_at": now_dt
        }

        async def fake_tx(cb):
            conn = MagicMock()
            conn.fetch = AsyncMock(return_value=[mock_wf_row])
            return await cb(conn)

        mock_transaction.side_effect = fake_tx

        res = await self.service.create_workflow(
            {"name": "Receptionist Workflow", "description": "Handles inbound clinic calls"},
            self.user_context
        )
        self.assertEqual(res["name"], "Receptionist Workflow")
        self.assertEqual(res["id"], str(wf_id))

    def test_02_validate_definition_valid_graph(self):
        """Verify validate_definition returns valid=True on correct authoring graph."""
        valid_def = {
            "version": 1,
            "workflow_id": "wf_test",
            "name": "Test",
            "start_node": "start",
            "global_prompt": "Global prompt",
            "nodes": {
                "start": {"id": "start", "name": "Start", "type": "START", "prompt": "", "tools": [], "config": {"next_node": "agent"}},
                "agent": {"id": "agent", "name": "Agent", "type": "AGENT", "prompt": "Hello", "tools": ["end_call"], "config": {}},
                "end": {"id": "end", "name": "End", "type": "END", "prompt": "Bye", "tools": ["end_call"], "config": {}}
            },
            "edges": [
                {"id": "e1", "source": "start", "target": "agent", "type": "default"},
                {"id": "e2", "source": "agent", "target": "end", "type": "tool"}
            ]
        }
        res = self.service.validate_definition(valid_def)
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["errors"]), 0)
        self.assertEqual(res["node_count"], 3)
        self.assertEqual(res["edge_count"], 2)

    def test_03_validate_definition_invalid_graph(self):
        """Verify validate_definition returns structured error details on broken graph."""
        invalid_def = {
            "version": 1,
            "workflow_id": "wf_test",
            "name": "Test",
            "start_node": "missing_start",
            "nodes": {
                "agent": {"id": "agent", "name": "Agent", "type": "AGENT", "prompt": "Hello", "tools": ["unregistered_tool_xyz"], "config": {}}
            },
            "edges": [
                {"id": "e1", "source": "agent", "target": "nonexistent_node", "type": "default"}
            ]
        }
        res = self.service.validate_definition(invalid_def)
        self.assertFalse(res["valid"])
        self.assertTrue(len(res["errors"]) > 0)
        error_messages = [e["message"] for e in res["errors"]]
        self.assertTrue(any("missing_start" in m for m in error_messages))

    @patch("api.database.transaction")
    @patch("api.database.query")
    async def test_04_publish_workflow_creates_immutable_version(self, mock_query, mock_transaction):
        """Verify publishing locks parent workflow, validates, and creates version snapshot."""
        wf_id = str(uuid.uuid4())
        ver_id = uuid.uuid4()
        now_dt = MagicMock()
        now_dt.isoformat.return_value = "2026-09-19T12:00:00Z"

        mock_wf = {
            "id": uuid.UUID(wf_id),
            "client_id": uuid.UUID(self.user_context["client_id"]),
            "user_id": uuid.UUID(self.user_context["id"]),
            "name": "Publish Workflow",
            "status": "active",
            "created_at": now_dt,
            "updated_at": now_dt
        }
        mock_draft = {
            "id": uuid.uuid4(),
            "workflow_id": uuid.UUID(wf_id),
            "version_number": 0,
            "lifecycle_status": "draft",
            "definition": json.dumps({
                "version": 1,
                "workflow_id": wf_id,
                "name": "Published WF",
                "start_node": "start",
                "nodes": {
                    "start": {"id": "start", "name": "Start", "type": "START", "prompt": "", "tools": [], "config": {"next_node": "end"}},
                    "end": {"id": "end", "name": "End", "type": "END", "prompt": "End", "tools": ["end_call"], "config": {}}
                },
                "edges": [{"id": "e1", "source": "start", "target": "end", "type": "default"}]
            }),
            "ui_metadata": json.dumps({"viewport": {"x": 100, "y": 200}}),
            "created_at": now_dt
        }

        mock_query.side_effect = [
            [mock_wf],    # find_by_id in publish_workflow
            [mock_draft], # get_or_create_draft
        ]

        mock_published_row = {
            "id": ver_id,
            "workflow_id": uuid.UUID(wf_id),
            "version_number": 1,
            "lifecycle_status": "published",
            "definition": mock_draft["definition"],
            "ui_metadata": mock_draft["ui_metadata"],
            "schema_version": "1.0",
            "engine_version": "1.0",
            "validation_metadata": "{}",
            "created_at": now_dt,
            "published_at": now_dt,
            "created_by": uuid.UUID(self.user_context["id"])
        }

        async def fake_pub_tx(cb):
            conn = MagicMock()
            conn.fetch = AsyncMock(side_effect=[
                [{"id": uuid.UUID(wf_id)}], # row lock
                [{"next_version": 1}],       # next version calculation
                [mock_published_row]         # insert published version
            ])
            conn.execute = AsyncMock()
            return await cb(conn)

        mock_transaction.side_effect = fake_pub_tx

        res = await self.service.publish_workflow(wf_id, self.user_context)
        self.assertEqual(res["versionNumber"], 1)
        self.assertEqual(res["lifecycleStatus"], "published")
        self.assertEqual(res["id"], str(ver_id))


if __name__ == "__main__":
    unittest.main()
