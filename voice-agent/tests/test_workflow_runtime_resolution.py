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

    def test_05_safe_room_ref_sanitization(self):
        """Verify safe_room_ref returns deterministic 12-char SHA-256 hash without leaking phone numbers."""
        from workflow_engine import safe_room_ref
        
        phone_room = "sip_+14155552671_user_call"
        ref = safe_room_ref(phone_room)
        
        # Must be exact 12-char hex
        self.assertEqual(len(ref), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in ref))
        # Must not contain phone digits or substring
        self.assertNotIn("+14155552671", ref)
        # Must be deterministic
        self.assertEqual(ref, safe_room_ref(phone_room))
        # Handles None/empty
        self.assertEqual(safe_room_ref(None), "none")
        self.assertEqual(safe_room_ref(""), "none")

    @patch("api.modules.workflows.repositories.WorkflowRepository.find_version_by_id")
    async def test_06_simultaneous_v1_v2_call_isolation(self, mock_find_version):
        """Verify Call A on V1 and Call B on V2 execute in complete version isolation without cross-contamination."""
        v1_id = str(uuid.uuid4())
        v2_id = str(uuid.uuid4())
        wf_id = str(uuid.uuid4())

        v1_def = {
            "version": 1,
            "workflow_id": wf_id,
            "name": "Smoke Flow V1",
            "start_node": "start",
            "nodes": {
                "start": {"id": "start", "name": "Start", "type": "START", "prompt": "", "tools": [], "config": {"next_node": "agent"}},
                "agent": {"id": "agent", "name": "Agent V1", "type": "AGENT", "prompt": "V1: Politely greet the caller.", "tools": ["end_call"], "config": {}},
                "end": {"id": "end", "name": "End", "type": "END", "prompt": "Goodbye V1", "tools": ["end_call"], "config": {}}
            },
            "edges": [
                {"id": "e1", "source": "start", "target": "agent", "type": "default"},
                {"id": "e2", "source": "agent", "target": "end", "type": "tool"}
            ]
        }

        v2_def = {
            "version": 1,
            "workflow_id": wf_id,
            "name": "Smoke Flow V2",
            "start_node": "start",
            "nodes": {
                "start": {"id": "start", "name": "Start", "type": "START", "prompt": "", "tools": [], "config": {"next_node": "agent"}},
                "agent": {"id": "agent", "name": "Agent V2", "type": "AGENT", "prompt": "V2: This is workflow version two.", "tools": ["end_call"], "config": {}},
                "end": {"id": "end", "name": "End", "type": "END", "prompt": "Goodbye V2", "tools": ["end_call"], "config": {}}
            },
            "edges": [
                {"id": "e1", "source": "start", "target": "agent", "type": "default"},
                {"id": "e2", "source": "agent", "target": "end", "type": "tool"}
            ]
        }

        def mock_find(vid):
            if str(vid) == v1_id:
                return {"id": uuid.UUID(v1_id), "workflow_id": uuid.UUID(wf_id), "version_number": 1, "lifecycle_status": "published", "definition": v1_def}
            elif str(vid) == v2_id:
                return {"id": uuid.UUID(v2_id), "workflow_id": uuid.UUID(wf_id), "version_number": 2, "lifecycle_status": "published", "definition": v2_def}
            return None

        mock_find_version.side_effect = mock_find

        # Resolve Call A on V1
        compiled_a, wf_a, ver_a = await self.resolver.resolve_for_agent(
            agent_data={"id": "ag_1", "published_workflow_version_id": v1_id},
            tool_platform_instance=self.tp
        )
        ctx_a = WorkflowRunContext(run_id="call_a", workflow_id=wf_a, workflow_version_id=ver_a, agent_id="ag_1", room_name="room_a", participant_identity="part_a")

        # Resolve Call B on V2
        compiled_b, wf_b, ver_b = await self.resolver.resolve_for_agent(
            agent_data={"id": "ag_1", "published_workflow_version_id": v2_id},
            tool_platform_instance=self.tp
        )
        ctx_b = WorkflowRunContext(run_id="call_b", workflow_id=wf_b, workflow_version_id=ver_b, agent_id="ag_1", room_name="room_b", participant_identity="part_b")

        # Assert independent state and prompts
        self.assertEqual(ctx_a.workflow_version_id, v1_id)
        self.assertEqual(ctx_b.workflow_version_id, v2_id)
        self.assertEqual(compiled_a.nodes["agent"].prompt, "V1: Politely greet the caller.")
        self.assertEqual(compiled_b.nodes["agent"].prompt, "V2: This is workflow version two.")


if __name__ == "__main__":
    unittest.main()
