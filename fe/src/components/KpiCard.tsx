import React from "react";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string | number;
  delta?: number | null;
  accent?: "default" | "success" | "warning" | "danger" | string;
  testId?: string;
}

export default function KpiCard({ label, value, sub, delta, accent = "default", testId }: KpiCardProps) {
  const accentClass = (
    {
      default: "text-zinc-900",
      success: "text-emerald-700",
      warning: "text-amber-700",
      danger: "text-rose-700",
    } as Record<string, string>
  )[accent] || "text-zinc-900";

  return (
    <div className="kpi-card" data-testid={testId}>
      <div className="label-tiny">{label}</div>
      <div className={`mt-2 font-mono-stat text-2xl font-semibold ${accentClass}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-zinc-500">{sub}</div>}
      {delta != null && (
        <div className={`mt-2 text-xs font-mono-stat ${delta >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
          {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
