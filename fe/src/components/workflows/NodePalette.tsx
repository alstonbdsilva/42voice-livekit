import React from "react";
import { Play, Bot, GitBranch, PhoneOff } from "lucide-react";

interface NodePaletteProps {
  onAddNode: (type: "START" | "AGENT" | "CONDITION" | "END") => void;
  disabled?: boolean;
}

export const NodePalette: React.FC<NodePaletteProps> = ({ onAddNode, disabled }) => {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  const paletteItems = [
    {
      type: "START" as const,
      label: "Start Node",
      badge: "START",
      description: "Workflow entry point & initial routing",
      icon: Play,
      bg: "bg-emerald-50",
      text: "text-emerald-700",
      border: "border-emerald-200 hover:border-emerald-400",
    },
    {
      type: "AGENT" as const,
      label: "Agent Node",
      badge: "AGENT",
      description: "Conversational instruction & tool execution step",
      icon: Bot,
      bg: "bg-indigo-50",
      text: "text-indigo-700",
      border: "border-indigo-200 hover:border-indigo-400",
    },
    {
      type: "CONDITION" as const,
      label: "Condition Node",
      badge: "CONDITION",
      description: "Fast deterministic variable branching",
      icon: GitBranch,
      bg: "bg-amber-50",
      text: "text-amber-700",
      border: "border-amber-200 hover:border-amber-400",
    },
    {
      type: "END" as const,
      label: "End Call",
      badge: "END",
      description: "Terminal node executing safe end_call",
      icon: PhoneOff,
      bg: "bg-rose-50",
      text: "text-rose-700",
      border: "border-rose-200 hover:border-rose-400",
    },
  ];

  return (
    <aside className="w-64 bg-white border-r border-zinc-200 flex flex-col h-full select-none z-10">
      <div className="p-4 border-b border-zinc-100">
        <div className="text-xs font-bold uppercase tracking-wider text-zinc-500">Node Palette</div>
        <p className="text-[11px] text-zinc-400 mt-0.5">Drag to canvas or click to add</p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {paletteItems.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.type}
              draggable={!disabled}
              onDragStart={(e) => onDragStart(e, item.type)}
              onClick={() => !disabled && onAddNode(item.type)}
              className={`p-3 rounded-xl border bg-white shadow-xs cursor-grab active:cursor-grabbing transition-all hover:shadow-sm ${item.border} ${
                disabled ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              <div className="flex items-center gap-2.5 mb-1">
                <div className={`w-7 h-7 rounded-lg ${item.bg} ${item.text} flex items-center justify-center font-bold`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${item.bg} ${item.text}`}>
                    {item.badge}
                  </span>
                  <div className="text-xs font-semibold text-zinc-900 mt-0.5">{item.label}</div>
                </div>
              </div>
              <p className="text-[11px] text-zinc-500 line-clamp-2 mt-1">{item.description}</p>
            </div>
          );
        })}
      </div>

      <div className="p-3 border-t border-zinc-100 text-[11px] text-zinc-500 bg-zinc-50/50">
        💡 Connect nodes by dragging lines between input and output ports.
      </div>
    </aside>
  );
};

export default NodePalette;
