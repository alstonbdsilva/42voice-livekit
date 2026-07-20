import { Agent, Conversation, UserRole } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtNumber, fmtCurrency, fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";
import { ArrowLeft, Pause, Play } from "lucide-react";

export default function AgentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [a, setA] = useState<Agent | null>(null);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const canEdit = user?.role ? ["super_admin", "reseller"].includes(user.role) : false;

  const load = () => {
    api.get(`/agents/${id}`).then((r) => setA(r.data)).catch(() => {});
    api.get(`/conversations?agentId=${id}&limit=20`).then((r) => setConvs(r.data)).catch(() => {});
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  const toggleStatus = async () => {
    if (!a) return;
    const next = a.status === "active" ? "paused" : "active";
    try {
      await api.patch(`/agents/${id}`, { status: next });
      toast.success(`Agent ${next}`);
      load();
    } catch { toast.error("Update failed"); }
  };

  if (!a) return <div className="label-tiny">Loading…</div>;

  return (
    <div data-testid="agent-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader
        title={a.name}
        subtitle={`${a.type} • ${a.channels.join(", ")} • Prompt ${a.promptVersion} • KB ${a.kbVersion}`}
        actions={(
          <div className="flex items-center gap-2">
            <StatusBadge value={a.status} />
            {canEdit && (
              <button onClick={toggleStatus} data-testid="agent-toggle" className="px-3 py-1.5 border border-zinc-300 text-xs rounded-sm hover:bg-zinc-50 flex items-center gap-1.5">
                {a.status === "active" ? <><Pause className="w-3 h-3"/> Pause</> : <><Play className="w-3 h-3"/> Resume</>}
              </button>
            )}
          </div>
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Total calls" value={fmtNumber(a.totalCalls)} />
        <KpiCard label="Total messages" value={fmtNumber(a.totalMessages)} />
        <KpiCard label="Total minutes" value={fmtNumber(a.totalMinutes)} />
        <KpiCard label="Total cost" value={fmtCurrency(a.totalCost ?? 0)} />
        <KpiCard label="Success rate" value={`${a.successRate}%`} accent="success" />
        <KpiCard label="Escalation rate" value={`${a.escalationRate}%`} accent="danger" />
        <KpiCard label="Last activity" value={fmtDateTime(a.lastActivity ?? "")} />
        <KpiCard label="Channels" value={a.channels.length} />
      </div>

      <div className="bg-white border border-zinc-200">
        <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">RECENT CONVERSATIONS</div></div>
        <div className="divide-y divide-zinc-100">
          {convs.map((c) => (
            <div key={c.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/conversations/${c.id}`)}>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{c.customerName}</div>
                <div className="text-xs text-zinc-500 truncate">{c.summary}</div>
              </div>
              <span className="text-xs font-mono-stat text-zinc-500">{c.channel}</span>
              <StatusBadge value={c.outcome} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
