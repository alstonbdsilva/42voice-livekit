import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Play } from "lucide-react";

export const StartNode: React.FC<NodeProps> = ({ data, selected }) => {
  const name = (data?.name as string) || (data?.label as string) || "Start";
  const nextNode = (data?.config as any)?.next_node;

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-white border-2 shadow-sm min-w-[200px] transition-all ${
        selected ? "border-emerald-600 ring-2 ring-emerald-200 shadow-md" : "border-emerald-300 hover:border-emerald-400"
      }`}
    >
      <div className="flex items-center gap-2.5 mb-1.5">
        <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
          <Play className="w-3.5 h-3.5 fill-current" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-700">START NODE</div>
          <div className="text-sm font-semibold text-zinc-900 truncate">{name}</div>
        </div>
      </div>

      <div className="text-xs text-zinc-700 bg-emerald-50/50 rounded-md px-2 py-1 mt-1 border border-emerald-100/80">
        <span className="text-zinc-600">Routes to: </span>
        <span className="font-medium text-emerald-800">{nextNode || "First connected node"}</span>
      </div>

      {/* Outgoing source handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="default"
        className="!w-3 !h-3 !bg-emerald-500 !border-2 !border-white"
      />
    </div>
  );
};

export default memo(StartNode);
