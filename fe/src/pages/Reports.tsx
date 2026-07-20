import React, { useState } from "react";
import { api, fmtCurrency } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import { Download } from "lucide-react";
import { toast } from "sonner";

interface BucketRow {
  invoice: string;
  client: string;
  amount: number;
  daysOverdue: number;
  [key: string]: any;
}

interface ReportData {
  rows?: Record<string, any>[];
  buckets?: Record<string, BucketRow[]>;
}

const reports = [
  { kind: "client_spend", title: "Client spend", desc: "Invoiced, paid and outstanding amounts per client" },
  { kind: "agent_performance", title: "Agent performance", desc: "Calls, messages, minutes, success and escalation per agent" },
  { kind: "ageing", title: "Ageing report", desc: "0–30, 31–60, 61–90, 90+ days overdue receivables" },
];

function toCSV(rows: Record<string, any>[]) {
  if (!rows || rows.length === 0) return "";
  const keys = Object.keys(rows[0]);
  return [keys.join(","), ...rows.map((r) => keys.map((k) => JSON.stringify(r[k] ?? "")).join(","))].join("\n");
}

export default function Reports() {
  const [active, setActive] = useState<string | null>(null);
  const [data, setData] = useState<ReportData | null>(null);

  const run = async (kind: string) => {
    setActive(kind); 
    setData(null);
    try {
      const r = await api.get<{ data: ReportData }>(`/reports/${kind}`);
      setData(r.data);
    } catch { 
      toast.error("Report failed"); 
    }
  };

  const download = () => {
    if (!data) return;
    const flatRows: Record<string, any>[] = data.rows || Object.entries(data.buckets || {}).flatMap(([b, rs]) => rs.map((x) => ({ bucket: b, ...x })));
    const csv = toCSV(flatRows);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; 
    a.download = `${active}.csv`; 
    a.click();
  };

  return (
    <div data-testid="reports-page">
      <PageHeader title="Reports" subtitle="Generate financial and operational reports" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {reports.map((r) => (
          <button key={r.kind} onClick={() => run(r.kind)} data-testid={`report-${r.kind}`}
            className={`text-left p-5 bg-white border ${active === r.kind ? "border-zinc-950" : "border-zinc-200"} hover:border-zinc-950 transition-colors`}>
            <div className="label-tiny">{r.kind.replace("_", " ")}</div>
            <div className="font-display text-lg font-semibold mt-1">{r.title}</div>
            <div className="text-xs text-zinc-500 mt-1">{r.desc}</div>
          </button>
        ))}
      </div>

      {data && active && (
        <div className="bg-white border border-zinc-200">
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <div className="label-tiny">{active.replace("_", " ").toUpperCase()}</div>
            <button onClick={download} data-testid="download-report" className="text-xs text-zinc-500 hover:text-zinc-950 flex items-center gap-1">
              <Download className="w-3 h-3" /> EXPORT CSV
            </button>
          </div>
          {data.rows && (
            <table className="w-full text-sm" data-testid="report-table">
              <thead>
                <tr>
                  {Object.keys(data.rows[0] || {}).map((k) => (
                    <th key={k} className="px-4 py-2 text-left label-tiny bg-zinc-50 border-b border-zinc-200">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={`row-${i}`} className="border-b border-zinc-100">
                    {Object.entries(row).map(([k, v]) => (
                      <td key={k} className="px-4 py-2 font-mono-stat text-sm">
                        {typeof v === "number" && (k.includes("amount") || k.includes("paid") || k.includes("invoiced") || k.includes("outstanding")) ? fmtCurrency(v) : String(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {data.buckets && (
            <div className="p-5 space-y-4">
              {Object.entries(data.buckets).map(([bucket, rows]) => (
                <div key={bucket}>
                  <div className="label-tiny mb-2">{bucket} DAYS — {rows.length} INVOICES — {fmtCurrency(rows.reduce((a, r) => a + r.amount, 0))}</div>
                  {rows.length > 0 ? (
                    <table className="w-full text-sm">
                      <thead><tr><th className="px-3 py-1 text-left label-tiny bg-zinc-50">Invoice</th><th className="px-3 py-1 text-left label-tiny bg-zinc-50">Client</th><th className="px-3 py-1 text-right label-tiny bg-zinc-50">Amount</th><th className="px-3 py-1 text-right label-tiny bg-zinc-50">Days</th></tr></thead>
                      <tbody>{rows.map((r, i) => (
                        <tr key={`${r.invoice}-${i}`} className="border-t border-zinc-100">
                          <td className="px-3 py-1 font-mono-stat text-xs">{r.invoice}</td>
                          <td className="px-3 py-1 text-xs">{r.client}</td>
                          <td className="px-3 py-1 text-right font-mono-stat text-xs">{fmtCurrency(r.amount)}</td>
                          <td className="px-3 py-1 text-right font-mono-stat text-xs">{r.daysOverdue}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  ) : <div className="text-xs text-zinc-400">None</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
