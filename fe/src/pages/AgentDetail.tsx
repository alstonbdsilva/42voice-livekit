import { Agent, Conversation, Reseller, Client, Tool } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtNumber, fmtCurrency, fmtDateTime } from "@/services/api";
import AgentService from "@/services/agent.service";
import ResellerService from "@/services/reseller.service";
import ClientService from "@/services/client.service";
import PhoneNumberService from "@/services/phone-number.service";
import ToolsService from "@/services/tools.service";
import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/store/authStore";
import { toast } from "sonner";
import ElevenLabsVoiceSelector from "@/components/voice/ElevenLabsVoiceSelector";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  ArrowLeft,
  Pause,
  Play,
  Building2,
  UserCheck,
  Edit,
  Sliders,
  Search,
  Sparkles,
  MessageSquareText,
  BookOpen,
  Mic2,
  Upload,
  Link2,
  FileText,
  Plus,
  File as FileIcon,
  Trash2,
  ShieldCheck
} from "lucide-react";

const VOICE_OPTIONS = [
  { value: "aria", label: "Aria", gender: "female" },
  { value: "luna", label: "Luna", gender: "female" },
  { value: "nova", label: "Nova", gender: "female" },
  { value: "atlas", label: "Atlas", gender: "male" },
  { value: "orion", label: "Orion", gender: "male" },
  { value: "sage", label: "Sage", gender: "male" },
];

const PROMPT_TEMPLATES = [
  {
    label: "Lead Qualification",
    text: "You are an AI assistant qualifying real estate leads. Your goal is to gather the budget, location preference, and timeline. Keep it friendly and concise.",
  },
  {
    label: "Customer Support",
    text: "You are a customer support agent. Help the user troubleshoot issues. Be empathetic, polite, and guide them to resolution steps.",
  },
  {
    label: "Booking Assistant",
    text: "You are a friendly receptionist at a dental clinic. Assist users in scheduling, rescheduling, or canceling appointments.",
  },
];

const DEFAULT_GUARDRAILS = {
  blockProfanity: true,
  piiRedaction: false,
  restrictOffTopic: true,
  requireDisclaimer: true,
  escalateOnFrustration: true,
};

const ACCEPTED_KB_FILE_TYPES = ".pdf,.doc,.docx,.txt,.md,.csv,.json";

export default function AgentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [a, setA] = useState<Agent | null>(null);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [activeTab, setActiveTab] = useState("basic");

  const isAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const isReseller = user?.role === "reseller";
  const isClient = user?.role === "client";
  const canEdit = isAdmin || isReseller || isClient;

  // Assignments edit state
  const [allResellers, setAllResellers] = useState<Reseller[]>([]);
  const [allClients, setAllClients] = useState<Client[]>([]);
  const [assignmentTarget, setAssignmentTarget] = useState<"none" | "reseller" | "client">("none");
  const [selectedResellerIds, setSelectedResellerIds] = useState<string[]>([]);
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);
  const [resellerSearch, setResellerSearch] = useState("");
  const [clientSearch, setClientSearch] = useState("");

  // Agent Details edit state
  const [editName, setEditName] = useState("");
  const [editUseCase, setEditUseCase] = useState("");
  const [editActivityDesc, setEditActivityDesc] = useState("");
  const [editCallType, setEditCallType] = useState("inbound");
  const [editVoiceGender, setEditVoiceGender] = useState<"female" | "male">("female");
  const [editVoiceName, setEditVoiceName] = useState("aria");
  const [editGuardrails, setEditGuardrails] = useState<any>(DEFAULT_GUARDRAILS);
  const [editCustomGuardrails, setEditCustomGuardrails] = useState("");
  const [editKnowledgeItems, setEditKnowledgeItems] = useState<any[]>([]);
  const [selectedPhoneNumberId, setSelectedPhoneNumberId] = useState<string>("none");
  const [phoneNumbers, setPhoneNumbers] = useState<any[]>([]);
  const [savingDetails, setSavingDetails] = useState(false);

  // Tools edit state
  const [allTools, setAllTools] = useState<Tool[]>([]);
  const [editToolIds, setEditToolIds] = useState<string[]>([]);

  const isSuperAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const userOwnerId = user?.clientId || user?.resellerId || user?.id;

  const filteredNumbersForDropdown = phoneNumbers.filter((num) => {
    if (isSuperAdmin) return true;
    const numOwnerId = num.clientId || num.resellerId;
    return numOwnerId && String(numOwnerId) === String(userOwnerId);
  });

  const connectedNumbers = filteredNumbersForDropdown.filter(
    (num) => num.agentId && String(num.agentId) === String(id)
  );

  // Knowledge base edit helpers
  const [kbUrlInput, setKbUrlInput] = useState("");
  const [kbTextInput, setKbTextInput] = useState("");
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const addKnowledgeUrl = () => {
    if (!kbUrlInput.trim()) return;
    const url = kbUrlInput.trim();
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      return toast.error("Please enter a valid HTTP/HTTPS URL.");
    }
    const itemId = `url-${Date.now()}`;
    setEditKnowledgeItems((prev) => [
      ...prev,
      { id: itemId, type: "url", label: url, value: url },
    ]);
    setKbUrlInput("");
  };

  const addKnowledgeText = () => {
    if (!kbTextInput.trim()) return;
    const snippet = kbTextInput.trim();
    const itemId = `text-${Date.now()}`;
    const truncatedLabel = snippet.length > 30 ? snippet.substring(0, 30) + "..." : snippet;
    setEditKnowledgeItems((prev) => [
      ...prev,
      { id: itemId, type: "text", label: truncatedLabel, value: snippet },
    ]);
    setKbTextInput("");
  };

  const addKnowledgeFiles = async (files: FileList) => {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`File ${file.name} exceeds the 10MB limit.`);
        continue;
      }
      const tempId = `file-${Date.now()}-${i}`;
      setEditKnowledgeItems((prev) => [
        ...prev,
        { id: tempId, type: "file", label: `${file.name} (Uploading...)`, value: "", size: file.size },
      ]);
      try {
        const uploadData = await AgentService.uploadFile(file);
        setEditKnowledgeItems((prev) =>
          prev.map((item) =>
            item.id === tempId
              ? { ...item, label: file.name, value: uploadData.s3Url }
              : item
          )
        );
        toast.success(`Successfully uploaded ${file.name}`);
      } catch (err: any) {
        toast.error(`Failed to upload ${file.name}`);
        setEditKnowledgeItems((prev) => prev.filter((item) => item.id !== tempId));
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addKnowledgeFiles(e.target.files);
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingFile(false);
    if (!canEdit) return;
    if (e.dataTransfer.files) addKnowledgeFiles(e.dataTransfer.files);
  };

  const removeKnowledgeItem = (itemId: string) => {
    setEditKnowledgeItems((prev) => prev.filter((item) => item.id !== itemId));
  };

  const formatFileSize = (bytes?: number) => {
    if (bytes === undefined) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

  const fetchNumbers = async () => {
    try {
      const data = await PhoneNumberService.getAll();
      setPhoneNumbers(data);
    } catch (err) {
      console.error("Failed to load phone numbers:", err);
    }
  };

  const fetchTools = async () => {
    try {
      const data = await ToolsService.getAll({ status: "active" });
      setAllTools(data);
    } catch (err) {
      console.error("Failed to load tools:", err);
    }
  };

  const load = () => {
    if (!id) return;
    AgentService.getById(id).then((data) => {
      setA(data);
    }).catch(() => {});
    api.get(`/conversations?agentId=${id}&limit=20`).then((r) => setConvs(r.data)).catch(() => {});
  };

  useEffect(() => {
    load();
    fetchNumbers();
    fetchTools();
    if (isAdmin) {
      ResellerService.getAll().then(setAllResellers).catch(() => {});
      ClientService.getAll().then(setAllClients).catch(() => {});
    } else if (isReseller) {
      ClientService.getAll().then(setAllClients).catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isAdmin, isReseller]);

  useEffect(() => {
    if (a) {
      setEditName(a.name || "");
      setEditUseCase(a.useCase || "");
      setEditActivityDesc(a.activityDescription || "");
      setEditCallType(a.callType || "inbound");
      setEditVoiceGender((a.voiceGender as any) || "female");
      setEditVoiceName(a.voiceName || "aria");
      setEditGuardrails(a.guardrails || DEFAULT_GUARDRAILS);
      setEditCustomGuardrails(a.customGuardrails || "");
      setEditKnowledgeItems(a.knowledgeItems || []);
      setEditToolIds(a.toolIds || []);

      const resIds = (a.assignedResellers || []).map((r) => String(r.id));
      const cliIds = (a.assignedClients || []).map((c) => String(c.id));
      setSelectedResellerIds(resIds);
      setSelectedClientIds(cliIds);

      if (resIds.length > 0) {
        setAssignmentTarget("reseller");
      } else if (cliIds.length > 0) {
        setAssignmentTarget("client");
      } else {
        setAssignmentTarget("none");
      }
    }
  }, [a]);

  useEffect(() => {
    if (a && filteredNumbersForDropdown.length > 0) {
      const connected = filteredNumbersForDropdown.find((num) => num.agentId && String(num.agentId) === String(id));
      setSelectedPhoneNumberId(connected ? connected.id : "none");
    }
  }, [a, phoneNumbers]);

  const toggleStatus = async () => {
    if (!a || !id) return;
    const next = a.status === "active" ? "paused" : "active";
    try {
      await AgentService.updateStatus(id, next);
      toast.success(`Agent ${next}`);
      load();
    } catch { toast.error("Update failed"); }
  };

  const handleSaveAllChanges = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!id) return;
    if (!editName.trim()) return toast.error("Agent name is required.");

    const isUploading = editKnowledgeItems.some(item => item.label.includes("(Uploading...)"));
    if (isUploading) {
      return toast.error("Please wait for all files to finish uploading.");
    }

    setSavingDetails(true);
    try {
      // 1. Save details (prompt, voice, guardrails, KB, name, useCase, callType)
      await AgentService.updateDetails(id, {
        name: editName.trim(),
        useCase: editUseCase.trim(),
        activityDescription: editActivityDesc.trim(),
        callType: editCallType,
        voiceName: editVoiceName,
        voiceGender: editVoiceGender,
        guardrails: editGuardrails,
        customGuardrails: editCustomGuardrails.trim(),
        knowledgeItems: editKnowledgeItems.map((k) => ({
          id: k.id,
          type: k.type,
          label: k.label,
          value: k.value,
          size: k.size,
        })),
        toolIds: editToolIds,
      });

      // 2. Save assignments
      let finalResellerIds: string[] = [];
      let finalClientIds: string[] = [];
      if (assignmentTarget === "reseller") {
        finalResellerIds = selectedResellerIds;
      } else if (assignmentTarget === "client") {
        finalClientIds = selectedClientIds;
      }
      await AgentService.updateAssignments(id, finalResellerIds, finalClientIds);

      // 3. Save phone number routing if changed
      const connected = filteredNumbersForDropdown.find((num) => num.agentId && String(num.agentId) === String(id));
      const currentConnectedId = connected ? connected.id : "none";

      if (selectedPhoneNumberId !== currentConnectedId) {
        if (selectedPhoneNumberId && selectedPhoneNumberId !== "none") {
          await PhoneNumberService.assignAgent(selectedPhoneNumberId, id);
        }
      }

      toast.success("Agent changes saved successfully!");
      load();
      fetchNumbers();
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to save agent changes.");
    } finally {
      setSavingDetails(false);
    }
  };

  if (!a) return <div className="p-6 text-xs text-zinc-500 font-mono-stat">Loading…</div>;

  const filteredResellers = allResellers.filter((r) =>
    r.name.toLowerCase().includes(resellerSearch.toLowerCase()) ||
    (r.country && r.country.toLowerCase().includes(resellerSearch.toLowerCase()))
  );

  const filteredClients = allClients.filter((c) =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  );

  return (
    <div data-testid="agent-detail" className="space-y-6">
      <div className="flex items-center justify-between border-b border-zinc-200 pb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => nav(-1)}
            className="p-1.5 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 rounded-sm transition-colors bg-white shadow-xs"
            title="Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-zinc-950 font-display">{a.name}</h1>
              <StatusBadge value={a.status} />
            </div>
            <p className="text-xs text-zinc-500 font-medium mt-0.5">
              {a.type} • {a.channels.join(", ")} • Prompt v{a.promptVersion} • KB v{a.kbVersion}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canEdit && (
            <Button type="button" variant="outline" onClick={toggleStatus}>
              {a.status === "active" ? <><Pause className="w-3.5 h-3.5 mr-1.5"/> Pause</> : <><Play className="w-3.5 h-3.5 mr-1.5"/> Resume</>}
            </Button>
          )}
          {canEdit && (
            <Button type="button" disabled={savingDetails} onClick={() => handleSaveAllChanges()} className="min-w-[130px]">
              {savingDetails ? "Saving..." : "Save Changes"}
            </Button>
          )}
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-7 mb-6 bg-zinc-100 p-0.5 rounded-sm">
          <TabsTrigger
            value="basic"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Basic Info
          </TabsTrigger>
          <TabsTrigger
            value="prompt"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <MessageSquareText className="w-3.5 h-3.5" />
            System Prompt
          </TabsTrigger>
          <TabsTrigger
            value="knowledge"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <BookOpen className="w-3.5 h-3.5" />
            Knowledge Base
          </TabsTrigger>
          <TabsTrigger
            value="voice"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <Mic2 className="w-3.5 h-3.5" />
            Voice & Safety
          </TabsTrigger>
          <TabsTrigger
            value="assignment"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <Building2 className="w-3.5 h-3.5" />
            Agent Assignment
          </TabsTrigger>
          <TabsTrigger
            value="tools"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <Sliders className="w-3.5 h-3.5" />
            Tool Configuration
          </TabsTrigger>
          <TabsTrigger
            value="conversations"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs border border-transparent data-[state=active]:bg-white data-[state=active]:border-zinc-200 shadow-none"
          >
            <MessageSquareText className="w-3.5 h-3.5" />
            Conversations
          </TabsTrigger>
        </TabsList>

        {/* ── Basic Info Tab ────────────────────────────────────────── */}
        <TabsContent value="basic" className="outline-none space-y-6">
          {/* Static KPI Cards */}
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

          <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-5 w-full">
            <div className="space-y-1.5">
              <Label htmlFor="agent-name" className="text-xs font-medium">
                Agent Name *
              </Label>
              <Input
                id="agent-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={!canEdit}
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Call Type</Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={!canEdit}
                  onClick={() => setEditCallType("inbound")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${
                    editCallType === "inbound"
                      ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  Inbound
                </button>
                <button
                  type="button"
                  disabled={!canEdit}
                  onClick={() => setEditCallType("outbound")}
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${
                    editCallType === "outbound"
                      ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  Outbound
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="use-case" className="text-xs font-medium">
                Use Case
              </Label>
              <Input
                id="use-case"
                value={editUseCase}
                onChange={(e) => setEditUseCase(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g., Lead Qualification, Customer Support"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="agent-phone-number" className="text-xs font-medium">
                Phone Number Attachment (Optional)
              </Label>
              <select
                id="agent-phone-number"
                value={selectedPhoneNumberId}
                onChange={(e) => setSelectedPhoneNumberId(e.target.value)}
                disabled={!canEdit}
                className="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-950"
              >
                <option value="none">-- None (Do not attach / Detach current number) --</option>
                {filteredNumbersForDropdown.map((num) => (
                  <option key={num.id} value={num.id}>
                    {num.number} {num.name ? `(${num.name})` : ""} {num.agentId && String(num.agentId) !== String(id) ? " - Assigned to other agent" : ""}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-zinc-500">Attach one of your registered phone numbers to route to this agent</p>
            </div>
          </div>
        </TabsContent>

        {/* ── System Prompt Tab ──────────────────────────────────────── */}
        <TabsContent value="prompt" className="outline-none">
          <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4 w-full">
            <div className="flex items-center justify-between">
              <Label htmlFor="system-prompt" className="text-xs font-medium">
                System Prompt
              </Label>
              <span className="text-[10px] text-zinc-400 font-mono-stat">{editActivityDesc.length} chars</span>
            </div>
            <Textarea
              id="system-prompt"
              rows={12}
              value={editActivityDesc}
              onChange={(e) => setEditActivityDesc(e.target.value)}
              disabled={!canEdit}
              placeholder="You are a helpful, professional voice agent..."
              className="text-xs font-mono bg-white"
            />
            {canEdit && (
              <div className="pt-2 border-t border-zinc-100 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Quick Templates</span>
                <div className="flex flex-wrap gap-2">
                  {PROMPT_TEMPLATES.map((tpl) => (
                    <button
                      key={tpl.label}
                      type="button"
                      onClick={() => setEditActivityDesc(tpl.text)}
                      className="px-2.5 py-1 text-[11px] border border-zinc-200 rounded-sm bg-zinc-50 text-zinc-700 hover:bg-zinc-100 transition-colors font-medium"
                    >
                      {tpl.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ── Knowledge Base Tab ─────────────────────────────────────── */}
        <TabsContent value="knowledge" className="outline-none">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 w-full">
            <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5 text-zinc-500" /> Upload Files
              </h3>
              <div
                onClick={() => { if (canEdit) fileInputRef.current?.click(); }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (canEdit) setIsDraggingFile(true);
                }}
                onDragLeave={() => setIsDraggingFile(false)}
                onDrop={handleFileDrop}
                className={`flex flex-col items-center justify-center gap-1.5 py-6 px-4 border-2 border-dashed rounded-sm cursor-pointer transition-colors text-center ${
                  isDraggingFile
                    ? "border-zinc-950 bg-zinc-50"
                    : "border-zinc-200 bg-zinc-50/50 hover:bg-zinc-50 hover:border-zinc-300"
                } ${!canEdit ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                <Upload className="w-5 h-5 text-zinc-400" />
                <p className="text-xs font-medium text-zinc-700">
                  <span className="underline">Click to upload</span> or drag & drop
                </p>
                <p className="text-[10px] text-zinc-400">PDF, DOC, TXT, MD, CSV, JSON (max 10MB each)</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept={ACCEPTED_KB_FILE_TYPES}
                  disabled={!canEdit}
                  className="hidden"
                  onChange={handleFileInputChange}
                />
              </div>

              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5 pt-2 border-t border-zinc-100">
                <Link2 className="w-3.5 h-3.5 text-zinc-500" /> Add from URL
              </h3>
              <div className="flex gap-2">
                <Input
                  placeholder="https://example.com/faq"
                  value={kbUrlInput}
                  onChange={(e) => setKbUrlInput(e.target.value)}
                  disabled={!canEdit}
                  className="text-xs h-9 bg-white"
                />
                <Button type="button" variant="outline" onClick={addKnowledgeUrl} disabled={!canEdit} className="shrink-0 h-9">
                  <Plus className="w-3.5 h-3.5" />
                </Button>
              </div>

              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5 pt-2 border-t border-zinc-100">
                <FileText className="w-3.5 h-3.5 text-zinc-500" /> Add Text Snippet
              </h3>
              <Textarea
                rows={4}
                placeholder="Paste reference text, policies, or product info..."
                value={kbTextInput}
                onChange={(e) => setKbTextInput(e.target.value)}
                disabled={!canEdit}
                className="text-xs bg-white"
              />
              <Button type="button" variant="outline" onClick={addKnowledgeText} disabled={!canEdit} className="w-full">
                <Plus className="w-3.5 h-3.5 mr-1.5" /> Add Snippet
              </Button>
            </div>

            <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900">
                Knowledge Sources ({editKnowledgeItems.length})
              </h3>
              {editKnowledgeItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center text-zinc-400">
                  <BookOpen className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-xs">No knowledge sources added yet</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {editKnowledgeItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-2 p-2.5 bg-zinc-50 border border-zinc-150 rounded-sm"
                    >
                      <div className="flex items-center gap-2 overflow-hidden">
                        {item.type === "url" ? (
                          <Link2 className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                        ) : item.type === "file" ? (
                          <FileIcon className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        )}
                        <span className="text-xs text-zinc-700 truncate">{item.label}</span>
                        {item.type === "file" && item.size !== undefined && (
                          <span className="text-[10px] text-zinc-400 shrink-0">({formatFileSize(item.size)})</span>
                        )}
                      </div>
                      {canEdit && (
                        <button
                          type="button"
                          onClick={() => removeKnowledgeItem(item.id)}
                          className="text-zinc-400 hover:text-rose-600 transition-colors shrink-0"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ── Voice & Safety Tab ─────────────────────────────────────── */}
        <TabsContent value="voice" className="outline-none space-y-6">
          <ElevenLabsVoiceSelector
            selectedVoiceName={editVoiceName}
            selectedVoiceGender={editVoiceGender as "female" | "male"}
            onSelectVoice={(vName, g) => {
              setEditVoiceName(vName);
              setEditVoiceGender(g);
            }}
            disabled={!canEdit}
          />

          <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-4">
            <div className="flex items-center gap-2 text-zinc-900 font-bold text-xs uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Safety Guardrails & Compliance</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { key: "blockProfanity" as const, label: "Block profanity & abusive language" },
                { key: "piiRedaction" as const, label: "Redact PII in transcripts" },
                { key: "restrictOffTopic" as const, label: "Restrict off-topic conversations" },
                { key: "requireDisclaimer" as const, label: "Require AI disclaimer at call start" },
                { key: "escalateOnFrustration" as const, label: "Escalate to human on frustration" },
              ].map((g) => (
                <div key={g.key} className="flex items-center justify-between gap-3 p-3 bg-zinc-50 border border-zinc-150 rounded-sm">
                  <span className="text-xs text-zinc-700 font-medium">{g.label}</span>
                  <Switch
                    checked={!!editGuardrails?.[g.key]}
                    disabled={!canEdit}
                    onCheckedChange={(checked) =>
                      setEditGuardrails((prev: any) => ({ ...prev, [g.key]: checked }))
                    }
                  />
                </div>
              ))}
            </div>

            <div className="space-y-1.5 pt-2 border-t border-zinc-100">
              <Label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                Custom Guardrail Rules
              </Label>
              <Textarea
                rows={3}
                placeholder="e.g., Never discuss pricing..."
                value={editCustomGuardrails}
                onChange={(e) => setEditCustomGuardrails(e.target.value)}
                disabled={!canEdit}
                className="text-xs bg-white"
              />
            </div>
          </div>
        </TabsContent>

        {/* ── Agent Assignment Tab ────────────────────────────────────── */}
        <TabsContent value="assignment" className="outline-none">
          <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4 w-full">
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
                disabled={!canEdit || isClient}
                className="flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-1 text-sm shadow-xs focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-zinc-950 animate-none"
              >
                <option value="none">Unassigned (Admin Pool / Global)</option>
                {isAdmin && <option value="reseller">Resellers</option>}
                <option value="client">Clients</option>
              </select>
            </div>

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
                    disabled={!canEdit || isClient}
                    className="pl-8 h-8 text-xs bg-white"
                  />
                </div>

                <div className="max-h-60 overflow-y-auto border border-zinc-200 rounded-md p-2 space-y-1 bg-zinc-50">
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
                          } ${(!canEdit || isClient) ? "pointer-events-none opacity-80" : ""}`}
                        >
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={!canEdit || isClient}
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
                    disabled={!canEdit || isClient}
                    className="pl-8 h-8 text-xs bg-white"
                  />
                </div>

                <div className="max-h-60 overflow-y-auto border border-zinc-200 rounded-md p-2 space-y-1 bg-zinc-50">
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
                          } ${(!canEdit || isClient) ? "pointer-events-none opacity-80" : ""}`}
                        >
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              disabled={!canEdit || isClient}
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
          </div>
        </TabsContent>

        {/* ── Tools Tab ──────────────────────────────────────────────── */}
        <TabsContent value="tools" className="outline-none">
          <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4 w-full">
            <div>
              <h3 className="text-sm font-semibold text-zinc-900 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-zinc-700" /> Enable Agent Tools
              </h3>
              <p className="text-xs text-zinc-500 mt-0.5">Select the tools this agent is allowed to execute during conversations.</p>
            </div>

            {allTools.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center text-zinc-400 border border-dashed border-zinc-200 rounded-sm bg-zinc-50/50">
                <Sliders className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-xs font-semibold">No active tools found</p>
                <p className="text-[11px] text-zinc-500 mt-1">Create tools first under the "Tools" navigation menu.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {allTools.map((tool) => {
                  const isChecked = editToolIds.includes(tool.toolUuid);
                  return (
                    <div
                      key={tool.toolUuid}
                      onClick={() => {
                        if (!canEdit) return;
                        setEditToolIds((prev) =>
                          prev.includes(tool.toolUuid)
                            ? prev.filter((id) => id !== tool.toolUuid)
                            : [...prev, tool.toolUuid]
                        );
                      }}
                      className={`flex items-start gap-3 p-4 border rounded-sm transition-all ${
                        isChecked
                          ? "border-zinc-950 bg-zinc-50/80 shadow-xs"
                          : "border-zinc-200 hover:border-zinc-300 bg-white"
                      } ${!canEdit ? "pointer-events-none opacity-80" : "cursor-pointer"}`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={!canEdit}
                        readOnly
                        className="mt-1 rounded border-zinc-300 text-zinc-950 focus:ring-zinc-950"
                      />
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-zinc-900 flex items-center gap-1.5">
                          <span className="capitalize px-1.5 py-0.5 rounded-sm bg-zinc-100 text-zinc-700 text-[10px]">
                            {tool.category.replace("_", " ")}
                          </span>
                          <span>{tool.name}</span>
                        </div>
                        {tool.description && (
                          <p className="text-[11px] text-zinc-500 leading-normal line-clamp-2">
                            {tool.description}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </TabsContent>

        {/* ── Recent Conversations Tab ───────────────────────────────── */}
        <TabsContent value="conversations" className="outline-none">
          <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
            <div className="px-5 py-3 border-b border-zinc-200">
              <div className="label-tiny">RECENT CONVERSATIONS</div>
            </div>
            {convs.length === 0 ? (
              <div className="p-8 text-center text-zinc-400 text-xs">
                No recent conversations found for this agent
              </div>
            ) : (
              <div className="divide-y divide-zinc-100">
                {convs.map((c) => (
                  <div
                    key={c.id}
                    className="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-zinc-50"
                    onClick={() => nav(`/conversations/${c.id}`)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{c.customerName}</div>
                      <div className="text-xs text-zinc-500 truncate">{c.summary}</div>
                    </div>
                    <span className="text-xs font-mono-stat text-zinc-500">{c.channel}</span>
                    <StatusBadge value={c.outcome} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
