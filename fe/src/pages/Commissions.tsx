import { Commission } from "@/types";
import React, { useEffect, useState } from "react";
import { api, fmtCurrency, fmtDate } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Commissions() {
  const [rows, setRows] = useState<Commission[]>([]);
  useEffect(() => { api.get("/commissions").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "createdAt", label: "Date", render: (r: Commission) => <span className="text-xs">{fmtDate(r.createdAt || r.date)}</span> },
    { key: "resellerName", label: "Reseller" },
    { key: "clientName", label: "Client" },
    { key: "invoiceNumber", label: "Invoice", render: (r: Commission) => <span className="font-mono-stat text-xs">{r.invoiceNumber ?? ""}</span> },
    { key: "commissionPct", label: "Rate", render: (r: Commission) => <span className="font-mono-stat text-xs">{r.commissionPct ?? 0}%</span> },
    { key: "amount", label: "Amount", render: (r: Commission) => <span className="font-mono-stat font-medium">{fmtCurrency(r.amount)}</span> },
    { key: "status", label: "Status", render: (r: Commission) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="commissions-page">
      <PageHeader title="Reseller commissions" subtitle="Earnings, payouts and pending obligations" />
      <DataTable testId="commissions-table" columns={columns} rows={rows} searchKeys={["resellerName", "clientName", "invoiceNumber"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "pending", label: "Pending" }, { value: "paid", label: "Paid" }
        ]}]} />
    </div>
  );
}
