import { DashboardSummary, Notification, Renewal, UserRole } from "@/types";
import React, { useEffect, useState } from "react";
import { api, fmtCurrency, fmtNumber } from "@/services/api";
import { useAuth } from "@/store/authStore";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar
} from "recharts";

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [renewals, setRenewals] = useState<Renewal[]>([]);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setData(r.data)).catch(() => {});
    api.get("/notifications").then((r) => setNotifications(r.data.slice(0, 6))).catch(() => {});
    api.get("/renewals").then((r) => setRenewals(r.data.slice(0, 6))).catch(() => {});
  }, []);

  if (!data) return <div className="label-tiny" data-testid="dashboard-loading">Loading…</div>;

  const t = data.totals;
  const isExec = user?.role === "super_admin" || user?.role === "finance_admin";
  const titles: Record<UserRole, string> = {
    super_admin: "Executive command centre",
    finance_admin: "Finance dashboard",
    reseller: "Reseller dashboard",
    client: "Client portal",
  };

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title={(user?.role && titles[user.role as UserRole]) || "Dashboard"}
        subtitle={`Welcome back, ${user?.name}. Here's what's happening across your portfolio.`}
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
        {isExec && (
          <>
            <KpiCard testId="kpi-revenue-collected" label="Revenue collected" value={fmtCurrency(t.revenueCollected)} sub="Lifetime payments" accent="success" />
            <KpiCard testId="kpi-revenue-due" label="Revenue due" value={fmtCurrency(t.revenueDue)} sub="Outstanding receivables" accent="warning" />
            <KpiCard testId="kpi-revenue-overdue" label="Revenue overdue" value={fmtCurrency(t.revenueOverdue)} accent="danger" />
            <KpiCard testId="kpi-pending-invoices" label="Pending invoices" value={fmtNumber(t.pendingInvoices)} />
            <KpiCard testId="kpi-mrr" label="MRR" value={fmtCurrency(t.mrr)} sub={`ARR ${fmtCurrency(t.arr)}`} />
            <KpiCard testId="kpi-active-clients" label="Active clients" value={fmtNumber(t.activeClients)} />
            <KpiCard testId="kpi-active-resellers" label="Active resellers" value={fmtNumber(t.activeResellers)} />
            <KpiCard testId="kpi-active-agents" label="Active AI agents" value={fmtNumber(t.activeAgents)} />
          </>
        )}
        {user?.role === "reseller" && (
          <>
            <KpiCard testId="kpi-clients" label="Clients" value={fmtNumber(t.activeClients)} />
            <KpiCard testId="kpi-revenue" label="Revenue managed" value={fmtCurrency(t.revenueCollected)} accent="success" />
            <KpiCard testId="kpi-due" label="Outstanding" value={fmtCurrency(t.revenueDue)} accent="warning" />
            <KpiCard testId="kpi-overdue" label="Overdue" value={fmtCurrency(t.revenueOverdue)} accent="danger" />
            <KpiCard testId="kpi-agents" label="AI agents" value={fmtNumber(t.activeAgents)} />
            <KpiCard testId="kpi-calls" label="Calls" value={fmtNumber(t.totalCalls)} />
            <KpiCard testId="kpi-messages" label="Messages" value={fmtNumber(t.totalMessages)} />
            <KpiCard testId="kpi-minutes" label="Minutes" value={fmtNumber(t.totalMinutes)} />
          </>
        )}
        {user?.role === "client" && (
          <>
            <KpiCard testId="kpi-spend" label="This month spend" value={fmtCurrency(t.mrr)} />
            <KpiCard testId="kpi-outstanding" label="Outstanding" value={fmtCurrency(t.revenueDue)} accent="warning" />
            <KpiCard testId="kpi-overdue" label="Overdue" value={fmtCurrency(t.revenueOverdue)} accent="danger" />
            <KpiCard testId="kpi-agents" label="AI agents deployed" value={fmtNumber(t.activeAgents)} />
            <KpiCard testId="kpi-calls" label="Total calls" value={fmtNumber(t.totalCalls)} />
            <KpiCard testId="kpi-messages" label="Total messages" value={fmtNumber(t.totalMessages)} />
            <KpiCard testId="kpi-minutes" label="Total minutes" value={fmtNumber(t.totalMinutes)} />
            <KpiCard testId="kpi-convos" label="Conversations" value={fmtNumber(t.totalConversations)} />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2 bg-white border border-zinc-200 p-5">
          <div className="flex items-baseline justify-between mb-4">
            <div>
              <div className="label-tiny">COLLECTIONS — LAST 6 MONTHS</div>
              <div className="font-display text-xl font-semibold mt-1">{fmtCurrency(t.revenueCollected)}</div>
            </div>
            <div className="label-tiny">USD</div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.monthlyTrend}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0a0a0a" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#0a0a0a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#f4f4f5" vertical={false} />
              <XAxis dataKey="month" stroke="#a1a1aa" fontSize={11} />
              <YAxis stroke="#a1a1aa" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e4e4e7", borderRadius: 2 }} formatter={(v: any) => fmtCurrency(Number(v))} />
              <Area type="monotone" dataKey="collected" stroke="#0a0a0a" fill="url(#g1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-zinc-200 p-5">
          <div className="label-tiny mb-4">AGEING — OUTSTANDING</div>
          <div className="space-y-3">
            {Object.entries(data.ageing ?? {}).map(([bucket, val]) => {
              const total = Object.values(data.ageing ?? {}).reduce((a: number, b: number) => a + b, 0) || 1;
              const pct = (val / total) * 100;
              const color = bucket === "0-30" ? "bg-amber-500" : bucket === "31-60" ? "bg-orange-500" : bucket === "61-90" ? "bg-rose-500" : "bg-rose-700";
              return (
                <div key={bucket} data-testid={`ageing-${bucket}`}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-mono-stat text-zinc-700">{bucket} DAYS</span>
                    <span className="font-mono-stat font-semibold">{fmtCurrency(val)}</span>
                  </div>
                  <div className="h-1.5 bg-zinc-100 rounded-sm overflow-hidden">
                    <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="border-t border-zinc-100 mt-4 pt-3 grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="label-tiny">30d</div>
              <div className="font-mono-stat text-sm font-semibold">{data.contractsExpiring?.["30"] ?? 0}</div>
            </div>
            <div>
              <div className="label-tiny">60d</div>
              <div className="font-mono-stat text-sm font-semibold">{data.contractsExpiring?.["60"] ?? 0}</div>
            </div>
            <div>
              <div className="label-tiny">90d</div>
              <div className="font-mono-stat text-sm font-semibold">{data.contractsExpiring?.["90"] ?? 0}</div>
            </div>
          </div>
          <div className="label-tiny mt-2 text-center">CONTRACTS EXPIRING</div>
        </div>
      </div>

      {/* Revenue by client/reseller */}
      {((data.revenueByClient?.length ?? 0) > 0 || (data.revenueByReseller?.length ?? 0) > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {(data.revenueByClient?.length ?? 0) > 0 && (
            <div className="bg-white border border-zinc-200 p-5">
              <div className="label-tiny mb-4">REVENUE BY CLIENT (TOP 10)</div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.revenueByClient ?? []} layout="vertical" margin={{ left: 0, right: 8 }}>
                  <XAxis type="number" stroke="#a1a1aa" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="name" stroke="#71717a" fontSize={11} width={140} />
                  <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e4e4e7", borderRadius: 2 }} formatter={(v: any) => fmtCurrency(Number(v))} />
                  <Bar dataKey="value" fill="#0a0a0a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {(data.revenueByReseller?.length ?? 0) > 0 && isExec && (
            <div className="bg-white border border-zinc-200 p-5">
              <div className="label-tiny mb-4">REVENUE BY RESELLER</div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.revenueByReseller ?? []} layout="vertical" margin={{ left: 0, right: 8 }}>
                  <XAxis type="number" stroke="#a1a1aa" fontSize={11} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="name" stroke="#71717a" fontSize={11} width={160} />
                  <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e4e4e7", borderRadius: 2 }} formatter={(v: any) => fmtCurrency(Number(v))} />
                  <Bar dataKey="value" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Recent activity & alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <div className="label-tiny">PRIORITY ALERTS</div>
            <a href="/notifications" className="text-xs text-zinc-500 hover:text-zinc-950">VIEW ALL →</a>
          </div>
          <div className="divide-y divide-zinc-100" data-testid="dashboard-alerts">
            {notifications.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No active alerts</div>}
            {notifications.map((n) => (
              <div key={n.id} className="px-5 py-3 flex items-start gap-3">
                <StatusBadge value={n.priority} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-zinc-900 truncate">{n.title}</div>
                  <div className="text-xs text-zinc-500 truncate">{n.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <div className="label-tiny">UPCOMING RENEWALS</div>
            <a href="/renewals" className="text-xs text-zinc-500 hover:text-zinc-950">VIEW ALL →</a>
          </div>
          <div className="divide-y divide-zinc-100" data-testid="dashboard-renewals">
            {renewals.length === 0 && <div className="px-5 py-6 text-sm text-zinc-400">No upcoming renewals</div>}
            {renewals.map((r) => (
              <div key={r.id} className="px-5 py-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-zinc-900 truncate">{r.clientName}</div>
                  <div className="text-xs text-zinc-500">
                    Renews {new Date(r.renewalDate ?? r.date).toLocaleDateString()} • {fmtCurrency(r.value)}
                  </div>
                </div>
                <StatusBadge value={r.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
