import { Node, Edge } from "@xyflow/react";
import {
  WorkflowDefinition,
  WorkflowUIMetadata,
  WorkflowNode,
  WorkflowEdge,
} from "@/types/workflow";

export interface WorkflowEditorState {
  nodes: Node[];
  edges: Edge[];
}

/**
 * Maps backend node type to React Flow custom node component type.
 */
export function getCustomNodeType(type: string): string {
  const upper = (type || "").toUpperCase();
  switch (upper) {
    case "START":
      return "startNode";
    case "AGENT":
      return "agentNode";
    case "CONDITION":
      return "conditionNode";
    case "END":
      return "endNode";
    default:
      return "unknownNode";
  }
}

/**
 * Deserializes backend WorkflowDefinition & WorkflowUIMetadata into React Flow nodes & edges.
 */
export function deserializeWorkflow(
  definition: WorkflowDefinition,
  uiMetadata?: WorkflowUIMetadata
): WorkflowEditorState {
  const nodesRecord = definition.nodes || {};
  const edgesList = definition.edges || [];
  const positions = uiMetadata?.positions || {};

  const nodes: Node[] = [];
  const nodeEntries = Object.entries(nodesRecord);

  nodeEntries.forEach(([nodeId, nodeData], index) => {
    const rawNode: WorkflowNode = {
      ...nodeData,
      id: nodeId,
      name: nodeData.name || nodeId,
      type: (nodeData.type || "AGENT").toUpperCase(),
      config: nodeData.config || {},
      tools: nodeData.tools || [],
    };

    // Calculate fallback position if not saved in ui_metadata
    const defaultX = 100 + (index % 4) * 320;
    const defaultY = 150 + Math.floor(index / 4) * 220;
    const pos = positions[nodeId] || { x: defaultX, y: defaultY };

    nodes.push({
      id: nodeId,
      type: getCustomNodeType(rawNode.type),
      position: { x: pos.x, y: pos.y },
      data: {
        label: rawNode.name,
        name: rawNode.name,
        type: rawNode.type,
        prompt: rawNode.prompt || "",
        tools: rawNode.tools || [],
        condition: rawNode.condition || rawNode.config?.condition || null,
        on_true: rawNode.on_true || rawNode.config?.on_true || null,
        on_false: rawNode.on_false || rawNode.config?.on_false || null,
        on_error: rawNode.on_error || rawNode.config?.on_error || null,
        config: rawNode.config || {},
        isStartNode: definition.start_node === nodeId || rawNode.type === "START",
        rawNode: { ...rawNode }, // Deep preservation of unknown/custom fields
      },
    });
  });

  const edges: Edge[] = edgesList.map((edge) => {
    let sourceHandle: string | undefined = undefined;
    const sourceNode = nodesRecord[edge.source];

    if (sourceNode && sourceNode.type === "CONDITION") {
      if (edge.target === sourceNode.on_true || edge.target === sourceNode.config?.on_true) {
        sourceHandle = "true";
      } else if (edge.target === sourceNode.on_false || edge.target === sourceNode.config?.on_false) {
        sourceHandle = "false";
      } else if (edge.target === sourceNode.on_error || edge.target === sourceNode.config?.on_error) {
        sourceHandle = "error";
      }
    }

    return {
      id: edge.id || `edge_${edge.source}_to_${edge.target}`,
      source: edge.source,
      target: edge.target,
      sourceHandle,
      type: "smoothstep",
      animated: edge.type === "semantic",
      label: edge.description || (sourceHandle ? sourceHandle.toUpperCase() : undefined),
      data: {
        rawEdge: { ...edge },
        type: edge.type || "semantic",
        description: edge.description || "",
        condition: edge.condition || null,
        priority: edge.priority ?? 10,
        required_variables: edge.required_variables || [],
        metadata: edge.metadata || {},
      },
    };
  });

  return { nodes, edges };
}

/**
 * Serializes React Flow nodes & edges back into canonical executable WorkflowDefinition & WorkflowUIMetadata.
 */
export function serializeWorkflow(
  nodes: Node[],
  edges: Edge[],
  baseDefinition: WorkflowDefinition,
  currentViewport?: { x: number; y: number; zoom: number }
): { definition: WorkflowDefinition; ui_metadata: WorkflowUIMetadata } {
  const nodesMap: Record<string, WorkflowNode> = {};
  const positionsMap: Record<string, { x: number; y: number }> = {};

  let startNodeId = baseDefinition.start_node;

  // Build nodes dictionary
  nodes.forEach((node) => {
    const rawNode: WorkflowNode = node.data?.rawNode ? { ...(node.data.rawNode as WorkflowNode) } : {
      id: node.id,
      name: (node.data?.name as string) || node.id,
      type: ((node.data?.type as string) || "AGENT").toUpperCase(),
      config: {},
    };

    const nodeType = ((node.data?.type as string) || rawNode.type || "AGENT").toUpperCase();
    const nodeName = (node.data?.name as string) || (node.data?.label as string) || rawNode.name || node.id;
    const nodePrompt = node.data?.prompt !== undefined ? (node.data.prompt as string) : rawNode.prompt;
    const nodeTools = Array.isArray(node.data?.tools) ? (node.data.tools as string[]) : (rawNode.tools || []);
    const nodeConfig = { ...(rawNode.config || {}), ...(node.data?.config as Record<string, any> || {}) };

    if (nodeType === "START") {
      startNodeId = node.id;
      // Find default outgoing edge from START node
      const startEdge = edges.find((e) => e.source === node.id);
      if (startEdge) {
        nodeConfig.next_node = startEdge.target;
      }
    }

    const conditionSpec = node.data?.condition !== undefined ? node.data.condition : (rawNode.condition || null);
    const onTrue = node.data?.on_true !== undefined ? (node.data.on_true as string) : (rawNode.on_true || null);
    const onFalse = node.data?.on_false !== undefined ? (node.data.on_false as string) : (rawNode.on_false || null);
    const onError = node.data?.on_error !== undefined ? (node.data.on_error as string) : (rawNode.on_error || null);

    if (nodeType === "CONDITION") {
      nodeConfig.condition = conditionSpec;
      nodeConfig.on_true = onTrue;
      nodeConfig.on_false = onFalse;
      if (onError) {
        nodeConfig.on_error = onError;
      }
    }

    const serializedNode: WorkflowNode = {
      ...rawNode,
      id: node.id,
      name: nodeName,
      type: nodeType,
      prompt: nodePrompt ?? null,
      tools: nodeTools,
      condition: conditionSpec,
      on_true: onTrue,
      on_false: onFalse,
      on_error: onError,
      config: nodeConfig,
    };

    nodesMap[node.id] = serializedNode;
    positionsMap[node.id] = {
      x: Math.round(node.position.x),
      y: Math.round(node.position.y),
    };
  });

  // Build edges array
  const serializedEdges: WorkflowEdge[] = edges.map((edge) => {
    const rawEdge = (edge.data?.rawEdge as WorkflowEdge) || {};
    const sourceNode = nodesMap[edge.source];
    let edgeType = (edge.data?.type as string) || rawEdge.type || "semantic";

    if (sourceNode && sourceNode.type === "START") {
      edgeType = "default";
    } else if (sourceNode && sourceNode.type === "CONDITION") {
      edgeType = "deterministic";
    }

    return {
      ...rawEdge,
      id: edge.id || `edge_${edge.source}_to_${edge.target}`,
      source: edge.source,
      target: edge.target,
      type: edgeType,
      description: (edge.data?.description as string) || (typeof edge.label === "string" ? edge.label : "") || rawEdge.description || "",
      condition: edge.data?.condition !== undefined ? edge.data.condition : (rawEdge.condition || null),
      priority: typeof edge.data?.priority === "number" ? edge.data.priority : (rawEdge.priority ?? 10),
      required_variables: Array.isArray(edge.data?.required_variables) ? edge.data.required_variables : (rawEdge.required_variables || []),
      metadata: (edge.data?.metadata as Record<string, any>) || rawEdge.metadata || {},
    };
  });

  const definition: WorkflowDefinition = {
    ...baseDefinition,
    version: baseDefinition.version || 1,
    workflow_id: baseDefinition.workflow_id,
    name: baseDefinition.name || "Untitled Workflow",
    start_node: startNodeId || Object.keys(nodesMap)[0] || "start_node",
    global_prompt: baseDefinition.global_prompt || "",
    variables: baseDefinition.variables || {},
    nodes: nodesMap,
    edges: serializedEdges,
    model_config: baseDefinition.model_config || {},
    execution_config: baseDefinition.execution_config || {},
  };

  const ui_metadata: WorkflowUIMetadata = {
    positions: positionsMap,
    viewport: currentViewport || { x: 0, y: 0, zoom: 1 },
  };

  return { definition, ui_metadata };
}
