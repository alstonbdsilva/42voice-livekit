import { Agent } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fmtNumber } from "@/services/api";
import AgentService, { CreateAgentDto } from "@/services/agent.service";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Bot, PhoneIncoming, PhoneOutgoing, Building2, UserCheck } from "lucide-react";
import { toast } from "sonner";

export default function Agents() {
  const nav = useNavigate();

  const [rows, setRows] = useState<Agent[]>([]);

  // Modal & form states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("");
  const [callType, setCallType] = useState("inbound");
  const [useCase, setUseCase] = useState("");
  const [activityDescription, setActivityDescription] = useState("");

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

  const resetForm = () => {
    setName("");
    setCallType("inbound");
    setUseCase("");
    setActivityDescription("");
  };

  const closeCreate = () => {
    setIsCreateOpen(false);
    resetForm();
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return toast.error("Agent name is required.");

    setLoading(true);
    try {
      const dto: CreateAgentDto = {
        name: name.trim(),
        callType,
        useCase: useCase.trim(),
        activityDescription: activityDescription.trim(),
      };

      await AgentService.create(dto);
      toast.success("Voice Agent created successfully!");
      closeCreate();
      fetchAgents();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to create voice agent.");
    } finally {
      setLoading(false);
    }
  };

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
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-1.5" data-testid="create-agent-btn">
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

      {/* ── Create Voice Agent Modal ─────────────────────────────────────── */}
      <AppModal
        open={isCreateOpen}
        onClose={closeCreate}
        title="Create Voice Agent"
        description="Tell us about your use case and we'll create a customized voice agent for you"
        maxWidth="sm:max-w-[560px]"
        showFooter={false}
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 pt-1">
          {/* Agent Name */}
          <div className="space-y-1.5">
            <Label htmlFor="agent-name" className="text-xs font-medium">
              Agent Name *
            </Label>
            <Input
              id="agent-name"
              placeholder="e.g., Customer Support Voice Assistant"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          {/* Call Type Dropdown */}
          <div className="space-y-1.5">
            <Label htmlFor="call-type" className="text-xs font-medium">
              Call Type
            </Label>
            <select
              id="call-type"
              value={callType}
              onChange={(e) => setCallType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-950"
            >
              <option value="inbound">Inbound (Users call AI)</option>
              <option value="outbound">Outbound (AI calls Users)</option>
            </select>
            <p className="text-[11px] text-zinc-500">Choose whether users will call your AI or your AI will call users</p>
          </div>

          {/* Use Case */}
          <div className="space-y-1.5">
            <Label htmlFor="use-case" className="text-xs font-medium">
              Use Case
            </Label>
            <Input
              id="use-case"
              placeholder="e.g., Lead Qualification, HR Screening, Customer Support"
              value={useCase}
              onChange={(e) => setUseCase(e.target.value)}
            />
            <p className="text-[11px] text-zinc-500">Describe the primary purpose of your voice agent</p>
          </div>

          {/* Activity Description */}
          <div className="space-y-1.5">
            <Label htmlFor="activity-description" className="text-xs font-medium">
              Activity Description
            </Label>
            <Textarea
              id="activity-description"
              rows={3}
              placeholder="Describe briefly what your voice agent will do (e.g., Qualify leads for real estate, Screen candidates for roles, Handle customer support)."
              value={activityDescription}
              onChange={(e) => setActivityDescription(e.target.value)}
              className="text-xs"
            />
            <p className="text-[11px] text-zinc-500">This description will be used to generate the AI prompt for your voice agent</p>
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={closeCreate}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="min-w-[120px]">
              {loading ? "Creating..." : "Create Agent"}
            </Button>
          </div>
        </form>
      </AppModal>
    </div>
  );
}
