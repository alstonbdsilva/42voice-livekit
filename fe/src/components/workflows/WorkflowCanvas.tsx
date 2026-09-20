import React, { useCallback, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  Connection,
  addEdge,
  useReactFlow,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { nodeTypes } from "./nodes";
import { getCustomNodeType } from "./serializer";

interface WorkflowCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  onSelectNode: (node: Node | null) => void;
  onSelectEdge: (edge: Edge | null) => void;
  onAddNodeAtPosition: (type: "START" | "AGENT" | "CONDITION" | "END", position: { x: number; y: number }) => void;
  disabled?: boolean;
}

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  setEdges,
  onSelectNode,
  onSelectEdge,
  onAddNodeAtPosition,
  disabled,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  const onConnect = useCallback(
    (params: Connection) => {
      if (disabled) return;
      const sourceNode = nodes.find((n) => n.id === params.source);
      let edgeType = "semantic";
      let label: string | undefined = undefined;

      if (sourceNode?.type === "startNode") {
        edgeType = "default";
      } else if (sourceNode?.type === "conditionNode") {
        edgeType = "deterministic";
        if (params.sourceHandle === "true") label = "TRUE";
        else if (params.sourceHandle === "false") label = "FALSE";
        else if (params.sourceHandle === "error") label = "ERROR";
      }

      setEdges((eds) =>
        addEdge(
          {
            ...params,
            id: `edge_${params.source}_${params.sourceHandle || "default"}_to_${params.target}`,
            type: "smoothstep",
            animated: edgeType === "semantic",
            label,
            data: {
              type: edgeType,
              description: label ? `Branch: ${label}` : "",
              rawEdge: {
                id: `edge_${params.source}_${params.sourceHandle || "default"}_to_${params.target}`,
                source: params.source,
                target: params.target,
                type: edgeType,
                description: label ? `Branch: ${label}` : "",
              },
            },
          },
          eds
        )
      );
    },
    [disabled, nodes, setEdges]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (disabled) return;

      const type = event.dataTransfer.getData("application/reactflow") as
        | "START"
        | "AGENT"
        | "CONDITION"
        | "END";

      if (!type) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      onAddNodeAtPosition(type, position);
    },
    [disabled, screenToFlowPosition, onAddNodeAtPosition]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectEdge(null);
      onSelectNode(node);
    },
    [onSelectNode, onSelectEdge]
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      onSelectNode(null);
      onSelectEdge(edge);
    },
    [onSelectNode, onSelectEdge]
  );

  const onPaneClick = useCallback(() => {
    onSelectNode(null);
    onSelectEdge(null);
  }, [onSelectNode, onSelectEdge]);

  return (
    <div ref={reactFlowWrapper} className="w-full h-full flex-1 bg-zinc-50 relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={disabled ? undefined : onNodesChange}
        onEdgesChange={disabled ? undefined : onEdgesChange}
        onConnect={disabled ? undefined : onConnect}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodesDraggable={!disabled}
        nodesConnectable={!disabled}
        elementsSelectable={true}
        fitView
        snapToGrid={true}
        snapGrid={[15, 15]}
        defaultEdgeOptions={{
          type: "smoothstep",
          style: { strokeWidth: 2, stroke: "#6366f1" },
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#d4d4d8" />
        <Controls showInteractive={!disabled} className="bg-white border border-zinc-200 shadow-sm rounded-lg" />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          className="bg-white border border-zinc-200 shadow-sm rounded-lg"
          nodeColor={(n) => {
            if (n.type === "startNode") return "#10b981";
            if (n.type === "agentNode") return "#6366f1";
            if (n.type === "conditionNode") return "#f59e0b";
            if (n.type === "endNode") return "#f43f5e";
            return "#94a3b8";
          }}
        />
      </ReactFlow>
    </div>
  );
};

export default WorkflowCanvas;
