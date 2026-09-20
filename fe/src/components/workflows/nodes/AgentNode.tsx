import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { Bot, Wrench } from "lucide-react";

export const AgentNode: React.FC<NodeProps> = ({ data, selected }) => {
  const name = (data?.name as string) || (data?.label as string) || "Agent Node";
  const prompt = (data?.prompt as string) || "";
  const tools = (data?.tools as string[]) || [];

  return (
    <div
      className={`px-4 py-3 rounded-xl bg-white border-2 shadow-sm min-w-[240px] max-w-[300px] transition-all ${
        selected ? "border-indigo-600 ring-2 ring-indigo-200 shadow-md" : "border-indigo-200 hover:border-indigo-300"
      }`}
    >
      {/* Target handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-indigo-500 !border-2 !border-white"
      />

      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
          <Bot className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-indigo-700">CONVERSATION STEP</div>
          <div className="text-sm font-semibold text-zinc-900 truncate">{name}</div>
        </div>
      </div>

      {prompt ? (
        <div className="text-xs text-zinc-600 bg-zinc-50 rounded-md p-2 mb-2 line-clamp-2 italic border border-zinc-100">
          "{prompt}"
        </div>
      ) : (
        <div className="text-xs text-zinc-400 italic mb-2">No prompt defined</div>
      )}

      {tools.length > 0 && (
        <div className="flex flex-wrap gap-1 items-center pt-1 border-t border-zinc-100">
          <Wrench className="w-3 h-3 text-zinc-400 mr-0.5" />
          {tools.map((t) => (
            <span
              key={t}
              className="text-[10px] font-medium bg-zinc-100 text-zinc-700 px-1.5 py-0.5 rounded border border-zinc-200"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Outgoing semantic handles */}
      <Handle
        type="source"
        position={Position.Right}
        id="default"
        className="!w-3 !h-3 !bg-indigo-500 !border-2 !border-white"
      />
    </div>
  );
};

export default memo(AgentNode);
