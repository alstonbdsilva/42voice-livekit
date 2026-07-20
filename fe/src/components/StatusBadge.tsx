import React from "react";

const variants: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  renewed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  positive: "bg-emerald-50 text-emerald-700 border-emerald-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  partially_paid: "bg-amber-50 text-amber-700 border-amber-200",
  due: "bg-amber-50 text-amber-700 border-amber-200",
  testing: "bg-amber-50 text-amber-700 border-amber-200",
  expiring_soon: "bg-amber-50 text-amber-700 border-amber-200",
  in_discussion: "bg-amber-50 text-amber-700 border-amber-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
  paused: "bg-zinc-100 text-zinc-700 border-zinc-300",
  neutral: "bg-zinc-100 text-zinc-700 border-zinc-300",
  not_started: "bg-zinc-100 text-zinc-700 border-zinc-300",
  abandoned: "bg-zinc-100 text-zinc-700 border-zinc-300",
  disabled: "bg-zinc-100 text-zinc-500 border-zinc-300",
  callback_scheduled: "bg-zinc-100 text-zinc-700 border-zinc-300",
  overdue: "bg-rose-50 text-rose-700 border-rose-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  escalated: "bg-rose-50 text-rose-700 border-rose-200",
  escalated_to_human: "bg-rose-50 text-rose-700 border-rose-200",
  negative: "bg-rose-50 text-rose-700 border-rose-200",
  expired: "bg-rose-50 text-rose-700 border-rose-200",
  lapsed: "bg-rose-50 text-rose-700 border-rose-200",
  urgent: "bg-rose-50 text-rose-700 border-rose-200",
  high: "bg-amber-50 text-amber-700 border-amber-200",
  medium: "bg-zinc-100 text-zinc-700 border-zinc-300",
  low: "bg-zinc-100 text-zinc-500 border-zinc-300",
};

interface StatusBadgeProps {
  value?: string | null;
  className?: string;
  testId?: string;
}

export default function StatusBadge({ value, className = "", testId }: StatusBadgeProps) {
  const key = (value || "").toLowerCase();
  const cls = variants[key] || "bg-zinc-100 text-zinc-700 border-zinc-300";
  
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 border px-2 py-0.5 rounded-sm text-[11px] font-mono-stat ${cls} ${className}`}
    >
      <span className="status-dot bg-current opacity-70" />
      {(value || "—").replace(/_/g, " ")}
    </span>
  );
}
