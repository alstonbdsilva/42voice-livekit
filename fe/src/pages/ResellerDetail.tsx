import { Reseller, Client, Commission } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fmtCurrency } from "@/services/api";
import ResellerService from "@/services/reseller.service";
import ClientService from "@/services/client.service";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

export default function ResellerDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [r, setR] = useState<Reseller | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [commissions, setCommissions] = useState<Commission[]>([]);

  useEffect(() => {
    if (!id) return;
    ResellerService.getById(id).then(setR).catch(() => {});
    ClientService.getAll().then((data) => {
      setClients(data.filter((c) => c.resellerId?.toString() === id?.toString()));
    }).catch(() => {});
    // Mocked commissions for now
    setCommissions([]);
  }, [id]);

  if (!r) return <div className="label-tiny">Loading…</div>;

  const earned = commissions.reduce((a, c) => a + (c.status === "paid" ? c.amount : 0), 0);
  const pending = commissions.reduce((a, c) => a + (c.status === "pending" ? c.amount : 0), 0);

  return (
    <div data-testid="reseller-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader title={r.name} subtitle={`${r.country} • ${r.commissionPct}% commission`} actions={<StatusBadge value={r.status} />} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Clients" value={clients.length} />
        <KpiCard label="Commission earned" value={fmtCurrency(earned)} accent="success" />
        <KpiCard label="Commission pending" value={fmtCurrency(pending)} accent="warning" />
        <KpiCard label="Commission rate" value={`${r.commissionPct}%`} />
      </div>

      <div className="bg-white border border-zinc-200">
        <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">PARTNER CLIENTS</div></div>
        <div className="divide-y divide-zinc-100">
          {clients.map((c) => (
            <div key={c.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/clients/${c.id}`)}>
              <div className="flex-1">
                <div className="text-sm font-medium">{c.name}</div>
                <div className="text-xs text-zinc-500">{c.industry} • MRR {fmtCurrency(c.monthlyRecurring)}</div>
              </div>
              <StatusBadge value={c.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
