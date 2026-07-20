import { Contract } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtCurrency, fmtDate, daysFrom } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Contracts() {
  const [rows, setRows] = useState<Contract[]>([]);
  const nav = useNavigate();
  useEffect(() => { api.get("/contracts").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "number", label: "Contract", render: (r: Contract) => <span className="font-mono-stat font-medium">{r.number ?? "Contract"}</span> },
    { key: "clientName", label: "Client" },
    { key: "startDate", label: "Start", render: (r: Contract) => <span className="text-xs">{fmtDate(r.startDate)}</span> },
    { key: "endDate", label: "End", render: (r: Contract) => {
      const d = daysFrom(r.endDate) ?? 999;
      const cls = d < 0 ? "text-rose-700" : d <= 30 ? "text-amber-700" : "text-zinc-900";
      return <span className={`text-xs font-mono-stat ${cls}`}>{fmtDate(r.endDate)} {d !== 999 && d >= 0 && d <= 90 && `(${d}d)`}</span>;
    }},
    { key: "contractValue", label: "Value", render: (r: Contract) => <span className="font-mono-stat">{fmtCurrency(r.contractValue ?? r.value ?? 0)}</span> },
    { key: "autoRenewal", label: "Auto-renew", render: (r: Contract) => <span className="text-xs">{r.autoRenewal ? "Yes" : "No"}</span> },
    { key: "status", label: "Status", render: (r: Contract) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="contracts-page">
      <PageHeader title="Contracts" subtitle="Active, expiring and expired agreements" />
      <DataTable testId="contracts-table" columns={columns} rows={rows} searchKeys={["number", "clientName"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "active", label: "Active" }, { value: "expiring_soon", label: "Expiring soon" }, { value: "expired", label: "Expired" }
        ]}]}
        onRowClick={(r) => nav(`/contracts/${r.id}`)}
      />
    </div>
  );
}
