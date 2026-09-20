import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { HelpCircle } from "lucide-react";

export const UnknownNode: React.FC<NodeProps> = ({ data, selected }) => {
  const name = (data?.name as string) || (data?.label as string) || "Custom / Unknown Node";
  const type = (data?.type as string) || "UNKNOWN";

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-slate-50 border-2 border-dashed shadow-sm min-w-[220px] transition-all ${
        selected ? "border-slate-800 ring-2 ring-slate-300" : "border-slate-300 hover:border-slate-400"
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-slate-500 !border-2 !border-white"
      />

      <div className="flex items-center gap-2.5 mb-1.5">
        <div className="w-7 h-7 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center font-bold">
          <HelpCircle className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">
            RAW TYPE: {type}
          </div>
          <div className="text-sm font-semibold text-zinc-800 truncate">{name}</div>
        </div>
      </div>

      <div className="text-[11px] text-slate-500 italic bg-white rounded p-1.5 border border-slate-200">
        Non-destructive raw node representation. Executable fields preserved upon saving.
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="default"
        className="!w-3 !h-3 !bg-slate-500 !border-2 !border-white"
      />
    </div>
  );
};

export default memo(UnknownNode);
