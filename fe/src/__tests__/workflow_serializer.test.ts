import {
  deserializeWorkflow,
  serializeWorkflow,
} from "../components/workflows/serializer";
import {
  WorkflowDefinition,
  WorkflowUIMetadata,
} from "../types/workflow";

describe("Workflow Serializer & Deserializer", () => {
  const sampleDefinition: WorkflowDefinition = {
    version: 1,
    workflow_id: "wf_test_123",
    name: "Customer Support Workflow",
    start_node: "start_node",
    global_prompt: "You are a professional AI voice representative.",
    variables: {
      account_status: "active",
      vip: false,
    },
    nodes: {
      start_node: {
        id: "start_node",
        name: "Start Step",
        type: "START",
        prompt: "",
        tools: [],
        config: { next_node: "agent_node" },
      },
      agent_node: {
        id: "agent_node",
        name: "Greeting & Triage",
        type: "AGENT",
        prompt: "Welcome the user and ask for their query.",
        tools: ["check_account", "end_call"],
        config: { max_retries: 3 },
      },
      condition_node: {
        id: "condition_node",
        name: "Check VIP Status",
        type: "CONDITION",
        condition: {
          variable: "vip",
          operator: "equals",
          value: true,
        },
        on_true: "vip_agent",
        on_false: "end_node",
        on_error: "end_node",
        config: {
          condition: { variable: "vip", operator: "equals", value: true },
          on_true: "vip_agent",
          on_false: "end_node",
          on_error: "end_node",
        },
      },
      vip_agent: {
        id: "vip_agent",
        name: "VIP Specialist",
        type: "AGENT",
        prompt: "Provide white-glove VIP assistance.",
        tools: ["transfer_call"],
        config: {},
      },
      end_node: {
        id: "end_node",
        name: "End Conversation",
        type: "END",
        prompt: "Thank you for contacting us. Goodbye!",
        tools: ["end_call"],
        config: {},
      },
      unknown_custom_node: {
        id: "unknown_custom_node",
        name: "Future AI Service Node",
        type: "FUTURE_VOICE_GATEWAY",
        tools: ["gateway_dispatch"],
        config: {
          gateway_endpoint: "https://gateway.example.com",
          auth_mode: "bearer",
        },
        custom_unsupported_key: "custom_unsupported_value",
      },
    },
    edges: [
      {
        id: "edge_start_to_agent",
        source: "start_node",
        target: "agent_node",
        type: "default",
        description: "",
      },
      {
        id: "edge_agent_to_cond",
        source: "agent_node",
        target: "condition_node",
        type: "semantic",
        description: "When the customer has identified their account number",
      },
      {
        id: "edge_cond_true_to_vip",
        source: "condition_node",
        target: "vip_agent",
        type: "deterministic",
        description: "Branch: TRUE",
      },
      {
        id: "edge_cond_false_to_end",
        source: "condition_node",
        target: "end_node",
        type: "deterministic",
        description: "Branch: FALSE",
      },
      {
        id: "edge_vip_to_custom",
        source: "vip_agent",
        target: "unknown_custom_node",
        type: "semantic",
        description: "Hand off to future gateway",
        metadata: {
          custom_edge_attr: 42,
          routing_tag: "fast_lane",
        },
      },
    ],
  };

  const sampleUIMetadata: WorkflowUIMetadata = {
    positions: {
      start_node: { x: 100, y: 150 },
      agent_node: { x: 400, y: 150 },
      condition_node: { x: 750, y: 150 },
      vip_agent: { x: 1100, y: 100 },
      end_node: { x: 1100, y: 300 },
      unknown_custom_node: { x: 1450, y: 100 },
    },
    viewport: { x: 50, y: 20, zoom: 0.85 },
  };

  test("1. Backend nodes map deserializes cleanly to React Flow nodes array", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);

    expect(nodes).toHaveLength(6);
    expect(edges).toHaveLength(5);

    // Verify node IDs match keys
    const nodeIds = nodes.map((n) => n.id);
    expect(nodeIds).toContain("start_node");
    expect(nodeIds).toContain("agent_node");
    expect(nodeIds).toContain("condition_node");
    expect(nodeIds).toContain("vip_agent");
    expect(nodeIds).toContain("end_node");
    expect(nodeIds).toContain("unknown_custom_node");

    // Verify positions preserved from ui_metadata
    const startNode = nodes.find((n) => n.id === "start_node");
    expect(startNode?.position).toEqual({ x: 100, y: 150 });
  });

  test("2. Serializer converts React Flow array back into backend Record<string, WorkflowNode>", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition, ui_metadata } = serializeWorkflow(
      nodes,
      edges,
      sampleDefinition,
      sampleUIMetadata.viewport
    );

    expect(typeof definition.nodes).toBe("object");
    expect(Array.isArray(definition.nodes)).toBe(false);
    expect(Object.keys(definition.nodes)).toHaveLength(6);
    expect(definition.nodes.start_node).toBeDefined();
    expect(definition.nodes.agent_node.name).toBe("Greeting & Triage");
  });

  test("3. START transition semantics are strictly preserved", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition } = serializeWorkflow(nodes, edges, sampleDefinition);

    // Verify definition.start_node
    expect(definition.start_node).toBe("start_node");

    // Verify config.next_node on start node
    expect(definition.nodes.start_node.config?.next_node).toBe("agent_node");

    // Verify default outgoing edge
    const startEdge = definition.edges.find((e) => e.source === "start_node");
    expect(startEdge).toBeDefined();
    expect(startEdge?.target).toBe("agent_node");
    expect(startEdge?.type).toBe("default");
  });

  test("4. CONDITION node exact backend schema and routing targets are preserved", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition } = serializeWorkflow(nodes, edges, sampleDefinition);

    const condNode = definition.nodes.condition_node;
    expect(condNode.type).toBe("CONDITION");
    expect(condNode.condition).toEqual({
      variable: "vip",
      operator: "equals",
      value: true,
    });
    expect(condNode.on_true).toBe("vip_agent");
    expect(condNode.on_false).toBe("end_node");
    expect(condNode.on_error).toBe("end_node");
    expect(condNode.config?.on_true).toBe("vip_agent");
    expect(condNode.config?.on_false).toBe("end_node");
  });

  test("5. END node required fields (tools: ['end_call']) are preserved", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition } = serializeWorkflow(nodes, edges, sampleDefinition);

    const endNode = definition.nodes.end_node;
    expect(endNode.type).toBe("END");
    expect(endNode.tools).toContain("end_call");
    expect(endNode.prompt).toBe("Thank you for contacting us. Goodbye!");
  });

  test("6. Unknown node types and arbitrary fields roundtrip non-destructively", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);

    // Verify mapped to unknownNode component
    const unknownNode = nodes.find((n) => n.id === "unknown_custom_node");
    expect(unknownNode?.type).toBe("unknownNode");

    // Roundtrip back to definition
    const { definition } = serializeWorkflow(nodes, edges, sampleDefinition);
    const serializedUnknown = definition.nodes.unknown_custom_node;

    expect(serializedUnknown.type).toBe("FUTURE_VOICE_GATEWAY");
    expect(serializedUnknown.tools).toEqual(["gateway_dispatch"]);
    expect(serializedUnknown.config?.gateway_endpoint).toBe("https://gateway.example.com");
    expect(serializedUnknown.custom_unsupported_key).toBe("custom_unsupported_value");
  });

  test("7. Unknown edge metadata roundtrips non-destructively", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition } = serializeWorkflow(nodes, edges, sampleDefinition);

    const customEdge = definition.edges.find((e) => e.id === "edge_vip_to_custom");
    expect(customEdge).toBeDefined();
    expect(customEdge?.metadata?.custom_edge_attr).toBe(42);
    expect(customEdge?.metadata?.routing_tag).toBe("fast_lane");
  });

  test("8. UI metadata (coordinates & viewport) remains strictly separated from executable definition", () => {
    const { nodes, edges } = deserializeWorkflow(sampleDefinition, sampleUIMetadata);
    const { definition, ui_metadata } = serializeWorkflow(
      nodes,
      edges,
      sampleDefinition,
      { x: 100, y: 50, zoom: 1.0 }
    );

    // Executable definition nodes must NOT have x/y in config
    expect(definition.nodes.agent_node.config?.x).toBeUndefined();
    expect(definition.nodes.agent_node.config?.y).toBeUndefined();

    // ui_metadata contains coordinates and viewport
    expect(ui_metadata.positions.agent_node).toEqual({ x: 400, y: 150 });
    expect(ui_metadata.viewport).toEqual({ x: 100, y: 50, zoom: 1.0 });
  });
});
