import { Invoice } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtCurrency, fmtDate } from "@/services/api";
import { InvoiceService } from "@/services/invoice.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Invoices() {
  const [rows, setRows] = useState<Invoice[]>([]);
  const nav = useNavigate();
  useEffect(() => { InvoiceService.getAll().then((data) => setRows(data)).catch(() => {}); }, []);

  const columns = [
    { key: "number", label: "Invoice", render: (r: Invoice) => <span className="font-mono-stat font-medium">{r.number ?? "Invoice"}</span> },
    { key: "clientName", label: "Client" },
    { key: "issueDate", label: "Issued", render: (r: Invoice) => <span className="text-xs">{fmtDate(r.issueDate || r.createdAt)}</span> },
    { key: "dueDate", label: "Due", render: (r: Invoice) => <span className="text-xs">{fmtDate(r.dueDate)}</span> },
    { key: "total", label: "Total", render: (r: Invoice) => <span className="font-mono-stat">{fmtCurrency(r.total ?? 0)}</span> },
    { key: "paidAmount", label: "Paid", render: (r: Invoice) => <span className="font-mono-stat text-emerald-700">{fmtCurrency(r.paidAmount ?? 0)}</span> },
    { key: "outstanding", label: "Outstanding", render: (r: Invoice) => <span className="font-mono-stat text-amber-700">{fmtCurrency(Math.max((r.total ?? 0) - (r.paidAmount ?? 0), 0))}</span> },
    { key: "status", label: "Status", render: (r: Invoice) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="invoices-page">
      <PageHeader title="Invoices" subtitle="All billing artefacts across your portfolio" />
      <DataTable
        testId="invoices-table" columns={columns} rows={rows} searchKeys={["number", "clientName"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "paid", label: "Paid" }, { value: "pending", label: "Pending" },
          { value: "partially_paid", label: "Partial" }, { value: "overdue", label: "Overdue" }
        ]}]}
        onRowClick={(r) => nav(`/invoices/${r.id}`)}
      />
    </div>
  );
}
