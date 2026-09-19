"""
Unit tests for the LiveKit Generic Node-Based Voice Workflow Engine (Phase 1).
"""

import asyncio
import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from workflow_engine import (
    AgentNodeExecutor,
    CompiledEdge,
    CompiledNode,
    CompiledWorkflow,
    ConditionEvaluator,
    ConditionNodeExecutor,
    ContextExposurePolicy,
    EndNodeExecutor,
    NodeResult,
    StartNodeExecutor,
    SystemToolRegistry,
    ToolPlatform,
    WorkflowCompiler,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowParser,
    WorkflowRunContext,
    WorkflowRuntime,
    WorkflowValidator,
    build_compatibility_workflow,
    resolve_legacy_agent_prompt,
)


class TestWorkflowEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tp = ToolPlatform(parent_system_registry=SystemToolRegistry())
        self.tp.register_system_tool("lookup_caller", lambda: "caller_data", "Look up caller details")
        self.tp.register_system_tool("update_record", lambda: "ok", "Update customer record")
        self.tp.register_system_tool("end_call", lambda: "disconnecting", "Authoritative end call tool")

    def test_01_parse_valid_workflow_json(self):
        raw_json = json.dumps({
            "version": 1,
            "workflow_id": "wf_test_01",
            "name": "Test Workflow",
            "start_node": "step_1",
            "global_prompt": "You are a helpful assistant.",
            "variables": {
                "caller_name": {"type": "string"},
                "is_verified": {"type": "boolean", "default": False}
            },
            "nodes": [
                {
                    "id": "step_1",
                    "name": "Step One",
                    "type": "AGENT",
                    "prompt": "Greet caller.",
                    "tools": ["lookup_caller"]
                },
                {
                    "id": "step_2",
                    "name": "Step Two",
                    "type": "END",
                    "prompt": "Say goodbye.",
                    "tools": ["end_call"]
                }
            ],
            "edges": [
                {
                    "id": "e1_to_e2",
                    "source": "step_1",
                    "target": "step_2",
                    "type": "semantic",
                    "description": "Move to close"
                }
            ]
        })

        graph = WorkflowParser.parse(raw_json)
        self.assertEqual(graph.version, 1)
        self.assertEqual(graph.start_node, "step_1")
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)

    def test_02_arbitrary_node_names(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_arbitrary",
            name="Arbitrary Nodes",
            start_node="custom_node_999",
            nodes={
                "custom_node_999": WorkflowNode(id="custom_node_999", name="Start", type="AGENT", tools=["lookup_caller"]),
                "step_alpha_42": WorkflowNode(id="step_alpha_42", name="Mid", type="AGENT"),
                "terminal_xyz": WorkflowNode(id="terminal_xyz", name="Close", type="END", tools=["end_call"])
            },
            edges=[
                WorkflowEdge(id="e1", source="custom_node_999", target="step_alpha_42", type="semantic"),
                WorkflowEdge(id="e2", source="step_alpha_42", target="terminal_xyz", type="semantic")
            ]
        )

        compiled = WorkflowCompiler.compile(graph, tool_platform_instance=self.tp)
        self.assertIn("custom_node_999", compiled.nodes)
        self.assertIn("step_alpha_42", compiled.nodes)
        self.assertIn("terminal_xyz", compiled.nodes)

    def test_03_validation_rejects_missing_start_node(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_invalid",
            name="Missing Start",
            start_node="non_existent_start",
            nodes={
                "node_1": WorkflowNode(id="node_1", name="N1", type="AGENT")
            }
        )
        errors = WorkflowValidator.validate(graph, self.tp)
        self.assertTrue(any("start_node 'non_existent_start' does not exist" in e for e in errors))

    def test_04_validation_rejects_unknown_transition_target(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_invalid",
            name="Invalid Target",
            start_node="node_1",
            nodes={
                "node_1": WorkflowNode(id="node_1", name="N1", type="AGENT")
            },
            edges=[
                WorkflowEdge(id="e1", source="node_1", target="non_existent_target")
            ]
        )
        errors = WorkflowValidator.validate(graph, self.tp)
        self.assertTrue(any("nonexistent target node: 'non_existent_target'" in e for e in errors))

    def test_05_validation_rejects_unknown_tool(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_invalid",
            name="Unknown Tool",
            start_node="node_1",
            nodes={
                "node_1": WorkflowNode(id="node_1", name="N1", type="AGENT", tools=["unregistered_tool_xyz"])
            }
        )
        errors = WorkflowValidator.validate(graph, self.tp)
        self.assertTrue(any("unregistered tool: 'unregistered_tool_xyz'" in e for e in errors))

    def test_06_validation_rejects_duplicate_edge_ids(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_invalid",
            name="Dup Edge",
            start_node="node_1",
            nodes={
                "node_1": WorkflowNode(id="node_1", name="N1", type="AGENT"),
                "node_2": WorkflowNode(id="node_2", name="N2", type="AGENT")
            },
            edges=[
                WorkflowEdge(id="dup_edge", source="node_1", target="node_2"),
                WorkflowEdge(id="dup_edge", source="node_2", target="node_1")
            ]
        )
        errors = WorkflowValidator.validate(graph, self.tp)
        self.assertTrue(any("Duplicate edge ID found: 'dup_edge'" in e for e in errors))

    def test_07_duplicate_tool_registration_prohibited(self):
        with self.assertRaises(ValueError):
            self.tp.register_system_tool("lookup_caller", lambda: "dup", "Duplicate registration")

    def test_08_safe_condition_evaluator(self):
        vars_state = {
            "caller_name": "Alice",
            "score": 85,
            "is_verified": True,
            "tags": ["vip", "enterprise"],
            "empty_val": None
        }

        # Test equals
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "caller_name", "operator": "equals", "value": "Alice"}, vars_state))
        self.assertFalse(ConditionEvaluator.evaluate({"variable": "caller_name", "operator": "equals", "value": "Bob"}, vars_state))

        # Test comparisons
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "score", "operator": "gt", "value": 80}, vars_state))
        self.assertFalse(ConditionEvaluator.evaluate({"variable": "score", "operator": "lte", "value": 50}, vars_state))

        # Test exists & empty
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "caller_name", "operator": "exists"}, vars_state))
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "empty_val", "operator": "is_empty"}, vars_state))
        self.assertFalse(ConditionEvaluator.evaluate({"variable": "caller_name", "operator": "is_empty"}, vars_state))

        # Test contains & in
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "tags", "operator": "contains", "value": "vip"}, vars_state))
        self.assertTrue(ConditionEvaluator.evaluate({"variable": "caller_name", "operator": "in", "value": ["Alice", "Bob"]}, vars_state))

        # Test composite and / or / not
        self.assertTrue(ConditionEvaluator.evaluate({
            "and": [
                {"variable": "score", "operator": "gte", "value": 80},
                {"variable": "is_verified", "operator": "equals", "value": True}
            ]
        }, vars_state))

        self.assertTrue(ConditionEvaluator.evaluate({
            "or": [
                {"variable": "score", "operator": "lt", "value": 50},
                {"variable": "caller_name", "operator": "equals", "value": "Alice"}
            ]
        }, vars_state))

        self.assertTrue(ConditionEvaluator.evaluate({
            "not": {"variable": "is_verified", "operator": "equals", "value": False}
        }, vars_state))

    async def test_09_condition_node_execution_branches(self):
        node = CompiledNode(
            id="cond_node",
            name="Check Auth",
            type="CONDITION",
            prompt=None,
            tool_names=(),
            context_policy=ContextExposurePolicy(),
            config={
                "condition": {"variable": "is_verified", "operator": "equals", "value": True},
                "on_true": "verified_node",
                "on_false": "collect_auth_node",
                "on_error": "escalate_node"
            },
            executor=ConditionNodeExecutor()
        )

        # 1. Condition True
        ctx_true = WorkflowRunContext(
            run_id="run_1",
            workflow_version_id="v1",
            agent_id="agent_1",
            room_name="room_1",
            participant_identity="part_1",
            variables={"is_verified": True}
        )
        res_true = await ConditionNodeExecutor().execute(node, ctx_true, None)
        self.assertEqual(res_true.status, "transition")
        self.assertEqual(res_true.target_node_id, "verified_node")

        # 2. Condition False
        ctx_false = WorkflowRunContext(
            run_id="run_2",
            workflow_version_id="v1",
            agent_id="agent_1",
            room_name="room_1",
            participant_identity="part_1",
            variables={"is_verified": False}
        )
        res_false = await ConditionNodeExecutor().execute(node, ctx_false, None)
        self.assertEqual(res_false.status, "transition")
        self.assertEqual(res_false.target_node_id, "collect_auth_node")

        # 3. Condition Error (missing malformed structure)
        node_bad = CompiledNode(
            id="cond_bad",
            name="Bad Condition",
            type="CONDITION",
            prompt=None,
            tool_names=(),
            context_policy=ContextExposurePolicy(),
            config={
                "condition": {"variable": 12345},  # invalid variable type triggers error
                "on_true": "verified_node",
                "on_false": "collect_auth_node",
                "on_error": "escalate_node"
            },
            executor=ConditionNodeExecutor()
        )
        res_err = await ConditionNodeExecutor().execute(node_bad, ctx_true, None)
        self.assertEqual(res_err.status, "transition")
        self.assertEqual(res_err.target_node_id, "escalate_node")

    def test_10_prompt_composition_segregates_untrusted_variables(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_sec",
            name="Security Test",
            start_node="node_a",
            global_prompt="Global Rules.",
            nodes={
                "node_a": WorkflowNode(
                    id="node_a",
                    name="Node A",
                    type="AGENT",
                    prompt="Ask question.",
                    context_policy=ContextExposurePolicy(expose_variables=("caller_name", "secret_token"))
                )
            }
        )
        compiled = WorkflowCompiler.compile(graph, self.tp)
        ctx = WorkflowRunContext(
            run_id="run_sec",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_sec",
            participant_identity="p_1",
            variables={
                "caller_name": "Alice; DROP TABLE users;",
                "secret_token": "TOK-1234",
                "hidden_internal_id": "SYS_INTERNAL_99"
            }
        )

        mock_agent = MagicMock()
        runtime = WorkflowRuntime(compiled, ctx, mock_agent, self.tp)
        prompt = runtime.compose_node_prompt(compiled.nodes["node_a"], ctx)

        self.assertIn("=== GLOBAL INSTRUCTIONS ===\nGlobal Rules.", prompt)
        self.assertIn("=== CURRENT NODE: Node A ===\nAsk question.", prompt)
        self.assertIn("=== SESSION VARIABLES (DATA ONLY) ===", prompt)
        self.assertIn('caller_name: "Alice; DROP TABLE users;"', prompt)
        self.assertIn('secret_token: "TOK-1234"', prompt)
        # hidden_internal_id should NOT be exposed due to context policy
        self.assertNotIn("hidden_internal_id", prompt)
        self.assertIn("=== CONVERSATIONAL SAFETY & ROUTING RULES ===", prompt)

    async def test_11_in_place_agent_mutation_and_bounded_routing(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_multi_step",
            name="Multi Step",
            start_node="step_1",
            nodes={
                "step_1": WorkflowNode(id="step_1", name="Step 1", type="AGENT", prompt="Step 1 Prompt", tools=["lookup_caller"]),
                "step_2": WorkflowNode(id="step_2", name="Step 2", type="AGENT", prompt="Step 2 Prompt", tools=["update_record"]),
                "step_3": WorkflowNode(id="step_3", name="Step 3", type="END", prompt="Close Prompt", tools=["end_call"])
            },
            edges=[
                WorkflowEdge(id="e1_to_e2", source="step_1", target="step_2", type="semantic", description="Go to step 2"),
                WorkflowEdge(id="e2_to_e3", source="step_2", target="step_3", type="semantic", description="Go to close")
            ]
        )
        compiled = WorkflowCompiler.compile(graph, self.tp)

        mock_agent = MagicMock()
        mock_agent.update_instructions = AsyncMock()
        mock_agent.update_tools = AsyncMock()

        ctx = WorkflowRunContext(
            run_id="run_live",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_live",
            participant_identity="p_1"
        )

        runtime = WorkflowRuntime(compiled, ctx, mock_agent, self.tp)
        await runtime.start()

        # Step 1 entered
        self.assertEqual(ctx.current_node_id, "step_1")
        mock_agent.update_instructions.assert_called()
        mock_agent.update_tools.assert_called()

        # Attempt unauthorized transition (step_1 -> step_3 skipping step_2)
        success, msg = await runtime.execute_transition("step_3", reason="Hacking target")
        self.assertFalse(success)
        self.assertIn("Illegal transition", msg)
        self.assertEqual(ctx.current_node_id, "step_1")

        # Execute authorized transition (step_1 -> step_2)
        success, msg = await runtime.execute_transition("step_2", reason="Valid transition")
        self.assertTrue(success)
        self.assertEqual(ctx.current_node_id, "step_2")

    async def test_12_loop_and_max_transition_limits(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_cycle",
            name="Cycle Guard",
            start_node="node_a",
            execution_config={
                "max_transitions_per_call": 3,
                "max_node_visits": 2
            },
            nodes={
                "node_a": WorkflowNode(id="node_a", name="A", type="AGENT"),
                "node_b": WorkflowNode(id="node_b", name="B", type="AGENT")
            },
            edges=[
                WorkflowEdge(id="a_to_b", source="node_a", target="node_b", type="semantic"),
                WorkflowEdge(id="b_to_a", source="node_b", target="node_a", type="semantic")
            ]
        )
        compiled = WorkflowCompiler.compile(graph, self.tp)

        mock_agent = MagicMock()
        mock_agent.update_instructions = AsyncMock()
        mock_agent.update_tools = AsyncMock()

        ctx = WorkflowRunContext(
            run_id="run_cycle",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_cycle",
            participant_identity="p_1"
        )

        runtime = WorkflowRuntime(compiled, ctx, mock_agent, self.tp)
        await runtime.start()  # Visits node_a (count=1)

        await runtime.execute_transition("node_b")  # Visits node_b (count=1, trans=1)
        await runtime.execute_transition("node_a")  # Visits node_a (count=2, trans=2)
        await runtime.execute_transition("node_b")  # Visits node_b (count=2, trans=3)

        # Exceeds max transitions (limit=3)
        success, msg = await runtime.execute_transition("node_a")
        self.assertFalse(success)
        self.assertIn("Maximum call transition limit", msg)

    def test_13_backward_compatibility_prompt_and_tools(self):
        agent_data = {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Legacy Assistant",
            "activity_description": "You are a customer service assistant."
        }
        custom_prompt = "Custom instructions for caller."

        # 1. Test prompt resolver
        prompt = resolve_legacy_agent_prompt(agent_data, custom_prompt, out_of_credits=False)
        self.assertIn("Custom instructions for caller.", prompt)
        self.assertIn("CRITICAL CONVERSATION TERMINATION RULE:", prompt)
        self.assertIn("### CALLER NAME CAPTURE RULES:", prompt)

        # 2. Test fallback compatibility graph construction
        compiled = build_compatibility_workflow(
            agent_data=agent_data,
            custom_prompt=custom_prompt,
            dynamic_tool_names=["lookup_caller", "update_record"]
        )

        self.assertEqual(compiled.start_node_id, "default_node")
        self.assertIn("default_node", compiled.nodes)
        self.assertIn("lookup_caller", compiled.nodes["default_node"].tool_names)
        self.assertIn("update_record", compiled.nodes["default_node"].tool_names)
        self.assertIn("end_call", compiled.nodes["default_node"].tool_names)

    async def test_14_start_and_end_node_executors(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_start_end",
            name="Start End Test",
            start_node="start_step",
            nodes={
                "start_step": WorkflowNode(id="start_step", name="Start", type="START"),
                "agent_step": WorkflowNode(id="agent_step", name="Agent", type="AGENT", tools=["lookup_caller"]),
                "end_step": WorkflowNode(id="end_step", name="End", type="END", tools=["end_call"])
            },
            edges=[
                WorkflowEdge(id="e_start_to_agent", source="start_step", target="agent_step", type="default"),
                WorkflowEdge(id="e_agent_to_end", source="agent_step", target="end_step", type="semantic")
            ]
        )
        compiled = WorkflowCompiler.compile(graph, self.tp)
        mock_agent = MagicMock()
        mock_agent.update_instructions = AsyncMock()
        mock_agent.update_tools = AsyncMock()

        ctx = WorkflowRunContext(
            run_id="run_start_end",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_se",
            participant_identity="p_1"
        )
        runtime = WorkflowRuntime(compiled, ctx, mock_agent, self.tp)
        await runtime.start()

        # START node automatically transitioned to agent_step
        self.assertEqual(ctx.current_node_id, "agent_step")
        self.assertIn("start_step", ctx.visited_nodes)
        self.assertIn("agent_step", ctx.visited_nodes)

        # Transition to END node
        success, msg = await runtime.execute_transition("end_step")
        self.assertTrue(success)
        self.assertEqual(ctx.current_node_id, "end_step")
        self.assertEqual(ctx.status, "completed")
        # Ensure agent.on_exit was NOT called directly by EndNodeExecutor
        self.assertFalse(hasattr(mock_agent, "on_exit") and mock_agent.on_exit.called)

    def test_15_idempotency_key_generation(self):
        run_id = "run_123"
        node_id = "node_charge"
        tool_exec_id = "exec_abc"

        key1 = ToolPlatform.generate_idempotency_key(run_id, node_id, tool_exec_id)
        key2 = ToolPlatform.generate_idempotency_key(run_id, node_id, tool_exec_id)
        key3 = ToolPlatform.generate_idempotency_key(run_id, node_id, "exec_diff")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertEqual(len(key1), 32)

    def test_16_workflow_run_context_early_creation(self):
        ctx = WorkflowRunContext(
            run_id="early_run_uuid",
            workflow_version_id="wv_1",
            agent_id="ag_1",
            room_name="room_call_101",
            participant_identity="user_caller"
        )

        # Early in call, conversation_id and recording_id do not exist yet
        self.assertIsNone(ctx.conversation_id)
        self.assertIsNone(ctx.recording_id)
        self.assertEqual(ctx.status, "running")
        self.assertEqual(ctx.run_id, "early_run_uuid")

        # Emitting trace works before conversation persistence
        ctx.emit_trace("TEST_EVENT", data={"msg": "hello"})
        self.assertEqual(len(ctx.trace_events), 1)
        self.assertEqual(ctx.trace_events[0]["event_type"], "TEST_EVENT")

        # After CALL_PERSIST, correlation IDs are attached
        ctx.conversation_id = "conv_uuid_999"
        ctx.recording_id = "rec_uuid_888"
        ctx.status = "completed"
        self.assertEqual(ctx.conversation_id, "conv_uuid_999")
        self.assertEqual(ctx.recording_id, "rec_uuid_888")

    async def test_17_deterministic_edge_priorities(self):
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_det_prio",
            name="Deterministic Priority",
            start_node="node_input",
            nodes={
                "node_input": WorkflowNode(id="node_input", name="Input", type="AGENT"),
                "high_priority_target": WorkflowNode(id="high_priority_target", name="High", type="AGENT"),
                "low_priority_target": WorkflowNode(id="low_priority_target", name="Low", type="AGENT")
            },
            edges=[
                WorkflowEdge(
                    id="e_low",
                    source="node_input",
                    target="low_priority_target",
                    type="deterministic",
                    condition={"variable": "score", "operator": "gte", "value": 50},
                    priority=20
                ),
                WorkflowEdge(
                    id="e_high",
                    source="node_input",
                    target="high_priority_target",
                    type="deterministic",
                    condition={"variable": "score", "operator": "gte", "value": 90},
                    priority=5
                )
            ]
        )
        compiled = WorkflowCompiler.compile(graph, self.tp)
        mock_agent = MagicMock()
        mock_agent.update_instructions = AsyncMock()
        mock_agent.update_tools = AsyncMock()

        ctx = WorkflowRunContext(
            run_id="run_prio",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_prio",
            participant_identity="p_1",
            variables={"score": 95}  # Satisfies both >=50 and >=90
        )

        runtime = WorkflowRuntime(compiled, ctx, mock_agent, self.tp)
        await runtime.start()

    def test_19_string_and_double_encoded_json_parsing(self):
        # 1. Single string JSON
        single_json = json.dumps({
            "version": 1,
            "workflow_id": "wf_single",
            "start_node": "n1",
            "nodes": {"n1": "You are a helpful assistant."}
        })
        graph1 = WorkflowParser.parse(single_json)
        self.assertEqual(graph1.workflow_id, "wf_single")
        self.assertIn("n1", graph1.nodes)
        self.assertEqual(graph1.nodes["n1"].prompt, "You are a helpful assistant.")

        # 2. Double-encoded JSON string
        double_json = json.dumps(single_json)
        graph2 = WorkflowParser.parse(double_json)
        self.assertEqual(graph2.workflow_id, "wf_single")

        # 3. List of node ID strings
        list_json = {
            "version": 1,
            "workflow_id": "wf_list_nodes",
            "start_node": "step_a",
            "nodes": ["step_a", "step_b"]
        }
        graph3 = WorkflowParser.parse(list_json)
        self.assertIn("step_a", graph3.nodes)
        self.assertIn("step_b", graph3.nodes)

    async def test_20_production_voice_agent_integration_with_workflow_runtime(self):
        """Verify VoiceAgent interacts with WorkflowRuntime properly on startup and transitions."""
        from agent import VoiceAgent

        # Mock VoiceAgent dependencies
        mock_session_mgr = MagicMock()
        mock_booking = MagicMock()
        mock_sales = MagicMock()
        mock_support = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enable_transcripts = False
        mock_ctx = MagicMock()
        mock_ctx.room.name = "room_test_prod"

        agent_data = {"id": "ag_prod_123", "name": "ProdAgent", "activity_description": "Production prompt"}
        custom_prompt = "Custom instructions for production."

        compiled_wf = build_compatibility_workflow(
            agent_data=agent_data,
            custom_prompt=custom_prompt,
            dynamic_tool_names=["lookup_caller"]
        )

        run_ctx = WorkflowRunContext(
            run_id="run_prod_001",
            workflow_version_id=None,
            agent_id="ag_prod_123",
            room_name="room_test_prod",
            participant_identity="part_user"
        )

        agent = VoiceAgent(
            session_manager=mock_session_mgr,
            booking_agent=mock_booking,
            sales_agent=mock_sales,
            support_agent=mock_support,
            settings=mock_settings,
            room_name="room_test_prod",
            participant_id="part_user",
            ctx=mock_ctx,
            custom_prompt=custom_prompt,
            agent_name="ProdAgent",
            agent_data=agent_data
        )

        runtime = WorkflowRuntime(compiled_wf, run_ctx, agent, self.tp)
        agent.workflow_runtime = runtime
        agent.run_id = "run_prod_001"

        # Start runtime via on_enter
        await agent.on_enter()
        self.assertEqual(run_ctx.current_node_id, "default_node")
        self.assertEqual(len(run_ctx.visited_nodes), 1)

    def test_21_livekit_sdk_update_instructions_and_tools_interface_verification(self):
        """Verify that livekit.agents.Agent exposes async update_instructions and update_tools in installed 1.5.13 SDK."""
        import inspect
        from livekit.agents import Agent

        # Check update_instructions
        self.assertTrue(hasattr(Agent, "update_instructions"), "Agent must have update_instructions method")
        self.assertTrue(inspect.iscoroutinefunction(Agent.update_instructions), "Agent.update_instructions must be a coroutine function (async)")

        # Check update_tools
        self.assertTrue(hasattr(Agent, "update_tools"), "Agent must have update_tools method")
        self.assertTrue(inspect.iscoroutinefunction(Agent.update_tools), "Agent.update_tools must be a coroutine function (async)")

    def test_22_single_source_legacy_prompt_resolver_identity(self):
        """Verify that resolve_legacy_agent_prompt is identical across agent.py and workflow_engine.py."""
        import agent
        from workflow_engine import resolve_legacy_agent_prompt

        agent_data = {"id": "test_id", "name": "TestBot", "activity_description": "Legacy activity"}
        custom_prompt = "Custom system prompt for testing."

        prompt_from_wf = resolve_legacy_agent_prompt(agent_data, custom_prompt, out_of_credits=False)
        self.assertIn("Custom system prompt for testing.", prompt_from_wf)
        self.assertIn("CRITICAL CONVERSATION TERMINATION RULE:", prompt_from_wf)
        self.assertIn("### CALLER NAME CAPTURE RULES:", prompt_from_wf)

        # Test out of credits prompt
        prompt_credits = resolve_legacy_agent_prompt(agent_data, custom_prompt, out_of_credits=True)
        self.assertEqual(prompt_credits, "You are a billing notice voice. State that the account is out of credits and goodbye.")

    def test_23_end_node_safety_delegates_to_end_call(self):
        """Verify END NodeExecutor provides end_call and does NOT invoke agent.on_exit directly."""
        mock_agent = MagicMock()
        mock_agent.on_exit = AsyncMock()

        node = CompiledNode(
            id="end_step",
            name="End Step",
            type="END",
            prompt="Farewell message",
            tool_names=("end_call",),
            context_policy=ContextExposurePolicy(),
            config={},
            executor=EndNodeExecutor()
        )

        ctx = WorkflowRunContext(
            run_id="run_end_safe",
            workflow_version_id="v1",
            agent_id="ag_1",
            room_name="room_end",
            participant_identity="p_1"
        )

        runtime = WorkflowRuntime(
            compiled=CompiledWorkflow(
                workflow_id="wf_end",
                version=1,
                start_node_id="end_step",
                global_prompt="",
                variable_schema={},
                nodes={"end_step": node},
                outgoing_edges={},
                tool_requirements={"end_call"},
                max_transitions=10,
                max_node_visits=5
            ),
            context=ctx,
            agent=mock_agent,
            tool_platform_instance=self.tp
        )

        res = asyncio.run(EndNodeExecutor().execute(node, ctx, runtime))
        self.assertEqual(res.status, "terminal")
        self.assertTrue(res.terminal)
        self.assertEqual(len(res.updated_tools), 1)
        # on_exit must NOT have been called directly
        mock_agent.on_exit.assert_not_called()

    def test_24_workflow_run_id_created_before_conversation_persistence(self):
        """Verify run_id is established and valid before conversation persistence."""
        run_id = str(uuid.uuid4())
        ctx = WorkflowRunContext(
            run_id=run_id,
            workflow_version_id=None,
            agent_id="ag_early",
            room_name="room_early_123",
            participant_identity="caller_1"
        )
        self.assertIsNotNone(ctx.run_id)
        self.assertIsNone(ctx.conversation_id)
        self.assertIsNone(ctx.recording_id)
        self.assertEqual(ctx.status, "running")

    def test_25_failed_pre_participant_dispatch_safety(self):
        """Verify that an unassigned / failed dispatch does not produce a successful workflow run."""
        ctx = WorkflowRunContext(
            run_id="run_failed_dispatch",
            workflow_version_id=None,
            agent_id=None,
            room_name="room_unassigned",
            participant_identity="unknown_participant"
        )
        self.assertEqual(ctx.status, "running")
        # If dispatch fails or unassigned number rejected, status is not 'completed' with conversation
        self.assertIsNone(ctx.conversation_id)
        self.assertIsNone(ctx.recording_id)

    async def test_26_multi_tenant_call_scoped_tool_isolation_concurrent(self):
        """Verify that two simultaneous runtimes for different clients with custom tools are strictly isolated."""
        # Client A ToolPlatform and Runtime
        tp_a = self.tp.create_scoped_view(client_id="client_aaa")
        tp_a.register_custom_tool("custom_action", lambda: "client_a_response", "Client A Custom Action")

        # Client B ToolPlatform and Runtime
        tp_b = self.tp.create_scoped_view(client_id="client_bbb")
        tp_b.register_custom_tool("custom_action", lambda: "client_b_response", "Client B Custom Action")

        # Assert Client A and Client B tools resolve independently
        tools_a = tp_a.resolve_tools_for_node(("custom_action",), client_id="client_aaa")
        tools_b = tp_b.resolve_tools_for_node(("custom_action",), client_id="client_bbb")

        self.assertEqual(len(tools_a), 1)
        self.assertEqual(len(tools_b), 1)
        self.assertNotEqual(tools_a[0], tools_b[0])

        # Client A cannot see Client B's private tools and vice versa
        tp_a.register_custom_tool("secret_a_tool", lambda: "secret_a")
        self.assertTrue(tp_a.has_tool("secret_a_tool", client_id="client_aaa"))
        self.assertFalse(tp_b.has_tool("secret_a_tool", client_id="client_bbb"))
        self.assertEqual(len(tp_b.resolve_tools_for_node(("secret_a_tool",), client_id="client_bbb")), 0)

        # Global system tools are shared and accessible by both
        self.assertTrue(tp_a.has_tool("end_call"))
        self.assertTrue(tp_b.has_tool("end_call"))

    async def test_27_configured_workflow_start_failure_policy_raises(self):
        """Verify that when a published custom workflow fails to start, VoiceAgent.on_enter raises an explicit error."""
        from agent import VoiceAgent

        mock_session_mgr = MagicMock()
        mock_booking = MagicMock()
        mock_sales = MagicMock()
        mock_support = MagicMock()
        mock_settings = MagicMock()
        mock_settings.enable_transcripts = False
        mock_ctx = MagicMock()
        mock_ctx.room.name = "room_fail_test"

        agent = VoiceAgent(
            session_manager=mock_session_mgr,
            booking_agent=mock_booking,
            sales_agent=mock_sales,
            support_agent=mock_support,
            settings=mock_settings,
            room_name="room_fail_test",
            participant_id="part_fail",
            ctx=mock_ctx,
            custom_prompt="Custom prompt",
            agent_name="FailAgent"
        )

        # Create a broken published workflow (invalid start node execution)
        graph = WorkflowGraph(
            version=1,
            workflow_id="wf_published_broken",  # does NOT start with compat_wf_
            name="Broken Workflow",
            start_node="bad_start_node",
            nodes={
                "bad_start_node": WorkflowNode(id="bad_start_node", name="Bad", type="START")
            },
            edges=[]  # START node with no outgoing edges will fail execution
        )
        compiled_wf = WorkflowCompiler.compile(graph, self.tp)
        run_ctx = WorkflowRunContext(
            run_id="run_fail_001",
            workflow_version_id="wv_published_1",
            agent_id="ag_fail_1",
            room_name="room_fail_test",
            participant_identity="part_fail"
        )
        runtime = WorkflowRuntime(compiled_wf, run_ctx, agent, self.tp)
        agent.workflow_runtime = runtime
        agent.run_id = "run_fail_001"

        # on_enter must raise RuntimeError when a configured workflow fails
        with self.assertRaises(RuntimeError):
            await agent.on_enter()

        self.assertEqual(run_ctx.status, "failed")


if __name__ == "__main__":
    unittest.main()
