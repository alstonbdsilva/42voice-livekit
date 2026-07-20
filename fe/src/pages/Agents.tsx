import { Agent } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtNumber } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Agents() {
  const [rows, setRows] = useState<Agent[]>([]);
  const nav = useNavigate();
  useEffect(() => { api.get("/agents").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "name", label: "Agent", render: (r: Agent) => (
      <div>
        <div className="font-medium">{r.name}</div>
        <div className="text-xs text-zinc-500 font-mono-stat">{r.type}</div>
      </div>
    )},
    { key: "channels", label: "Channels", render: (r: Agent) => (
      <div className="flex flex-wrap gap-1">
        {r.channels.map((c) => (
          <span key={c} className="px-1.5 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">{c}</span>
        ))}
      </div>
    )},
    { key: "totalCalls", label: "Calls", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalCalls)}</span> },
    { key: "totalMessages", label: "Messages", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalMessages)}</span> },
    { key: "totalMinutes", label: "Minutes", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalMinutes)}</span> },
    { key: "successRate", label: "Success", render: (r: Agent) => <span className="font-mono-stat text-emerald-700">{r.successRate}%</span> },
    { key: "escalationRate", label: "Escalation", render: (r: Agent) => <span className="font-mono-stat text-rose-700">{r.escalationRate}%</span> },
    { key: "status", label: "Status", render: (r: Agent) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="agents-page">
      <PageHeader title="AI Agents" subtitle="Production voice & chat agents across all channels" />
      <DataTable
        testId="agents-table" columns={columns} rows={rows} searchKeys={["name", "type"]}
        filters={[{ key: "status", label: "Status", options: [
          { value: "active", label: "Active" }, { value: "paused", label: "Paused" }, { value: "testing", label: "Testing" }
        ]}]}
        onRowClick={(r) => nav(`/agents/${r.id}`)}
      />
    </div>
  );
}
