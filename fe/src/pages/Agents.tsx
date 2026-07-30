import { Agent } from "@/types";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtNumber } from "@/services/api";
import AgentService from "@/services/agent.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Plus, Bot, PhoneIncoming, PhoneOutgoing, Building2, UserCheck } from "lucide-react";

export default function Agents() {
  const nav = useNavigate();

  const [rows, setRows] = useState<Agent[]>([]);

  const fetchAgents = async () => {
    try {
      const data = await AgentService.getAll();
      setRows(data);
    } catch {
      /* fallback */
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const columns = [
    {
      key: "name",
      label: "Agent",
      render: (r: Agent) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-zinc-900 text-white flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <div className="font-medium text-zinc-950 flex items-center gap-1.5">
              {r.name}
              {r.callType === "outbound" ? (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-700 border border-blue-200 rounded-xs">
                  <PhoneOutgoing className="w-2.5 h-2.5" /> Outbound
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-xs">
                  <PhoneIncoming className="w-2.5 h-2.5" /> Inbound
                </span>
              )}
            </div>
            {r.useCase && <div className="text-xs text-zinc-500 font-normal">{r.useCase}</div>}
          </div>
        </div>
      ),
    },
    {
      key: "assignments",
      label: "Assigned To",
      render: (r: Agent) => {
        const resellersList = r.assignedResellers || [];
        const clientsList = r.assignedClients || [];
        const isUnassigned = resellersList.length === 0 && clientsList.length === 0;

        if (isUnassigned) {
          return (
            <span className="px-2 py-0.5 bg-zinc-100 text-zinc-600 text-xs font-medium rounded-sm border border-zinc-200">
              Admin Bucket
            </span>
          );
        }

        return (
          <div className="flex flex-wrap gap-1 max-w-[220px]">
            {resellersList.map((res) => (
              <span
                key={String(res.id)}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-amber-50 text-amber-800 text-[10px] rounded-xs border border-amber-200"
                title={`Reseller: ${res.name}`}
              >
                <Building2 className="w-3 h-3 text-amber-600" />
                {res.name}
              </span>
            ))}
            {clientsList.map((cli) => (
              <span
                key={String(cli.id)}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-purple-50 text-purple-800 text-[10px] rounded-xs border border-purple-200"
                title={`Client: ${cli.name}`}
              >
                <UserCheck className="w-3 h-3 text-purple-600" />
                {cli.name}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      key: "channels",
      label: "Channels",
      render: (r: Agent) => (
        <div className="flex flex-wrap gap-1">
          {r.channels.map((c) => (
            <span key={c} className="px-1.5 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">
              {c}
            </span>
          ))}
        </div>
      ),
    },
    { key: "totalCalls", label: "Calls", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalCalls)}</span> },
    { key: "totalMessages", label: "Messages", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalMessages)}</span> },
    { key: "totalMinutes", label: "Minutes", render: (r: Agent) => <span className="font-mono-stat">{fmtNumber(r.totalMinutes)}</span> },
    { key: "successRate", label: "Success", render: (r: Agent) => <span className="font-mono-stat text-emerald-700">{r.successRate}%</span> },
    { key: "escalationRate", label: "Escalation", render: (r: Agent) => <span className="font-mono-stat text-rose-700">{r.escalationRate}%</span> },
    { key: "status", label: "Status", render: (r: Agent) => <StatusBadge value={r.status} /> },
  ];

  return (
    <div data-testid="agents-page">
      <PageHeader
        title="AI Agents"
        subtitle="Production voice & chat agents across all channels"
        actions={
          <Button onClick={() => nav("/agents/create")} className="flex items-center gap-1.5" data-testid="create-agent-btn">
            <Plus className="w-4 h-4" /> Create Agent
          </Button>
        }
      />

      <DataTable
        testId="agents-table"
        columns={columns}
        rows={rows}
        searchKeys={["name", "type", "useCase"]}
        filters={[
          {
            key: "status",
            label: "Status",
            options: [
              { value: "active", label: "Active" },
              { value: "paused", label: "Paused" },
              { value: "testing", label: "Testing" },
            ],
          },
        ]}
        onRowClick={(r) => nav(`/agents/${r.id}`)}
      />
    </div>
  );
}
