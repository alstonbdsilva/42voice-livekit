import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { PhoneOff } from "lucide-react";

export const EndNode: React.FC<NodeProps> = ({ data, selected }) => {
  const name = (data?.name as string) || (data?.label as string) || "End Call";
  const prompt = (data?.prompt as string) || "";

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-white border-2 shadow-sm min-w-[200px] max-w-[280px] transition-all ${
        selected ? "border-rose-600 ring-2 ring-rose-200 shadow-md" : "border-rose-300 hover:border-rose-400"
      }`}
    >
      {/* Target handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-rose-500 !border-2 !border-white"
      />

      <div className="flex items-center gap-2.5 mb-1.5">
        <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center font-bold">
          <PhoneOff className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-rose-700">TERMINAL NODE</div>
          <div className="text-sm font-semibold text-zinc-900 truncate">{name}</div>
        </div>
      </div>

      {prompt ? (
        <div className="text-xs text-zinc-600 bg-rose-50/40 rounded-md p-2 mb-1.5 line-clamp-2 italic border border-rose-100">
          "{prompt}"
        </div>
      ) : (
        <div className="text-xs text-zinc-400 italic mb-1.5">Ends active call</div>
      )}

      <div className="text-[10px] font-medium text-rose-800 bg-rose-100/70 rounded px-1.5 py-0.5 inline-block">
        Authoritative end_call tool
      </div>
    </div>
  );
};

export default memo(EndNode);
