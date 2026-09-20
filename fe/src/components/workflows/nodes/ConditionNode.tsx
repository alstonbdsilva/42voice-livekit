import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { GitBranch, Check, X, AlertTriangle } from "lucide-react";

export const ConditionNode: React.FC<NodeProps> = ({ data, selected }) => {
  const name = (data?.name as string) || (data?.label as string) || "Condition Node";
  const condition = data?.condition as any;
  const onTrue = (data?.on_true as string) || "";
  const onFalse = (data?.on_false as string) || "";
  const onError = (data?.on_error as string) || "";

  // Helper to format condition summary
  let condSummary = "Not configured";
  if (condition) {
    if (condition.variable) {
      condSummary = `${condition.variable} ${condition.operator || "equals"} ${condition.value !== undefined ? JSON.stringify(condition.value) : ""}`;
    } else if (condition.and) {
      condSummary = `AND (${condition.and.length} conditions)`;
    } else if (condition.or) {
      condSummary = `OR (${condition.or.length} conditions)`;
    } else if (condition.not) {
      condSummary = "NOT condition";
    }
  }

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-white border-2 shadow-sm min-w-[260px] max-w-[320px] transition-all relative ${
        selected ? "border-amber-500 ring-2 ring-amber-200 shadow-md" : "border-amber-300 hover:border-amber-400"
      }`}
    >
      {/* Target handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-amber-500 !border-2 !border-white"
      />

      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
          <GitBranch className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-amber-700">DETERMINISTIC BRANCH</div>
          <div className="text-sm font-semibold text-zinc-900 truncate">{name}</div>
        </div>
      </div>

      <div className="text-xs bg-amber-50/60 rounded-md p-2 mb-2 font-mono text-amber-950 border border-amber-200/60 break-all">
        {condSummary}
      </div>

      <div className="space-y-1 text-xs">
        <div className="flex items-center justify-between px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-100">
          <span className="flex items-center gap-1 font-semibold text-[11px]">
            <Check className="w-3 h-3 text-emerald-600" /> TRUE:
          </span>
          <span className="font-mono text-[11px] truncate max-w-[120px]">{onTrue || "Not connected"}</span>
        </div>
        <div className="flex items-center justify-between px-1.5 py-0.5 rounded bg-rose-50 text-rose-800 border border-rose-100">
          <span className="flex items-center gap-1 font-semibold text-[11px]">
            <X className="w-3 h-3 text-rose-600" /> FALSE:
          </span>
          <span className="font-mono text-[11px] truncate max-w-[120px]">{onFalse || "Not connected"}</span>
        </div>
        {onError && (
          <div className="flex items-center justify-between px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-100">
            <span className="flex items-center gap-1 font-semibold text-[11px]">
              <AlertTriangle className="w-3 h-3 text-amber-600" /> ERROR:
            </span>
            <span className="font-mono text-[11px] truncate max-w-[120px]">{onError}</span>
          </div>
        )}
      </div>

      {/* Outgoing TRUE handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: "40%" }}
        className="!w-3 !h-3 !bg-emerald-500 !border-2 !border-white"
      />

      {/* Outgoing FALSE handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: "70%" }}
        className="!w-3 !h-3 !bg-rose-500 !border-2 !border-white"
      />

      {/* Outgoing ERROR handle */}
      {onError && (
        <Handle
          type="source"
          position={Position.Right}
          id="error"
          style={{ top: "90%" }}
          className="!w-3 !h-3 !bg-amber-500 !border-2 !border-white"
        />
      )}
    </div>
  );
};

export default memo(ConditionNode);
