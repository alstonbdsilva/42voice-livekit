import { Contract } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtCurrency, fmtDate, daysFrom } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft } from "lucide-react";

export default function ContractDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState<Contract | null>(null);
  useEffect(() => { api.get(`/contracts/${id}`).then((r) => setC(r.data)).catch(() => {}); }, [id]);
  if (!c) return <div className="label-tiny">Loading…</div>;
  const days = daysFrom(c.endDate);

  return (
    <div data-testid="contract-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader title={c.number ?? "Contract"} subtitle={`${c.clientName ?? ""} • ${c.paymentTerms ?? ""} • ${c.billingCycle ?? ""}`} actions={<StatusBadge value={c.status} />} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Contract value" value={fmtCurrency(c.contractValue ?? c.value ?? 0)} />
        <KpiCard label="Start date" value={fmtDate(c.startDate)} />
        <KpiCard label="End date" value={fmtDate(c.endDate)} sub={days != null && days >= 0 ? `${days} days left` : "Expired"} accent={days != null && days < 30 ? "danger" : "default"} />
        <KpiCard label="Renewal probability" value={`${c.renewalProbability ?? 0}%`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">TERMS</div>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div><dt className="label-tiny mb-1">Notice period</dt><dd>{c.noticePeriodDays ?? 0} days</dd></div>
            <div><dt className="label-tiny mb-1">Auto-renewal</dt><dd>{c.autoRenewal ? "Yes" : "No"}</dd></div>
            <div><dt className="label-tiny mb-1">Renewal date</dt><dd>{fmtDate(c.renewalDate ?? "")}</dd></div>
            <div><dt className="label-tiny mb-1">Renewal status</dt><dd><StatusBadge value={c.renewalStatus ?? ""} /></dd></div>
            <div className="col-span-2"><dt className="label-tiny mb-1">Renewal owner</dt><dd>{c.renewalOwner ?? ""}</dd></div>
          </dl>
        </div>
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-3">NOTES</div>
          <p className="text-sm text-zinc-700 leading-relaxed">{c.notes ?? ""}</p>
        </div>
      </div>
    </div>
  );
}
