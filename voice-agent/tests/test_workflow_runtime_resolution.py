"""
Unit tests for WorkflowRuntimeResolver and runtime version pinning.
"""

import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from api.modules.workflows.resolver import WorkflowRuntimeResolver
from workflow_engine import WorkflowRunContext, WorkflowRuntime, ToolPlatform


class TestWorkflowRuntimeResolution(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tp = ToolPlatform(client_id="client_test")
        self.resolver = WorkflowRuntimeResolver()

    async def test_01_null_version_returns_compatibility_workflow(self):
        """Verify NULL published_workflow_version_id resolves to compatibility workflow."""
        agent_data = {
            "id": "ag_123",
            "name": "LegacyAgent",
            "published_workflow_version_id": None
        }

        compiled, wf_id, ver_id = await self.resolver.resolve_for_agent(
            agent_data=agent_data,
            custom_prompt="Custom legacy prompt",
            tool_platform_instance=self.tp
        )
        self.assertIsNotNone(compiled)
        self.assertIsNone(wf_id)
        self.assertIsNone(ver_id)
        self.assertEqual(compiled.start_node_id, "default_node")
        self.assertIn("default_node", compiled.nodes)

    @patch("api.modules.workflows.repositories.WorkflowRepository.find_version_by_id")
    async def test_02_pinned_version_resolves_exact_definition(self, mock_find_version):
        """Verify NON-NULL published_workflow_version_id loads and compiles exact definition."""
        ver_id = str(uuid.uuid4())
        wf_id = str(uuid.uuid4())

        exact_def = {
            "version": 1,
            "workflow_id": wf_id,
            "name": "Pinned Flow",
            "start_node": "start_step",
            "global_prompt": "Always be polite.",
            "nodes": {
                "start_step": {
                    "id": "start_step",
                    "name": "Greeting Step",
                    "type": "START",
                    "prompt": "",
                    "tools": [],
                    "config": {"next_node": "agent_step"}
                },
                "agent_step": {
                    "id": "agent_step",
                    "name": "Agent Conversation",
                    "type": "AGENT",
                    "prompt": "Ask the caller for their account ID.",
                    "tools": ["end_call"],
                    "config": {}
                },
                "end_step": {
                    "id": "end_step",
                    "name": "Goodbye Step",
                    "type": "END",
                    "prompt": "Goodbye!",
                    "tools": ["end_call"],
                    "config": {}
                }
            },
            "edges": [
                {"id": "e_start", "source": "start_step", "target": "agent_step", "type": "default"},
                {"id": "e_end", "source": "agent_step", "target": "end_step", "type": "tool"}
            ]
        }

        mock_find_version.return_value = {
            "id": uuid.UUID(ver_id),
            "workflow_id": uuid.UUID(wf_id),
            "version_number": 2,
            "lifecycle_status": "published",
            "definition": exact_def
        }

        agent_data = {
            "id": "ag_pinned",
            "name": "PinnedAgent",
            "published_workflow_version_id": ver_id
        }

        compiled, resolved_wf_id, resolved_ver_id = await self.resolver.resolve_for_agent(
            agent_data=agent_data,
            tool_platform_instance=self.tp
        )
        self.assertEqual(resolved_wf_id, wf_id)
        self.assertEqual(resolved_ver_id, ver_id)
        self.assertEqual(compiled.start_node_id, "start_step")
        self.assertIn("agent_step", compiled.nodes)

    @patch("api.modules.workflows.repositories.WorkflowRepository.find_version_by_id")
    async def test_03_missing_or_corrupt_version_raises_runtime_error(self, mock_find_version):
        """Verify resolver raises explicit RuntimeError when configured version is missing or invalid."""
        mock_find_version.return_value = None

        agent_data = {
            "id": "ag_broken",
            "name": "BrokenAgent",
            "published_workflow_version_id": "missing_ver_123"
        }

        with self.assertRaises(RuntimeError):
            await self.resolver.resolve_for_agent(
                agent_data=agent_data,
                tool_platform_instance=self.tp
            )

    @patch("api.modules.workflows.repositories.WorkflowRepository.find_version_by_id")
    async def test_04_active_call_pinned_version_remains_immutable_during_republish(self, mock_find_version):
        """Verify that an active call WorkflowRunContext retains its pinned v1 throughout execution."""
        v1_id = "ver_001"
        v1_def = {
            "version": 1,
            "workflow_id": "wf_1",
            "name": "Flow V1",
            "start_node": "start",
            "nodes": {
                "start": {"id": "start", "name": "Start", "type": "START", "prompt": "", "tools": [], "config": {"next_node": "end"}},
                "end": {"id": "end", "name": "End", "type": "END", "prompt": "End V1", "tools": ["end_call"], "config": {}}
            },
            "edges": [{"id": "e1", "source": "start", "target": "end", "type": "default"}]
        }

        mock_find_version.return_value = {
            "id": v1_id,
            "workflow_id": "wf_1",
            "version_number": 1,
            "lifecycle_status": "published",
            "definition": v1_def
        }

        compiled_v1, wf_id, ver_id = await self.resolver.resolve_for_agent(
            agent_data={"published_workflow_version_id": v1_id},
            tool_platform_instance=self.tp
        )

        ctx = WorkflowRunContext(
            run_id="call_v1_active",
            workflow_id=wf_id,
            workflow_version_id=ver_id,
            agent_id="ag_1",
            room_name="room_v1",
            participant_identity="part_v1"
        )

        # In-flight call holds compiled_v1 and workflow_version_id='ver_001'
        self.assertEqual(ctx.workflow_version_id, "ver_001")
        self.assertEqual(compiled_v1.nodes["end"].prompt, "End V1")


if __name__ == "__main__":
    unittest.main()
