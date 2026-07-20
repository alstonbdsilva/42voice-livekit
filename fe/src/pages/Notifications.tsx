import React, { useEffect, useState } from "react";
import { api, fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { toast } from "sonner";
import { Notification } from "@/types";

export default function Notifications() {
  const [rows, setRows] = useState<Notification[]>([]);
  const [filter, setFilter] = useState("all");

  const load = () => api.get("/notifications").then((r) => setRows(r.data)).catch(() => { });
  useEffect(() => { load(); }, []);

  const markRead = async (id: string | number) => {
    try { await api.patch(`/notifications/${id}`, { read: true }); load(); }
    catch { toast.error("Failed"); }
  };

  const shown = rows.filter((n) => filter === "all" || (filter === "unread" ? !n.read : n.priority === filter));

  return (
    <div data-testid="notifications-page">
      <PageHeader title="Notification centre" subtitle="Payment, contract, escalation and usage alerts" />
      <div className="bg-white border border-zinc-200">
        <div className="px-4 py-3 border-b border-zinc-200 flex items-center gap-2">
          {[["all", "All"], ["unread", "Unread"], ["urgent", "Urgent"], ["high", "High"], ["medium", "Medium"]].map(([k, label]) => (
            <button key={k} onClick={() => setFilter(k)} data-testid={`notif-filter-${k}`}
              className={`px-3 py-1.5 text-xs rounded-sm ${filter === k ? "bg-zinc-950 text-white" : "border border-zinc-200 hover:bg-zinc-50"}`}>
              {label}
            </button>
          ))}
          <div className="ml-auto label-tiny font-mono-stat">{shown.length} alerts</div>
        </div>
        <div className="divide-y divide-zinc-100">
          {shown.map((n) => (
            <div key={n.id} data-testid={`notif-${n.id}`}
              className={`px-5 py-4 flex items-start gap-3 ${n.read ? "opacity-60" : ""}`}>
              <StatusBadge value={n.priority} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-zinc-900">{n.title}</div>
                <div className="text-xs text-zinc-500 mt-0.5">{n.description}</div>
                <div className="text-[10px] text-zinc-400 font-mono-stat mt-1">{fmtDateTime(n.createdAt)} • {n.type.replace("_", " ")}</div>
              </div>
              {!n.read && (
                <button onClick={() => markRead(n.id)} className="text-xs text-zinc-500 hover:text-zinc-950" data-testid={`mark-read-${n.id}`}>
                  Mark read
                </button>
              )}
            </div>
          ))}
          {shown.length === 0 && <div className="px-5 py-12 text-center text-sm text-zinc-400">No alerts</div>}
        </div>
      </div>
    </div>
  );
}
