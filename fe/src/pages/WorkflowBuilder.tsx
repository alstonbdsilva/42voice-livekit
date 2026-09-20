import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import {
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  useReactFlow,
} from "@xyflow/react";
import { toast } from "sonner";
import {
  WorkflowDefinition,
  WorkflowDraft,
  WorkflowVersion,
  ValidationResponse,
  WorkflowUIMetadata,
} from "@/types/workflow";
import { WorkflowService } from "@/services/workflow.service";
import {
  deserializeWorkflow,
  serializeWorkflow,
  getCustomNodeType,
} from "@/components/workflows/serializer";
import WorkflowToolbar from "@/components/workflows/WorkflowToolbar";
import NodePalette from "@/components/workflows/NodePalette";
import NodePropertiesPanel from "@/components/workflows/NodePropertiesPanel";
import WorkflowCanvas from "@/components/workflows/WorkflowCanvas";
import ValidationModal from "@/components/workflows/ValidationModal";
import VersionHistoryModal from "@/components/workflows/VersionHistoryModal";
import PublishDialog from "@/components/workflows/PublishDialog";

function WorkflowBuilderInner() {
  const { id: workflowId } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getViewport, fitView, setCenter } = useReactFlow();

  const [workflow, setWorkflow] = useState<any>(null);
  const [draft, setDraft] = useState<WorkflowDraft | null>(null);
  const [baseDefinition, setBaseDefinition] = useState<WorkflowDefinition | null>(null);
  const [activeVersion, setActiveVersion] = useState<WorkflowVersion | null>(null);

  const [nodes, setNodes, onNodesChangeOriginal] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChangeOriginal] = useEdgesState<Edge>([]);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const [isDirty, setIsDirty] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const [validationResult, setValidationResult] = useState<ValidationResponse | null>(null);
  const [isValidationModalOpen, setIsValidationModalOpen] = useState(false);
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const [isPublishDialogOpen, setIsPublishDialogOpen] = useState(false);

  const isReadOnly = activeVersion !== null;
  const activeVersionNumber = activeVersion?.version_number ?? null;

  // Track user modifications safely without false dirty on initial load
  const onNodesChange = useCallback(
    (changes: any) => {
      onNodesChangeOriginal(changes);
      // Ignore initial dimension/position measuring changes from triggering dirty
      const hasMeaningfulChange = changes.some(
        (c: any) => c.type === "position" && c.dragging === false || c.type === "remove" || c.type === "add"
      );
      if (hasMeaningfulChange && !isReadOnly) {
        setIsDirty(true);
      }
    },
    [onNodesChangeOriginal, isReadOnly]
  );

  const onEdgesChange = useCallback(
    (changes: any) => {
      onEdgesChangeOriginal(changes);
      if (changes.length > 0 && !isReadOnly) {
        setIsDirty(true);
      }
    },
    [onEdgesChangeOriginal, isReadOnly]
  );

  // Load workflow container and draft or version snapshot
  const loadWorkflowData = useCallback(async () => {
    if (!workflowId) return;
    setIsLoading(true);
    try {
      const [wfSummary, draftData] = await Promise.all([
        WorkflowService.getWorkflow(workflowId),
        WorkflowService.getDraft(workflowId),
      ]);
      setWorkflow(wfSummary);
      setDraft(draftData);
      setBaseDefinition(draftData.definition);

      const { nodes: initialNodes, edges: initialEdges } = deserializeWorkflow(
        draftData.definition,
        draftData.ui_metadata
      );
      setNodes(initialNodes);
      setEdges(initialEdges);
      setIsDirty(false);
    } catch (err: any) {
      toast.error(err?.response?.data?.message || "Failed to load workflow draft.");
    } finally {
      setIsLoading(false);
    }
  }, [workflowId, setNodes, setEdges]);

  useEffect(() => {
    loadWorkflowData();
  }, [loadWorkflowData]);

  // Handle keyboard shortcut (Ctrl+S / Cmd+S)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (!isReadOnly && isDirty && !isSaving) {
          handleSaveDraft();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  // Selected node and edge helpers
  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) || null,
    [nodes, selectedNodeId]
  );
  const selectedEdge = useMemo(
    () => edges.find((e) => e.id === selectedEdgeId) || null,
    [edges, selectedEdgeId]
  );

  // Update node data
  const handleUpdateNodeData = useCallback(
    (nodeId: string, dataUpdates: Record<string, any>) => {
      if (isReadOnly) return;
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: {
                ...node.data,
                ...dataUpdates,
              },
            };
          }
          return node;
        })
      );
      setIsDirty(true);
    },
    [isReadOnly, setNodes]
  );

  // Update edge data
  const handleUpdateEdgeData = useCallback(
    (edgeId: string, edgeUpdates: Record<string, any>) => {
      if (isReadOnly) return;
      setEdges((eds) =>
        eds.map((edge) => {
          if (edge.id === edgeId) {
            return {
              ...edge,
              ...edgeUpdates,
              data: {
                ...edge.data,
                ...edgeUpdates,
              },
            };
          }
          return edge;
        })
      );
      setIsDirty(true);
    },
    [isReadOnly, setEdges]
  );

  // Add new node at canvas position
  const handleAddNodeAtPosition = useCallback(
    (type: "START" | "AGENT" | "CONDITION" | "END", position: { x: number; y: number }) => {
      if (isReadOnly) return;

      const count = nodes.filter((n) => (n.data?.type as string) === type).length + 1;
      const typeLower = type.toLowerCase();
      const newId = `${typeLower}_${Date.now().toString(36)}`;
      let defaultName = `${type.charAt(0) + type.slice(1).toLowerCase()} ${count}`;

      let defaultPrompt: string | undefined = undefined;
      let defaultTools: string[] = [];

      if (type === "START") {
        defaultName = "Start";
      } else if (type === "AGENT") {
        defaultPrompt = "Provide helpful guidance to the caller.";
        defaultTools = ["end_call"];
      } else if (type === "CONDITION") {
        defaultName = "Check Condition";
      } else if (type === "END") {
        defaultName = "End Call";
        defaultPrompt = "Thank you for calling. Goodbye!";
        defaultTools = ["end_call"];
      }

      const newNode: Node = {
        id: newId,
        type: getCustomNodeType(type),
        position,
        data: {
          label: defaultName,
          name: defaultName,
          type,
          prompt: defaultPrompt,
          tools: defaultTools,
          condition: type === "CONDITION" ? { variable: "status", operator: "equals", value: "active" } : null,
          config: {},
          isStartNode: type === "START" && !nodes.some((n) => n.data?.type === "START"),
        },
      };

      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(newId);
      setSelectedEdgeId(null);
      setIsDirty(true);
    },
    [isReadOnly, nodes, setNodes]
  );

  // Delete node
  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      if (isReadOnly) return;
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null);
      }
      setIsDirty(true);
    },
    [isReadOnly, selectedNodeId, setNodes, setEdges]
  );

  // Delete edge
  const handleDeleteEdge = useCallback(
    (edgeId: string) => {
      if (isReadOnly) return;
      setEdges((eds) => eds.filter((e) => e.id !== edgeId));
      if (selectedEdgeId === edgeId) {
        setSelectedEdgeId(null);
      }
      setIsDirty(true);
    },
    [isReadOnly, selectedEdgeId, setEdges]
  );

  // Auto layout nodes neatly
  const handleAutoLayout = useCallback(() => {
    setNodes((nds) => {
      const startNodes = nds.filter((n) => n.data?.type === "START");
      const agentNodes = nds.filter((n) => n.data?.type === "AGENT");
      const condNodes = nds.filter((n) => n.data?.type === "CONDITION");
      const endNodes = nds.filter((n) => n.data?.type === "END");
      const otherNodes = nds.filter(
        (n) => !["START", "AGENT", "CONDITION", "END"].includes((n.data?.type as string) || "")
      );

      const ordered = [...startNodes, ...agentNodes, ...condNodes, ...otherNodes, ...endNodes];
      return ordered.map((n, idx) => ({
        ...n,
        position: {
          x: 100 + (idx % 3) * 360,
          y: 120 + Math.floor(idx / 3) * 260,
        },
      }));
    });
    setTimeout(() => fitView({ duration: 400 }), 50);
    if (!isReadOnly) setIsDirty(true);
  }, [fitView, isReadOnly, setNodes]);

  // Focus and center on a specific node (used by validation error clicks)
  const handleFocusNode = useCallback(
    (nodeId: string) => {
      const target = nodes.find((n) => n.id === nodeId);
      if (target) {
        setSelectedNodeId(nodeId);
        setSelectedEdgeId(null);
        setCenter(target.position.x + 120, target.position.y + 60, { zoom: 1.2, duration: 600 });
      }
    },
    [nodes, setCenter]
  );

  // SAVE DRAFT
  const handleSaveDraft = useCallback(async (): Promise<boolean> => {
    if (!workflowId || !baseDefinition) return false;
    setIsSaving(true);
    try {
      const currentViewport = getViewport();
      const { definition, ui_metadata } = serializeWorkflow(
        nodes,
        edges,
        baseDefinition,
        currentViewport
      );

      const updatedDraft = await WorkflowService.saveDraft(workflowId, definition, ui_metadata);
      setDraft(updatedDraft);
      setBaseDefinition(updatedDraft.definition);
      setIsDirty(false);
      toast.success("Draft saved successfully.");
      return true;
    } catch (err: any) {
      toast.error(err?.response?.data?.message || "Failed to save workflow draft.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [workflowId, baseDefinition, nodes, edges, getViewport]);

  // VALIDATE GRAPH
  const handleValidate = useCallback(async (): Promise<ValidationResponse | null> => {
    if (!workflowId || !baseDefinition) return null;
    setIsValidating(true);
    try {
      const { definition } = serializeWorkflow(nodes, edges, baseDefinition);
      const res = await WorkflowService.validateWorkflow(workflowId, definition);
      setValidationResult(res);
      setIsValidationModalOpen(true);
      if (res.valid) {
        toast.success("Workflow validation passed!");
      } else {
        toast.error(`Validation found ${res.errors.length} error(s).`);
      }
      return res;
    } catch (err: any) {
      toast.error(err?.response?.data?.message || "Failed to validate workflow definition.");
      return null;
    } finally {
      setIsValidating(false);
    }
  }, [workflowId, baseDefinition, nodes, edges]);

  // PUBLISH CLICK SEQUENCE: Save if dirty -> Validate -> Open Publish Dialog
  const handlePublishClick = useCallback(async () => {
    if (isReadOnly) return;

    // 1. If dirty, save draft first
    if (isDirty) {
      const saveSuccess = await handleSaveDraft();
      if (!saveSuccess) {
        toast.error("Cannot publish: failed to save current draft changes.");
        return;
      }
    }

    // 2. Validate exact definition
    const valRes = await handleValidate();
    if (!valRes || !valRes.valid) {
      toast.error("Cannot publish: workflow definition has validation errors.");
      return;
    }

    // 3. Open publish release notes dialog
    setIsPublishDialogOpen(true);
  }, [isReadOnly, isDirty, handleSaveDraft, handleValidate]);

  // CONFIRM PUBLISH (calls backend POST /publish)
  const handleConfirmPublish = useCallback(
    async (description: string) => {
      if (!workflowId) return;
      setIsPublishing(true);
      try {
        const newVersion = await WorkflowService.publishWorkflow(workflowId, description);
        toast.success(`Workflow published successfully as Version ${newVersion.version_number}!`);
        // Refresh workflow metadata
        const wfSummary = await WorkflowService.getWorkflow(workflowId);
        setWorkflow(wfSummary);
        // Switch to inspect newly published version
        setActiveVersion(newVersion);
        const { nodes: vNodes, edges: vEdges } = deserializeWorkflow(
          newVersion.definition,
          newVersion.ui_metadata
        );
        setNodes(vNodes);
        setEdges(vEdges);
        setIsDirty(false);
      } catch (err: any) {
        throw err;
      } finally {
        setIsPublishing(false);
      }
    },
    [workflowId, setNodes, setEdges]
  );

  // Switch between Draft and a Published Version
  const handleSelectVersion = useCallback(
    (version: WorkflowVersion | null) => {
      if (version === null) {
        // Switch to working draft
        setActiveVersion(null);
        if (draft) {
          const { nodes: dNodes, edges: dEdges } = deserializeWorkflow(
            draft.definition,
            draft.ui_metadata
          );
          setNodes(dNodes);
          setEdges(dEdges);
          setBaseDefinition(draft.definition);
          setIsDirty(false);
        }
      } else {
        // Inspect published version (read-only)
        setActiveVersion(version);
        const { nodes: vNodes, edges: vEdges } = deserializeWorkflow(
          version.definition,
          version.ui_metadata
        );
        setNodes(vNodes);
        setEdges(vEdges);
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
        setIsDirty(false);
      }
    },
    [draft, setNodes, setEdges]
  );

  // Restore a published version into the draft
  const handleRestoreVersionToDraft = useCallback(
    async (version: WorkflowVersion) => {
      if (!workflowId) return;
      try {
        const updatedDraft = await WorkflowService.saveDraft(
          workflowId,
          version.definition,
          version.ui_metadata
        );
        setDraft(updatedDraft);
        setBaseDefinition(updatedDraft.definition);
        setActiveVersion(null);
        const { nodes: dNodes, edges: dEdges } = deserializeWorkflow(
          updatedDraft.definition,
          updatedDraft.ui_metadata
        );
        setNodes(dNodes);
        setEdges(dEdges);
        setIsDirty(false);
        toast.success(`Draft successfully restored from Version ${version.version_number}.`);
      } catch (err: any) {
        toast.error(err?.response?.data?.message || "Failed to restore version to draft.");
      }
    },
    [workflowId, setNodes, setEdges]
  );

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-zinc-50">
        <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-xs font-medium text-zinc-600">Loading Workflow Canvas...</p>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-white">
      {/* Top Toolbar */}
      <WorkflowToolbar
        workflowName={workflow?.name || "Workflow Builder"}
        isDirty={isDirty}
        isSaving={isSaving}
        isValidating={isValidating}
        isPublishing={isPublishing}
        activeVersionNumber={activeVersionNumber}
        isReadOnly={isReadOnly}
        onSaveDraft={handleSaveDraft}
        onValidate={handleValidate}
        onPublishClick={handlePublishClick}
        onAutoLayout={handleAutoLayout}
        onOpenVersionHistory={() => setIsVersionModalOpen(true)}
      />

      {/* Main Builder workspace: Left Palette | Canvas | Right Properties */}
      <div className="flex-1 flex overflow-hidden relative">
        <NodePalette
          disabled={isReadOnly}
          onAddNode={(type) =>
            handleAddNodeAtPosition(type, {
              x: 250 + Math.random() * 80,
              y: 200 + Math.random() * 80,
            })
          }
        />

        <WorkflowCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          setEdges={setEdges}
          onSelectNode={(node) => {
            setSelectedNodeId(node ? node.id : null);
            if (node) setSelectedEdgeId(null);
          }}
          onSelectEdge={(edge) => {
            setSelectedEdgeId(edge ? edge.id : null);
            if (edge) setSelectedNodeId(null);
          }}
          onAddNodeAtPosition={handleAddNodeAtPosition}
          disabled={isReadOnly}
        />

        <NodePropertiesPanel
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
          allNodes={nodes}
          onUpdateNodeData={handleUpdateNodeData}
          onUpdateEdgeData={handleUpdateEdgeData}
          onDeleteNode={handleDeleteNode}
          onDeleteEdge={handleDeleteEdge}
          onClose={() => {
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
          disabled={isReadOnly}
        />
      </div>

      {/* Modals & Dialogs */}
      <ValidationModal
        isOpen={isValidationModalOpen}
        onClose={() => setIsValidationModalOpen(false)}
        validationResult={validationResult}
        onFocusNode={handleFocusNode}
      />

      <VersionHistoryModal
        isOpen={isVersionModalOpen}
        onClose={() => setIsVersionModalOpen(false)}
        workflowId={workflowId || ""}
        currentVersionNumber={activeVersionNumber}
        onSelectVersion={handleSelectVersion}
        onRestoreVersionToDraft={handleRestoreVersionToDraft}
      />

      <PublishDialog
        isOpen={isPublishDialogOpen}
        onClose={() => setIsPublishDialogOpen(false)}
        onConfirmPublish={handleConfirmPublish}
        isPublishing={isPublishing}
      />
    </div>
  );
}

export default function WorkflowBuilder() {
  return (
    <ReactFlowProvider>
      <WorkflowBuilderInner />
    </ReactFlowProvider>
  );
}
