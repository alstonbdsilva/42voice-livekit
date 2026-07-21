import { Agent, Conversation, Reseller, Client } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtNumber, fmtCurrency, fmtDateTime } from "@/services/api";
import AgentService from "@/services/agent.service";
import ResellerService from "@/services/reseller.service";
import ClientService from "@/services/client.service";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import AppModal from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";
import { ArrowLeft, Pause, Play, Building2, UserCheck, Edit, Sliders, Search } from "lucide-react";

export default function AgentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [a, setA] = useState<Agent | null>(null);
  const [convs, setConvs] = useState<Conversation[]>([]);

  const isAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const isReseller = user?.role === "reseller";
  const canEdit = isAdmin || isReseller;

  // Assignments edit state
  const [allResellers, setAllResellers] = useState<Reseller[]>([]);
  const [allClients, setAllClients] = useState<Client[]>([]);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [assignmentTarget, setAssignmentTarget] = useState<"none" | "reseller" | "client">("none");
  const [selectedResellerIds, setSelectedResellerIds] = useState<string[]>([]);
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);
  const [resellerSearch, setResellerSearch] = useState("");
  const [clientSearch, setClientSearch] = useState("");
  const [savingAssignments, setSavingAssignments] = useState(false);

  // Agent Details edit state
  const [isEditDetailsOpen, setIsEditDetailsOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editUseCase, setEditUseCase] = useState("");
  const [editActivityDesc, setEditActivityDesc] = useState("");
  const [editCallType, setEditCallType] = useState("inbound");
  const [savingDetails, setSavingDetails] = useState(false);

  const load = () => {
    if (!id) return;
    AgentService.getById(id).then((data) => {
      setA(data);
    }).catch(() => {});
    api.get(`/conversations?agentId=${id}&limit=20`).then((r) => setConvs(r.data)).catch(() => {});
  };

  useEffect(() => {
    load();
    if (isAdmin) {
      ResellerService.getAll().then(setAllResellers).catch(() => {});
      ClientService.getAll().then(setAllClients).catch(() => {});
    } else if (isReseller) {
      ClientService.getAll().then(setAllClients).catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isAdmin, isReseller]);

  const toggleStatus = async () => {
    if (!a || !id) return;
    const next = a.status === "active" ? "paused" : "active";
    try {
      await AgentService.updateStatus(id, next);
      toast.success(`Agent ${next}`);
      load();
    } catch { toast.error("Update failed"); }
  };

  const handleOpenAssignModal = () => {
    if (a) {
      const resIds = (a.assignedResellers || []).map((r) => String(r.id));
      const cliIds = (a.assignedClients || []).map((c) => String(c.id));
      setSelectedResellerIds(resIds);
      setSelectedClientIds(cliIds);
      setResellerSearch("");
      setClientSearch("");

      if (resIds.length > 0) {
        setAssignmentTarget("reseller");
      } else if (cliIds.length > 0) {
        setAssignmentTarget("client");
      } else {
        setAssignmentTarget("none");
      }
    }
    setIsAssignModalOpen(true);
  };

  const handleToggleReseller = (rId: string) => {
    setSelectedResellerIds((prev) =>
      prev.includes(rId) ? prev.filter((i) => i !== rId) : [...prev, rId]
    );
  };

  const handleToggleClient = (cId: string) => {
    setSelectedClientIds((prev) =>
      prev.includes(cId) ? prev.filter((i) => i !== cId) : [...prev, cId]
    );
  };

  const handleSaveAssignments = async () => {
    if (!id) return;

    let finalResellerIds: string[] = [];
    let finalClientIds: string[] = [];

    if (assignmentTarget === "reseller") {
      if (selectedResellerIds.length === 0) {
        return toast.error("Please select at least one reseller.");
      }
      finalResellerIds = selectedResellerIds;
    } else if (assignmentTarget === "client") {
      if (selectedClientIds.length === 0) {
        return toast.error("Please select at least one client.");
      }
      finalClientIds = selectedClientIds;
    }

    setSavingAssignments(true);
    try {
      const updatedAgent = await AgentService.updateAssignments(id, finalResellerIds, finalClientIds);
      toast.success("Agent assignment updated successfully!");
      setIsAssignModalOpen(false);

      if (updatedAgent && String(updatedAgent.id) !== String(id)) {
        nav(`/agents/${updatedAgent.id}`, { replace: true });
      } else {
        load();
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to update assignment.");
    } finally {
      setSavingAssignments(false);
    }
  };

  const handleOpenEditDetails = () => {
    if (a) {
      setEditName(a.name || "");
      setEditUseCase(a.useCase || "");
      setEditActivityDesc(a.activityDescription || "");
      setEditCallType(a.callType || "inbound");
    }
    setIsEditDetailsOpen(true);
  };

  const handleSaveDetails = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    if (!editName.trim()) return toast.error("Agent name is required.");

    setSavingDetails(true);
    try {
      await AgentService.updateDetails(id, {
        name: editName.trim(),
        useCase: editUseCase.trim(),
        activityDescription: editActivityDesc.trim(),
        callType: editCallType,
      });
      toast.success("Agent configuration updated successfully!");
      setIsEditDetailsOpen(false);
      load();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to update agent details.");
    } finally {
      setSavingDetails(false);
    }
  };

  if (!a) return <div className="p-6 text-xs text-zinc-500 font-mono-stat">Loading…</div>;

  const assignedResellers = a.assignedResellers || [];
  const assignedClients = a.assignedClients || [];

  const filteredResellers = allResellers.filter((r) =>
    r.name.toLowerCase().includes(resellerSearch.toLowerCase()) ||
    (r.country && r.country.toLowerCase().includes(resellerSearch.toLowerCase()))
  );

  const filteredClients = allClients.filter((c) =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  );

  return (
    <div data-testid="agent-detail" className="space-y-6">
      <div>
        <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
          <ArrowLeft className="w-3 h-3" /> BACK
        </button>
        <PageHeader
          title={a.name}
          subtitle={`${a.type} • ${a.channels.join(", ")} • Prompt ${a.promptVersion} • KB ${a.kbVersion}`}
          actions={(
            <div className="flex items-center gap-2">
              <StatusBadge value={a.status} />
              {canEdit && (
                <button onClick={toggleStatus} data-testid="agent-toggle" className="px-3 py-1.5 border border-zinc-300 text-xs rounded-sm hover:bg-zinc-50 flex items-center gap-1.5">
                  {a.status === "active" ? <><Pause className="w-3 h-3"/> Pause</> : <><Play className="w-3 h-3"/> Resume</>}
                </button>
              )}
            </div>
          )}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total calls" value={fmtNumber(a.totalCalls)} />
        <KpiCard label="Total messages" value={fmtNumber(a.totalMessages)} />
        <KpiCard label="Total minutes" value={fmtNumber(a.totalMinutes)} />
        <KpiCard label="Total cost" value={fmtCurrency(a.totalCost ?? 0)} />
        <KpiCard label="Success rate" value={`${a.successRate}%`} accent="success" />
        <KpiCard label="Escalation rate" value={`${a.escalationRate}%`} accent="danger" />
        <KpiCard label="Last activity" value={fmtDateTime(a.lastActivity ?? "")} />
        <KpiCard label="Channels" value={a.channels.length} />
      </div>

      {/* ── Agent Configuration & Details Section ─────────────────────── */}
      <div className="bg-white border border-zinc-200 rounded-xs p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-zinc-700" /> Agent Configuration & Prompt
            </h3>
            <p className="text-xs text-zinc-500">View and customize agent prompt description and operational use case</p>
          </div>
          <Button variant="outline" size="sm" onClick={handleOpenEditDetails} className="flex items-center gap-1.5 text-xs">
            <Edit className="w-3.5 h-3.5" /> Edit Configuration
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-sm space-y-1">
            <div className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Use Case</div>
            <div className="text-xs font-semibold text-zinc-900">{a.useCase || "Not specified"}</div>
          </div>
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-sm space-y-1">
            <div className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Call Type</div>
            <div className="text-xs font-semibold text-zinc-900 capitalize">{a.callType || "inbound"}</div>
          </div>
        </div>

        <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-sm space-y-1">
          <div className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Activity Description / AI Prompt</div>
          <div className="text-xs text-zinc-800 whitespace-pre-wrap leading-relaxed">
            {a.activityDescription || "No activity description provided."}
          </div>
        </div>
      </div>

      {/* ── Agent Assignment Section ───────────────────────────────────── */}
      <div className="bg-white border border-zinc-200 rounded-xs p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">Agent Assignment</h3>
            <p className="text-xs text-zinc-500">Reseller or Client entity access for this voice agent</p>
          </div>
          {canEdit && (
            <Button variant="outline" size="sm" onClick={handleOpenAssignModal} className="flex items-center gap-1.5 text-xs">
              <Edit className="w-3.5 h-3.5" /> Manage Assignment
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Resellers Card */}
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-sm">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold text-zinc-700">
              <Building2 className="w-4 h-4 text-amber-600" /> Assigned Resellers
            </div>
            {assignedResellers.length === 0 ? (
              <p className="text-xs text-zinc-500 italic">No resellers assigned (Global Admin pool)</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {assignedResellers.map((r) => (
                  <span key={String(r.id)} className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-xs text-xs">
                    {r.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Clients Card */}
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-sm">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold text-zinc-700">
              <UserCheck className="w-4 h-4 text-purple-600" /> Assigned Clients
            </div>
            {assignedClients.length === 0 ? (
              <p className="text-xs text-zinc-500 italic">No clients assigned</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {assignedClients.map((c) => (
                  <span key={String(c.id)} className="inline-flex items-center gap-1 px-2 py-1 bg-purple-50 text-purple-800 border border-purple-200 rounded-xs text-xs">
                    {c.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white border border-zinc-200">
        <div className="px-5 py-3 border-b border-zinc-200"><div className="label-tiny">RECENT CONVERSATIONS</div></div>
        <div className="divide-y divide-zinc-100">
          {convs.map((c) => (
            <div key={c.id} className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50" onClick={() => nav(`/conversations/${c.id}`)}>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{c.customerName}</div>
                <div className="text-xs text-zinc-500 truncate">{c.summary}</div>
              </div>
              <span className="text-xs font-mono-stat text-zinc-500">{c.channel}</span>
              <StatusBadge value={c.outcome} />
            </div>
          ))}
        </div>
      </div>

      {/* ── Manage Assignments Modal ────────────────────────────────────── */}
      <AppModal
        open={isAssignModalOpen}
        onClose={() => setIsAssignModalOpen(false)}
        title="Manage Agent Assignment"
        description={`Configure reseller or client assignment for ${a.name}`}
        showFooter={false}
      >
        <div className="space-y-4 py-1">
          {/* Assignment Target Choice */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Assign To</Label>
            <select
              value={assignmentTarget}
              onChange={(e) => {
                const val = e.target.value as "none" | "reseller" | "client";
                setAssignmentTarget(val);
                if (val === "none") {
                  setSelectedResellerIds([]);
                  setSelectedClientIds([]);
                }
              }}
              className="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-950"
            >
              <option value="none">Unassigned (Admin Pool / Global)</option>
              {isAdmin && <option value="reseller">Resellers</option>}
              <option value="client">Clients</option>
            </select>
          </div>

          {/* Resellers Selection (Multi-select with Search) */}
          {assignmentTarget === "reseller" && isAdmin && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Select Resellers *</Label>
                {selectedResellerIds.length > 0 && (
                  <span className="text-[11px] font-medium text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                    {selectedResellerIds.length} Selected
                  </span>
                )}
              </div>

              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-400" />
                <Input
                  placeholder="Search resellers..."
                  value={resellerSearch}
                  onChange={(e) => setResellerSearch(e.target.value)}
                  className="pl-8 h-8 text-xs bg-white"
                />
              </div>

              <div className="max-h-44 overflow-y-auto border border-zinc-200 rounded-md p-2 space-y-1 bg-zinc-50">
                {filteredResellers.length === 0 ? (
                  <p className="text-xs text-zinc-400 p-1">No matching resellers found.</p>
                ) : (
                  filteredResellers.map((r) => {
                    const isChecked = selectedResellerIds.includes(String(r.id));
                    return (
                      <label
                        key={String(r.id)}
                        className={`flex items-center justify-between text-xs p-1.5 rounded cursor-pointer transition-colors ${
                          isChecked ? "bg-amber-100/60 text-amber-900 font-medium" : "text-zinc-700 hover:bg-zinc-100"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleReseller(String(r.id))}
                            className="rounded border-zinc-300 text-amber-600 focus:ring-0"
                          />
                          <span>{r.name}</span>
                        </div>
                        {r.country && <span className="text-[10px] text-zinc-500 font-normal">{r.country}</span>}
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* Clients Selection (Multi-select with Search) */}
          {assignmentTarget === "client" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Select Clients *</Label>
                {selectedClientIds.length > 0 && (
                  <span className="text-[11px] font-medium text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                    {selectedClientIds.length} Selected
                  </span>
                )}
              </div>

              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-400" />
                <Input
                  placeholder="Search clients..."
                  value={clientSearch}
                  onChange={(e) => setClientSearch(e.target.value)}
                  className="pl-8 h-8 text-xs bg-white"
                />
              </div>

              <div className="max-h-44 overflow-y-auto border border-zinc-200 rounded-md p-2 space-y-1 bg-zinc-50">
                {filteredClients.length === 0 ? (
                  <p className="text-xs text-zinc-400 p-1">No matching clients found.</p>
                ) : (
                  filteredClients.map((c) => {
                    const isChecked = selectedClientIds.includes(String(c.id));
                    return (
                      <label
                        key={String(c.id)}
                        className={`flex items-center justify-between text-xs p-1.5 rounded cursor-pointer transition-colors ${
                          isChecked ? "bg-purple-100/60 text-purple-900 font-medium" : "text-zinc-700 hover:bg-zinc-100"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleClient(String(c.id))}
                            className="rounded border-zinc-300 text-purple-600 focus:ring-0"
                          />
                          <span>{c.name}</span>
                        </div>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button variant="outline" size="sm" onClick={() => setIsAssignModalOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSaveAssignments} disabled={savingAssignments}>
              {savingAssignments ? "Saving..." : "Save Assignment"}
            </Button>
          </div>
        </div>
      </AppModal>

      {/* ── Edit Configuration Modal ────────────────────────────────────── */}
      <AppModal
        open={isEditDetailsOpen}
        onClose={() => setIsEditDetailsOpen(false)}
        title="Edit Agent Configuration"
        description="Modify agent details and AI prompt instructions"
        showFooter={false}
      >
        <form onSubmit={handleSaveDetails} className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label htmlFor="edit-name" className="text-xs font-medium">Agent Name *</Label>
            <Input
              id="edit-name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-call-type" className="text-xs font-medium">Call Type</Label>
            <select
              id="edit-call-type"
              value={editCallType}
              onChange={(e) => setEditCallType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-950"
            >
              <option value="inbound">Inbound (Users call AI)</option>
              <option value="outbound">Outbound (AI calls Users)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-use-case" className="text-xs font-medium">Use Case</Label>
            <Input
              id="edit-use-case"
              value={editUseCase}
              onChange={(e) => setEditUseCase(e.target.value)}
              placeholder="e.g. Lead Qualification, Customer Support"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-activity-desc" className="text-xs font-medium">Activity Description / Prompt</Label>
            <Textarea
              id="edit-activity-desc"
              rows={4}
              value={editActivityDesc}
              onChange={(e) => setEditActivityDesc(e.target.value)}
              placeholder="Describe what your voice agent will do..."
              className="text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsEditDetailsOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={savingDetails}>
              {savingDetails ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </form>
      </AppModal>
    </div>
  );
}
