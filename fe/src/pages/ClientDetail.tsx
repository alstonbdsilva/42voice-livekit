import { Client, Agent, Invoice, Contract } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtCurrency, fmtDate } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

export default function ClientDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState<Client | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);

  useEffect(() => {
    api.get(`/clients/${id}`).then((r) => setC(r.data)).catch(() => {});
    api.get(`/agents?clientId=${id}`).then((r) => setAgents(r.data)).catch(() => {});
    api.get(`/invoices`).then((r) => setInvoices(r.data.filter((x: Invoice) => x.clientId.toString() === id?.toString()))).catch(() => {});
    api.get(`/contracts`).then((r) => setContracts(r.data.filter((x: Contract) => x.clientId.toString() === id?.toString()))).catch(() => {});
  }, [id]);

  if (!c) return <div className="label-tiny">Loading…</div>;

  const outstanding = invoices.reduce((sum, i) => sum + (i.status !== "paid" ? ((i.total ?? 0) - (i.paidAmount ?? 0)) : 0), 0);
  const collected = invoices.reduce((sum, i) => sum + (i.paidAmount ?? 0), 0);

  return (
    <div data-testid="client-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1" data-testid="back-btn">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader
        title={c.name}
        subtitle={`${c.industry} • ${c.country} • ${c.contactEmail}`}
        actions={<StatusBadge value={c.status} />}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="MRR" value={fmtCurrency(c.monthlyRecurring)} />
        <KpiCard label="Collected" value={fmtCurrency(collected)} accent="success" />
        <KpiCard label="Outstanding" value={fmtCurrency(outstanding)} accent="warning" />
        <KpiCard label="AI Agents" value={agents.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">AGENTS</div></div>
          <div className="divide-y divide-zinc-100">
            {agents.map((a) => (
              <div key={a.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/agents/${a.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-medium">{a.name}</div>
                  <div className="text-xs text-zinc-500 font-mono-stat">{a.type} • {a.channels.join(", ")}</div>
                </div>
                <StatusBadge value={a.status} />
              </div>
            ))}
            {agents.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No agents</div>}
          </div>
        </div>

        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">INVOICES</div></div>
          <div className="divide-y divide-zinc-100">
            {invoices.slice(0, 8).map((i) => (
              <div key={i.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/invoices/${i.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-mono-stat font-medium">{i.number ?? "Invoice"}</div>
                  <div className="text-xs text-zinc-500">Due {fmtDate(i.dueDate)}</div>
                </div>
                <div className="font-mono-stat text-sm">{fmtCurrency(i.total ?? 0)}</div>
                <StatusBadge value={i.status} />
              </div>
            ))}
            {invoices.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No invoices</div>}
          </div>
        </div>

        <div className="bg-white border border-zinc-200 lg:col-span-2">
          <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">CONTRACTS</div></div>
          <div className="divide-y divide-zinc-100">
            {contracts.map((ct) => (
              <div key={ct.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/contracts/${ct.id}`)}>
                <div className="flex-1">
                  <div className="text-sm font-mono-stat font-medium">{ct.number ?? "Contract"}</div>
                  <div className="text-xs text-zinc-500">{fmtDate(ct.startDate)} → {fmtDate(ct.endDate)}</div>
                </div>
                <div className="font-mono-stat text-sm">{fmtCurrency(ct.contractValue ?? ct.value ?? 0)}</div>
                <StatusBadge value={ct.status} />
              </div>
            ))}
            {contracts.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No contracts</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
