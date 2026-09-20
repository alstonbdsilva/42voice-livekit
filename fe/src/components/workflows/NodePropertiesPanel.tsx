import React from "react";
import { Node, Edge } from "@xyflow/react";
import { Trash2, X, Plus, Sparkles, AlertCircle } from "lucide-react";
import { ConditionOperator } from "@/types/workflow";

interface NodePropertiesPanelProps {
  selectedNode: Node | null;
  selectedEdge: Edge | null;
  allNodes: Node[];
  onUpdateNodeData: (nodeId: string, dataUpdates: Record<string, any>) => void;
  onUpdateEdgeData: (edgeId: string, edgeUpdates: Record<string, any>) => void;
  onDeleteNode: (nodeId: string) => void;
  onDeleteEdge: (edgeId: string) => void;
  onClose: () => void;
  disabled?: boolean;
}

const CONDITION_OPERATORS: { value: ConditionOperator; label: string; needsValue: boolean }[] = [
  { value: "equals", label: "Equals (==)", needsValue: true },
  { value: "not_equals", label: "Not Equals (!=)", needsValue: true },
  { value: "greater_than", label: "Greater Than (>)", needsValue: true },
  { value: "greater_than_or_equal", label: "Greater Than or Equal (>=)", needsValue: true },
  { value: "less_than", label: "Less Than (<)", needsValue: true },
  { value: "less_than_or_equal", label: "Less Than or Equal (<=)", needsValue: true },
  { value: "contains", label: "Contains / Substring", needsValue: true },
  { value: "exists", label: "Exists (Not Null)", needsValue: false },
  { value: "is_empty", label: "Is Empty (Null / Blank)", needsValue: false },
  { value: "is_not_empty", label: "Is Not Empty", needsValue: false },
  { value: "in", label: "In Array / List", needsValue: true },
  { value: "not_in", label: "Not In Array / List", needsValue: true },
];

export const NodePropertiesPanel: React.FC<NodePropertiesPanelProps> = ({
  selectedNode,
  selectedEdge,
  allNodes,
  onUpdateNodeData,
  onUpdateEdgeData,
  onDeleteNode,
  onDeleteEdge,
  onClose,
  disabled,
}) => {
  if (!selectedNode && !selectedEdge) {
    return (
      <aside className="w-80 bg-white border-l border-zinc-200 flex flex-col h-full z-10 select-none">
        <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">Properties</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-zinc-400">
          <Sparkles className="w-8 h-8 mb-2 stroke-1 text-zinc-300" />
          <div className="text-sm font-medium text-zinc-600">No Selection</div>
          <p className="text-xs text-zinc-400 mt-1 max-w-[200px]">
            Click a node or edge on the canvas to inspect and edit its properties.
          </p>
        </div>
      </aside>
    );
  }

  // Render Edge properties
  if (selectedEdge) {
    const edgeData = selectedEdge.data || {};
    const description = (edgeData.description as string) || (typeof selectedEdge.label === "string" ? selectedEdge.label : "");
    const edgeType = (edgeData.type as string) || "semantic";

    return (
      <aside className="w-80 bg-white border-l border-zinc-200 flex flex-col h-full z-10">
        <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500">Edge Transition</span>
            <div className="text-sm font-semibold text-zinc-900 truncate">
              {selectedEdge.source} → {selectedEdge.target}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Transition Description / Intent</label>
            <textarea
              disabled={disabled}
              value={description}
              onChange={(e) =>
                onUpdateEdgeData(selectedEdge.id, {
                  description: e.target.value,
                  label: e.target.value,
                })
              }
              rows={3}
              placeholder="e.g. When the user asks to speak with billing support"
              className="w-full text-xs p-2 rounded-md border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none"
            />
            <p className="text-[11px] text-zinc-400 mt-1">
              For semantic transitions, the LLM will use this description to trigger a transition tool.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Edge Type</label>
            <select
              disabled={disabled}
              value={edgeType}
              onChange={(e) => onUpdateEdgeData(selectedEdge.id, { type: e.target.value })}
              className="w-full text-xs p-2 rounded-md border border-zinc-300 bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900"
            >
              <option value="semantic">Semantic (LLM Triggered)</option>
              <option value="deterministic">Deterministic (Rule-based)</option>
              <option value="default">Default / Direct</option>
              <option value="tool">Tool Result</option>
            </select>
          </div>
        </div>

        <div className="p-4 border-t border-zinc-100">
          <button
            disabled={disabled}
            onClick={() => onDeleteEdge(selectedEdge.id)}
            className="w-full flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete Transition
          </button>
        </div>
      </aside>
    );
  }

  // Render Node properties
  const nodeData = selectedNode?.data || {};
  const nodeType = ((nodeData.type as string) || "AGENT").toUpperCase();
  const name = (nodeData.name as string) || (nodeData.label as string) || selectedNode?.id || "";
  const prompt = (nodeData.prompt as string) || "";
  const tools = (nodeData.tools as string[]) || [];
  const condition = (nodeData.condition as any) || { variable: "", operator: "equals", value: "" };
  const onTrue = (nodeData.on_true as string) || "";
  const onFalse = (nodeData.on_false as string) || "";
  const onError = (nodeData.on_error as string) || "";

  // Available candidate target nodes (excluding self)
  const candidateTargetNodes = allNodes.filter((n) => n.id !== selectedNode?.id);

  return (
    <aside className="w-84 bg-white border-l border-zinc-200 flex flex-col h-full z-10">
      <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
            {nodeType} PROPERTIES
          </span>
          <div className="text-sm font-semibold text-zinc-900 truncate">{name}</div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Node Name */}
        <div>
          <label className="block text-xs font-medium text-zinc-700 mb-1">Node Name</label>
          <input
            disabled={disabled}
            type="text"
            value={name}
            onChange={(e) => onUpdateNodeData(selectedNode!.id, { name: e.target.value, label: e.target.value })}
            className="w-full text-xs p-2 rounded-md border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        {/* START NODE specifics */}
        {nodeType === "START" && (
          <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-100 space-y-2">
            <div className="text-xs font-semibold text-emerald-900">Start Node Settings</div>
            <p className="text-[11px] text-zinc-600">
              This node initializes the call runtime session and routes directly to the first conversational step.
            </p>
          </div>
        )}

        {/* AGENT NODE specifics */}
        {nodeType === "AGENT" && (
          <>
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Instructions / Step Prompt</label>
              <textarea
                disabled={disabled}
                value={prompt}
                onChange={(e) => onUpdateNodeData(selectedNode!.id, { prompt: e.target.value })}
                rows={5}
                placeholder="You are greeting the caller. Introduce yourself and ask how you can assist today..."
                className="w-full text-xs p-2 rounded-md border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-y font-sans"
              />
              <p className="text-[11px] text-zinc-400 mt-1">
                Context-specific instructions for this step. Combined with global workflow instructions.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Scoped Business Tools</label>
              <div className="space-y-1.5 mb-2">
                {tools.map((toolName) => (
                  <div
                    key={toolName}
                    className="flex items-center justify-between p-1.5 bg-zinc-50 border border-zinc-200 rounded text-xs"
                  >
                    <span className="font-mono text-zinc-800">{toolName}</span>
                    <button
                      disabled={disabled}
                      onClick={() => {
                        const nextTools = tools.filter((t) => t !== toolName);
                        onUpdateNodeData(selectedNode!.id, { tools: nextTools });
                      }}
                      className="text-zinc-400 hover:text-rose-600 p-0.5"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex gap-1.5">
                <input
                  disabled={disabled}
                  id="new-tool-input"
                  type="text"
                  placeholder="Tool name (e.g. check_calendar)"
                  className="flex-1 text-xs p-1.5 rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const val = (e.target as HTMLInputElement).value.trim();
                      if (val && !tools.includes(val)) {
                        onUpdateNodeData(selectedNode!.id, { tools: [...tools, val] });
                        (e.target as HTMLInputElement).value = "";
                      }
                    }
                  }}
                />
                <button
                  disabled={disabled}
                  onClick={() => {
                    const input = document.getElementById("new-tool-input") as HTMLInputElement;
                    const val = input?.value.trim();
                    if (val && !tools.includes(val)) {
                      onUpdateNodeData(selectedNode!.id, { tools: [...tools, val] });
                      input.value = "";
                    }
                  }}
                  className="p-1.5 bg-zinc-900 text-white rounded-md text-xs hover:bg-zinc-800 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}

        {/* CONDITION NODE specifics */}
        {nodeType === "CONDITION" && (
          <div className="space-y-3">
            <div className="p-3 bg-amber-50/50 rounded-lg border border-amber-100">
              <span className="text-xs font-semibold text-amber-900 block mb-1">Branch Expression</span>
              <p className="text-[11px] text-zinc-600">
                Evaluated safely by backend ConditionEvaluator against runtime session variables.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Variable Name</label>
              <input
                disabled={disabled}
                type="text"
                value={condition.variable || ""}
                onChange={(e) =>
                  onUpdateNodeData(selectedNode!.id, {
                    condition: { ...condition, variable: e.target.value },
                  })
                }
                placeholder="e.g. appointment_confirmed, user_intent"
                className="w-full text-xs p-2 rounded-md border border-zinc-300 font-mono focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Operator</label>
              <select
                disabled={disabled}
                value={condition.operator || "equals"}
                onChange={(e) =>
                  onUpdateNodeData(selectedNode!.id, {
                    condition: { ...condition, operator: e.target.value },
                  })
                }
                className="w-full text-xs p-2 rounded-md border border-zinc-300 bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                {CONDITION_OPERATORS.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Target Value input if operator needs value */}
            {CONDITION_OPERATORS.find((op) => op.value === (condition.operator || "equals"))?.needsValue && (
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">Target Value</label>
                <input
                  disabled={disabled}
                  type="text"
                  value={
                    typeof condition.value === "object"
                      ? JSON.stringify(condition.value)
                      : condition.value !== undefined
                      ? String(condition.value)
                      : ""
                  }
                  onChange={(e) => {
                    let val: any = e.target.value;
                    if (val === "true") val = true;
                    else if (val === "false") val = false;
                    else if (!isNaN(Number(val)) && val !== "") val = Number(val);
                    onUpdateNodeData(selectedNode!.id, {
                      condition: { ...condition, value: val },
                    });
                  }}
                  placeholder="Value to compare against"
                  className="w-full text-xs p-2 rounded-md border border-zinc-300 font-mono focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            )}

            <div className="pt-2 border-t border-zinc-200 space-y-2">
              <label className="block text-xs font-semibold text-zinc-900">Branch Routing Targets</label>

              <div>
                <label className="block text-[11px] font-medium text-emerald-800 mb-0.5">Route if TRUE</label>
                <select
                  disabled={disabled}
                  value={onTrue}
                  onChange={(e) => onUpdateNodeData(selectedNode!.id, { on_true: e.target.value })}
                  className="w-full text-xs p-1.5 rounded-md border border-emerald-300 bg-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="">-- Select Target Node --</option>
                  {candidateTargetNodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.data?.name as string || n.id} ({n.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-rose-800 mb-0.5">Route if FALSE</label>
                <select
                  disabled={disabled}
                  value={onFalse}
                  onChange={(e) => onUpdateNodeData(selectedNode!.id, { on_false: e.target.value })}
                  className="w-full text-xs p-1.5 rounded-md border border-rose-300 bg-white focus:outline-none focus:ring-1 focus:ring-rose-500"
                >
                  <option value="">-- Select Target Node --</option>
                  {candidateTargetNodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.data?.name as string || n.id} ({n.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-amber-800 mb-0.5">
                  Route if ERROR (Optional)
                </label>
                <select
                  disabled={disabled}
                  value={onError}
                  onChange={(e) => onUpdateNodeData(selectedNode!.id, { on_error: e.target.value || null })}
                  className="w-full text-xs p-1.5 rounded-md border border-amber-300 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
                >
                  <option value="">-- None (Raise Execution Error) --</option>
                  {candidateTargetNodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.data?.name as string || n.id} ({n.id})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* END NODE specifics */}
        {nodeType === "END" && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Final Farewell Prompt</label>
              <textarea
                disabled={disabled}
                value={prompt}
                onChange={(e) => onUpdateNodeData(selectedNode!.id, { prompt: e.target.value })}
                rows={3}
                placeholder="Thank you for calling. Have a wonderful day! Goodbye."
                className="w-full text-xs p-2 rounded-md border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none"
              />
            </div>
            <div className="p-3 bg-rose-50/50 rounded-lg border border-rose-100 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <p className="text-[11px] text-rose-800">
                This node automatically attaches the authoritative <code>end_call</code> tool and signals call completion.
              </p>
            </div>
          </div>
        )}

        {/* UNKNOWN NODE specifics */}
        {nodeType !== "START" && nodeType !== "AGENT" && nodeType !== "CONDITION" && nodeType !== "END" && (
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
            <div className="text-xs font-semibold text-slate-800 mb-1">Custom Node Payload</div>
            <p className="text-[11px] text-slate-500">
              Raw configuration is preserved non-destructively in workflow serialization.
            </p>
          </div>
        )}
      </div>

      {/* Delete node button (prevent deleting start node if only start node) */}
      <div className="p-4 border-t border-zinc-100">
        <button
          disabled={disabled || (nodeType === "START" && allNodes.filter((n) => (n.data?.type as string) === "START").length <= 1)}
          onClick={() => onDeleteNode(selectedNode!.id)}
          className="w-full flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Delete Node
        </button>
      </div>
    </aside>
  );
};

export default NodePropertiesPanel;
