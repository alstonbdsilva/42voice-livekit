import { Payment } from "@/types";
import React, { useEffect, useState } from "react";
import { fmtCurrency, fmtDate } from "@/services/api";
import { PaymentService } from "@/services/payment.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Payments() {
  const [rows, setRows] = useState<Payment[]>([]);
  useEffect(() => { PaymentService.getAll().then((data) => setRows(data)).catch(() => {}); }, []);

  const columns = [
    { key: "paidAt", label: "Date", render: (r: Payment) => <span className="text-xs font-mono-stat">{fmtDate(r.paidAt)}</span> },
    { key: "reference", label: "Reference", render: (r: Payment) => <span className="font-mono-stat text-xs">{r.reference}</span> },
    { key: "clientName", label: "Client" },
    { key: "invoiceNumber", label: "Invoice", render: (r: Payment) => <span className="font-mono-stat text-xs">{r.invoiceNumber}</span> },
    { key: "amount", label: "Amount", render: (r: Payment) => <span className="font-mono-stat font-medium">{fmtCurrency(r.amount)}</span> },
    { key: "method", label: "Method", render: (r: Payment) => <span className="text-xs uppercase font-mono-stat">{r.method}</span> },
    { key: "status", label: "Status", render: (r: Payment) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="payments-page">
      <PageHeader title="Payments" subtitle="Inbound payments across all clients" />
      <DataTable testId="payments-table" columns={columns} rows={rows} searchKeys={["reference", "clientName", "invoiceNumber"]}
        filters={[{ key: "method", label: "Method", options: [
          { value: "card", label: "Card" }, { value: "ach", label: "ACH" }, { value: "wire", label: "Wire" }, { value: "credit", label: "Credit" }
        ]}]}
      />
    </div>
  );
}
