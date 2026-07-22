import { Commission } from "@/types";
import React, { useEffect, useState } from "react";
import { fmtCurrency, fmtDate } from "@/services/api";
import { CommissionService } from "@/services/commission.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";

export default function Commissions() {
  const [rows, setRows] = useState<Commission[]>([]);
  const { user } = useAuth();

  useEffect(() => {
    CommissionService.getAll()
      .then((data) => setRows(data))
      .catch(() => {});
  }, []);

  const canPayout = user?.role && ["super_admin", "finance_admin"].includes(user.role.toLowerCase());

  const handlePayout = async (id: string) => {
    try {
      await CommissionService.processPayout(id);
      toast.success("Commission payout processed successfully.");
      // Refresh list
      const data = await CommissionService.getAll();
      setRows(data);
    } catch (err: any) {
      toast.error(err.response?.data?.message || err.message || "Failed to process payout.");
    }
  };

  const columns = [
    { key: "createdAt", label: "Date", render: (r: Commission) => <span className="text-xs">{fmtDate(r.createdAt || r.date)}</span> },
    { key: "resellerName", label: "Reseller" },
    { key: "clientName", label: "Client" },
    { key: "invoiceNumber", label: "Invoice", render: (r: Commission) => <span className="font-mono-stat text-xs">{r.invoiceNumber ?? ""}</span> },
    { key: "commissionPct", label: "Rate", render: (r: Commission) => <span className="font-mono-stat text-xs">{r.commissionPct ?? 0}%</span> },
    { key: "amount", label: "Amount", render: (r: Commission) => <span className="font-mono-stat font-medium">{fmtCurrency(r.amount)}</span> },
    { key: "status", label: "Status", render: (r: Commission) => <StatusBadge value={r.status} /> },
    ...(canPayout
      ? [
          {
            key: "actions",
            label: "Actions",
            render: (r: Commission) => {
              if (r.status?.toLowerCase() === "paid") {
                return <span className="text-xs text-zinc-400">Paid</span>;
              }
              return (
                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePayout(r.id.toString());
                  }}
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-none h-7 px-3 text-xs"
                >
                  Pay Commission
                </Button>
              );
            },
          },
        ]
      : []),
  ];

  return (
    <div data-testid="commissions-page">
      <PageHeader title="Reseller commissions" subtitle="Earnings, payouts and pending obligations" />
      <DataTable testId="commissions-table" columns={columns} rows={rows} searchKeys={["resellerName", "clientName", "invoiceNumber"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "pending", label: "Pending" }, { value: "payable", label: "Payable" }, { value: "paid", label: "Paid" }
        ]}]} />
    </div>
  );
}
