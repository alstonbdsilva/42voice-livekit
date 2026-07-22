import { Renewal } from "@/types";
import React, { useEffect, useState } from "react";
import { fmtCurrency, fmtDate, daysFrom } from "@/services/api";
import { RenewalService } from "@/services/renewal.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Renewals() {
  const [rows, setRows] = useState<Renewal[]>([]);
  useEffect(() => { RenewalService.getAll().then((data) => setRows(data)).catch(() => {}); }, []);

  const columns = [
    { key: "clientName", label: "Client" },
    { key: "renewalDate", label: "Renewal date", render: (r: Renewal) => {
      const d = daysFrom(r.renewalDate ?? r.date ?? "") ?? 0;
      const cls = d < 0 ? "text-rose-700" : d <= 30 ? "text-amber-700" : "text-zinc-900";
      return <span className={`text-xs font-mono-stat ${cls}`}>{fmtDate(r.renewalDate ?? r.date)} ({d}d)</span>;
    }},
    { key: "endDate", label: "End date", render: (r: Renewal) => <span className="text-xs">{fmtDate(r.endDate ?? "")}</span> },
    { key: "value", label: "Value", render: (r: Renewal) => <span className="font-mono-stat">{fmtCurrency(r.value)}</span> },
    { key: "owner", label: "Owner" },
    { key: "probability", label: "Probability", render: (r: Renewal) => <span className="font-mono-stat">{r.probability}%</span> },
    { key: "status", label: "Status", render: (r: Renewal) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="renewals-page">
      <PageHeader title="Renewals pipeline" subtitle="Contracts up for renewal in the next 90 days" />
      <DataTable testId="renewals-table" columns={columns} rows={rows} searchKeys={["clientName", "owner"]} />
    </div>
  );
}
