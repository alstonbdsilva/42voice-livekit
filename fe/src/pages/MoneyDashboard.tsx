import { DashboardMoney } from "@/types";
import React, { useEffect, useState } from "react";
import { fmtCurrency, fmtNumber } from "@/services/api";
import { FinanceService } from "@/services/finance.service";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";

export default function MoneyDashboard() {
  const [data, setData] = useState<DashboardMoney | null>(null);

  useEffect(() => {
    FinanceService.getDashboardMoney().then((data) => setData(data)).catch(() => {});
  }, []);

  if (!data) return <div className="label-tiny" data-testid="money-loading">Loading…</div>;

  const t = data.totals;

  return (
    <div data-testid="money-page">
      <PageHeader
        title="Money command centre"
        subtitle="Consolidated view of collections, receivables, commissions, and platform margin."
      />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard testId="money-collected" label="Total collected" value={fmtCurrency(t.totalCollected ?? 0)} accent="success" />
        <KpiCard testId="money-available" label="Available cash" value={fmtCurrency(t.totalAvailable ?? 0)} sub="Post commissions & platform cost" />
        <KpiCard testId="money-due" label="Total due" value={fmtCurrency(t.totalDue ?? 0)} accent="warning" />
        <KpiCard testId="money-overdue" label="Total overdue" value={fmtCurrency(t.totalOverdue ?? 0)} accent="danger" />
        <KpiCard testId="money-gross-rev" label="Gross revenue" value={fmtCurrency(t.grossRevenue ?? 0)} />
        <KpiCard testId="money-net-rev" label="Net revenue" value={fmtCurrency(t.netRevenue ?? 0)} accent="success" />
        <KpiCard testId="money-margin" label="Gross margin" value={`${t.grossMargin ?? 0}%`} />
        <KpiCard testId="money-platform-cost" label="Platform cost" value={fmtCurrency(t.platformCost ?? 0)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny">INVOICES RAISED</div>
          <div className="font-mono-stat text-3xl font-semibold mt-2">{fmtNumber(t.totalInvoicesRaised ?? 0)}</div>
        </div>
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny">INVOICES UNPAID</div>
          <div className="font-mono-stat text-3xl font-semibold mt-2 text-amber-700">{fmtNumber(t.totalInvoicesUnpaid ?? 0)}</div>
        </div>
        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny">INVOICES PARTIAL</div>
          <div className="font-mono-stat text-3xl font-semibold mt-2 text-zinc-700">{fmtNumber(t.totalInvoicesPartial ?? 0)}</div>
        </div>
      </div>

      <div className="bg-white border border-zinc-200 p-5">
        <div className="label-tiny mb-3">COMMISSIONS PAYABLE TO RESELLERS</div>
        <div className="font-mono-stat text-4xl font-semibold text-zinc-950">{fmtCurrency(t.commissionPayable ?? 0)}</div>
        <p className="text-sm text-zinc-500 mt-2">Pending commission obligations across all reseller partners. Process payouts from the Commissions module.</p>
      </div>
    </div>
  );
}
