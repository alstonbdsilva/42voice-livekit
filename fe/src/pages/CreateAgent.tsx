import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  PhoneIncoming,
  PhoneOutgoing,
  MessageSquareText,
  BookOpen,
  Mic2,
  ShieldCheck,
  Link2,
  FileText,
  Plus,
  Trash2,
  Sparkles,
  Play,
  Upload,
  File as FileIcon,
  Sliders,
} from "lucide-react";
import AgentService, { CreateAgentDto } from "@/services/agent.service";
import PhoneNumberService from "@/services/phone-number.service";
import ToolsService from "@/services/tools.service";
import { Tool } from "@/types";
import { useAuth } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface KnowledgeItem {
  id: string;
  type: "url" | "text" | "file";
  label: string;
  value: string;
  size?: number;
}

const ACCEPTED_KB_FILE_TYPES = ".pdf,.doc,.docx,.txt,.md,.csv,.json";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const VOICE_OPTIONS = [
  { value: "aria", label: "Aria", gender: "female" },
  { value: "luna", label: "Luna", gender: "female" },
  { value: "nova", label: "Nova", gender: "female" },
  { value: "atlas", label: "Atlas", gender: "male" },
  { value: "orion", label: "Orion", gender: "male" },
  { value: "sage", label: "Sage", gender: "male" },
];

const PROMPT_TEMPLATES = [
  { label: "Customer Support", text: "You are a friendly and professional customer support voice agent. Greet the caller, understand their issue, and provide clear, concise solutions. If you cannot resolve the issue, offer to escalate to a human agent." },
  { label: "Lead Qualification", text: "You are a lead qualification voice agent. Politely ask about the caller's needs, budget, and timeline. Determine if they are a good fit and schedule a follow-up if appropriate." },
  { label: "Appointment Booking", text: "You are a scheduling assistant. Help the caller find an available slot, confirm their details, and book the appointment. Always confirm the date and time back to the caller." },
];

const DEFAULT_GUARDRAILS = {
  blockProfanity: true,
  piiRedaction: true,
  restrictOffTopic: true,
  requireDisclaimer: false,
  escalateOnFrustration: true,
};

export default function CreateAgent() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("basic");

  // Basic info
  const [name, setName] = useState("");
  const [callType, setCallType] = useState("inbound");
  const [useCase, setUseCase] = useState("");

  // System prompt
  const [systemPrompt, setSystemPrompt] = useState("");

  // Knowledge base
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [kbUrlInput, setKbUrlInput] = useState("");
  const [kbTextInput, setKbTextInput] = useState("");
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Voice
  const [voiceGender, setVoiceGender] = useState<"female" | "male">("female");
  const [voiceName, setVoiceName] = useState("aria");

  // Guardrails
  const [guardrails, setGuardrails] = useState(DEFAULT_GUARDRAILS);
  const [customGuardrails, setCustomGuardrails] = useState("");

  // Phone numbers available
  const [phoneNumbers, setPhoneNumbers] = useState<any[]>([]);
  const [selectedPhoneNumberId, setSelectedPhoneNumberId] = useState<string>("none");

  // Tools available
  const [tools, setTools] = useState<Tool[]>([]);
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([]);

  useEffect(() => {
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
        setTools(data);
      } catch (err) {
        console.error("Failed to load tools:", err);
      }
    };
    fetchNumbers();
    fetchTools();
  }, []);

  const isSuperAdmin = user?.role === "super_admin" || user?.role === "finance_admin";
  const userOwnerId = user?.clientId || user?.resellerId || user?.id;

  const filteredNumbersForDropdown = phoneNumbers.filter((num) => {
    if (isSuperAdmin) return true;
    const numOwnerId = num.clientId || num.resellerId;
    return numOwnerId && String(numOwnerId) === String(userOwnerId);
  });

  const toggleGuardrail = (key: keyof typeof DEFAULT_GUARDRAILS) => {
    setGuardrails((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const addKnowledgeUrl = () => {
    if (!kbUrlInput.trim()) return;
    setKnowledgeItems((prev) => [
      ...prev,
      { id: crypto.randomUUID(), type: "url", label: kbUrlInput.trim(), value: kbUrlInput.trim() },
    ]);
    setKbUrlInput("");
  };

  const addKnowledgeText = () => {
    if (!kbTextInput.trim()) return;
    setKnowledgeItems((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        type: "text",
        label: kbTextInput.trim().slice(0, 40) + (kbTextInput.trim().length > 40 ? "…" : ""),
        value: kbTextInput.trim(),
      },
    ]);
    setKbTextInput("");
  };

  const removeKnowledgeItem = (id: string) => {
    setKnowledgeItems((prev) => prev.filter((k) => k.id !== id));
  };

  const addKnowledgeFiles = async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const fileId = crypto.randomUUID();
      // Add a placeholder item with type "file"
      const placeholderItem: KnowledgeItem = {
        id: fileId,
        type: "file",
        label: `${file.name} (Uploading...)`,
        value: file.name,
        size: file.size,
      };
      
      setKnowledgeItems((prev) => [...prev, placeholderItem]);
      
      try {
        const response = await AgentService.uploadFile(file);
        // Update placeholder with returned S3 URL
        setKnowledgeItems((prev) =>
          prev.map((item) =>
            item.id === fileId
              ? {
                  ...item,
                  label: file.name,
                  value: response.s3Url,
                }
              : item
          )
        );
        toast.success(`Uploaded ${file.name} successfully!`);
      } catch (err: any) {
        toast.error(`Failed to upload ${file.name}`);
        // Remove item on failure
        setKnowledgeItems((prev) => prev.filter((item) => item.id !== fileId));
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addKnowledgeFiles(e.target.files);
    e.target.value = "";
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingFile(false);
    if (e.dataTransfer.files) addKnowledgeFiles(e.dataTransfer.files);
  };

  const filteredVoices = VOICE_OPTIONS.filter((v) => v.gender === voiceGender);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setActiveTab("basic");
      return toast.error("Agent name is required.");
    }

    const isUploading = knowledgeItems.some(item => item.label.includes("(Uploading...)"));
    if (isUploading) {
      return toast.error("Please wait for all files to finish uploading.");
    }

    setLoading(true);
    try {
      const dto: CreateAgentDto = {
        name: name.trim(),
        callType,
        useCase: useCase.trim(),
        activityDescription: systemPrompt.trim(),
        voiceName,
        voiceGender,
        guardrails,
        customGuardrails: customGuardrails.trim(),
        knowledgeItems: knowledgeItems.map((k) => ({
          id: k.id,
          type: k.type,
          label: k.label,
          value: k.value,
          size: k.size,
        })),
        toolIds: selectedToolIds,
      };

      const newAgent = await AgentService.create(dto);
      toast.success("Voice Agent created successfully!");

      if (selectedPhoneNumberId && selectedPhoneNumberId !== "none" && selectedPhoneNumberId !== "") {
        try {
          await PhoneNumberService.assignAgent(selectedPhoneNumberId, String(newAgent.id));
          toast.success("Phone number linked to agent successfully!");
        } catch (err: any) {
          toast.error("Agent created, but failed to link the phone number.");
          console.error("Failed to link phone number:", err);
        }
      }

      navigate("/agents");
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Failed to create voice agent.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 w-full" data-testid="create-agent-page">
      <div className="flex items-center justify-between border-b border-zinc-200 pb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/agents")}
            className="p-1.5 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 rounded-sm transition-colors bg-white shadow-xs"
            title="Back to Agents"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-zinc-950 font-display">Create Voice Agent</h1>
            <p className="text-xs text-zinc-500 font-medium">
              Configure identity, behavior, knowledge, voice and safety for your new agent
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/agents")}>
            Cancel
          </Button>
          <Button type="button" disabled={loading} onClick={handleSubmit} className="min-w-[130px]">
            {loading ? "Creating..." : "Create Agent"}
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-5 mb-6">
            <TabsTrigger
              value="basic"
              className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
            >
              <Sparkles className="w-4 h-4" />
              Basic Info
            </TabsTrigger>
            <TabsTrigger
              value="prompt"
              className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
            >
              <MessageSquareText className="w-4 h-4" />
              System Prompt
            </TabsTrigger>
            <TabsTrigger
              value="knowledge"
              className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
            >
              <BookOpen className="w-4 h-4" />
              Knowledge Base
            </TabsTrigger>
            <TabsTrigger
              value="voice"
              className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
            >
              <Mic2 className="w-4 h-4" />
              Voice
            </TabsTrigger>
            <TabsTrigger
              value="tools"
              className="flex items-center justify-center gap-2 border border-transparent data-[state=active]:border-zinc-200 shadow-none data-[state=active]:shadow-none"
            >
              <Sliders className="w-4 h-4" />
              Tools
            </TabsTrigger>
          </TabsList>

          {/* ── Basic Info ─────────────────────────────────────────────── */}
          <TabsContent value="basic" className="outline-none">
            <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-5 w-full">
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

              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Call Type</Label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setCallType("inbound")}
                    className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${
                      callType === "inbound"
                        ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                        : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                    }`}
                  >
                    <PhoneIncoming className="w-3.5 h-3.5" /> Inbound
                  </button>
                  <button
                    type="button"
                    onClick={() => setCallType("outbound")}
                    className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${
                      callType === "outbound"
                        ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                        : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                    }`}
                  >
                    <PhoneOutgoing className="w-3.5 h-3.5" /> Outbound
                  </button>
                </div>
                <p className="text-[11px] text-zinc-500">Choose whether users will call your AI or your AI will call users</p>
              </div>

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

              <div className="space-y-1.5">
                <Label className="text-xs font-medium">Phone Number Attachment (Optional)</Label>
                <Select value={selectedPhoneNumberId} onValueChange={setSelectedPhoneNumberId}>
                  <SelectTrigger className="text-xs h-9">
                    <SelectValue placeholder="Select a phone number" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none" className="text-xs">
                      -- None (Do not attach a number) --
                    </SelectItem>
                    {filteredNumbersForDropdown.map((num) => (
                      <SelectItem key={num.id} value={num.id} className="text-xs">
                        {num.number} {num.name ? `(${num.name})` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-zinc-500">Attach an available phone number to this agent</p>
              </div>
            </div>
          </TabsContent>

          {/* ── System Prompt ──────────────────────────────────────────── */}
          <TabsContent value="prompt" className="outline-none">
            <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4 w-full">
              <div className="flex items-center justify-between">
                <Label htmlFor="system-prompt" className="text-xs font-medium">
                  System Prompt
                </Label>
                <span className="text-[10px] text-zinc-400 font-mono-stat">{systemPrompt.length} chars</span>
              </div>
              <Textarea
                id="system-prompt"
                rows={10}
                placeholder="You are a helpful, professional voice agent. Describe the agent's persona, tone, goals, and how it should handle the conversation..."
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="text-xs font-mono"
              />
              <p className="text-[11px] text-zinc-500">
                This instructs the model on persona, tone, and behavior. Be specific about goals, constraints and escalation paths.
              </p>

              <div className="pt-2 border-t border-zinc-100 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Quick Templates</span>
                <div className="flex flex-wrap gap-2">
                  {PROMPT_TEMPLATES.map((tpl) => (
                    <button
                      key={tpl.label}
                      type="button"
                      onClick={() => setSystemPrompt(tpl.text)}
                      className="px-2.5 py-1 text-[11px] border border-zinc-200 rounded-sm bg-zinc-50 text-zinc-700 hover:bg-zinc-100 transition-colors font-medium"
                    >
                      {tpl.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          {/* ── Knowledge Base ──────────────────────────────────────────── */}
          <TabsContent value="knowledge" className="outline-none">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 w-full">
              <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5">
                  <Upload className="w-3.5 h-3.5 text-zinc-500" /> Upload Files
                </h3>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDraggingFile(true);
                  }}
                  onDragLeave={() => setIsDraggingFile(false)}
                  onDrop={handleFileDrop}
                  className={`flex flex-col items-center justify-center gap-1.5 py-6 px-4 border-2 border-dashed rounded-sm cursor-pointer transition-colors text-center ${
                    isDraggingFile
                      ? "border-zinc-950 bg-zinc-50"
                      : "border-zinc-200 bg-zinc-50/50 hover:bg-zinc-50 hover:border-zinc-300"
                  }`}
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
                    className="text-xs"
                  />
                  <Button type="button" variant="outline" onClick={addKnowledgeUrl} className="shrink-0">
                    <Plus className="w-3.5 h-3.5" />
                  </Button>
                </div>
                <p className="text-[11px] text-zinc-500">Add website links, docs, or FAQ pages for the agent to reference.</p>

                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5 pt-2 border-t border-zinc-100">
                  <FileText className="w-3.5 h-3.5 text-zinc-500" /> Add Text Snippet
                </h3>
                <Textarea
                  rows={4}
                  placeholder="Paste reference text, policies, or product info..."
                  value={kbTextInput}
                  onChange={(e) => setKbTextInput(e.target.value)}
                  className="text-xs"
                />
                <Button type="button" variant="outline" onClick={addKnowledgeText} className="w-full">
                  <Plus className="w-3.5 h-3.5 mr-1.5" /> Add Snippet
                </Button>
              </div>

              <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900">
                  Knowledge Sources ({knowledgeItems.length})
                </h3>
                {knowledgeItems.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 text-center text-zinc-400">
                    <BookOpen className="w-8 h-8 mb-2 opacity-50" />
                    <p className="text-xs">No knowledge sources added yet</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {knowledgeItems.map((item) => (
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
                        <button
                          type="button"
                          onClick={() => removeKnowledgeItem(item.id)}
                          className="text-zinc-400 hover:text-rose-600 transition-colors shrink-0"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          {/* ── Voice ───────────────────────────────────────────────────── */}
          <TabsContent value="voice" className="outline-none">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 w-full">
              <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900">Voice Selection</h3>

                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Voice Gender</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setVoiceGender("female");
                        setVoiceName(VOICE_OPTIONS.find((v) => v.gender === "female")!.value);
                      }}
                      className={`py-2 px-3 text-xs border rounded-sm transition-all font-medium ${
                        voiceGender === "female"
                          ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                          : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                      }`}
                    >
                      Female
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setVoiceGender("male");
                        setVoiceName(VOICE_OPTIONS.find((v) => v.gender === "male")!.value);
                      }}
                      className={`py-2 px-3 text-xs border rounded-sm transition-all font-medium ${
                        voiceGender === "male"
                          ? "bg-zinc-950 border-zinc-950 text-white font-semibold"
                          : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                      }`}
                    >
                      Male
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-medium">Voice Name</Label>
                  <Select value={voiceName} onValueChange={setVoiceName}>
                    <SelectTrigger className="text-xs h-9">
                      <SelectValue placeholder="Select a voice" />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredVoices.map((v) => (
                        <SelectItem key={v.value} value={v.value} className="text-xs">
                          {v.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button type="button" variant="outline" className="w-full">
                  <Play className="w-3.5 h-3.5 mr-1.5" /> Preview Voice Sample
                </Button>
                <p className="text-[11px] text-zinc-500">Voice preview playback will be available once connected to the voice engine.</p>
              </div>

              <div className="bg-zinc-50 border border-zinc-200 p-5 rounded-sm space-y-3 shadow-xs">
                <div className="flex items-center gap-2 text-zinc-700 font-semibold text-xs">
                  <Mic2 className="w-4 h-4 text-zinc-500" />
                  <span>Selected Voice</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-white border border-zinc-200 rounded-sm">
                  <div className="w-10 h-10 rounded-full bg-zinc-900 text-white flex items-center justify-center font-bold text-sm">
                    {VOICE_OPTIONS.find((v) => v.value === voiceName)?.label.charAt(0)}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-zinc-900">
                      {VOICE_OPTIONS.find((v) => v.value === voiceName)?.label}
                    </div>
                    <div className="text-[11px] text-zinc-500 capitalize">{voiceGender} voice</div>
                  </div>
                </div>

                <div className="pt-3 border-t border-zinc-200 space-y-3">
                  <div className="flex items-center gap-2 text-zinc-700 font-semibold text-xs">
                    <ShieldCheck className="w-4 h-4 text-zinc-500" />
                    <span>Guardrails</span>
                  </div>

                  {[
                    { key: "blockProfanity" as const, label: "Block profanity & abusive language" },
                    { key: "piiRedaction" as const, label: "Redact PII in transcripts" },
                    { key: "restrictOffTopic" as const, label: "Restrict off-topic conversations" },
                    { key: "requireDisclaimer" as const, label: "Require AI disclaimer at call start" },
                    { key: "escalateOnFrustration" as const, label: "Escalate to human on frustration" },
                  ].map((g) => (
                    <div key={g.key} className="flex items-center justify-between gap-2">
                      <span className="text-[11px] text-zinc-700">{g.label}</span>
                      <Switch checked={guardrails[g.key]} onCheckedChange={() => toggleGuardrail(g.key)} />
                    </div>
                  ))}

                  <div className="space-y-1.5 pt-1">
                    <Label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                      Custom Guardrail Rules
                    </Label>
                    <Textarea
                      rows={3}
                      placeholder="e.g., Never discuss pricing for competitor products. Always confirm identity before sharing account details."
                      value={customGuardrails}
                      onChange={(e) => setCustomGuardrails(e.target.value)}
                      className="text-xs bg-white"
                    />
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* ── Tools ───────────────────────────────────────────────────── */}
          <TabsContent value="tools" className="outline-none">
            <div className="bg-white border border-zinc-200 p-6 rounded-sm shadow-xs space-y-4 w-full">
              <div>
                <h3 className="text-sm font-semibold text-zinc-900 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-zinc-700" /> Enable Agent Tools
                </h3>
                <p className="text-xs text-zinc-500 mt-0.5">Select the tools this agent is allowed to execute during conversations.</p>
              </div>

              {tools.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center text-zinc-400 border border-dashed border-zinc-200 rounded-sm bg-zinc-50/50">
                  <Sliders className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-xs font-semibold">No active tools found</p>
                  <p className="text-[11px] text-zinc-500 mt-1">Create tools first under the "Tools" navigation menu.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {tools.map((tool) => {
                    const isChecked = selectedToolIds.includes(tool.toolUuid);
                    return (
                      <div
                        key={tool.toolUuid}
                        onClick={() => {
                          setSelectedToolIds((prev) =>
                            prev.includes(tool.toolUuid)
                              ? prev.filter((id) => id !== tool.toolUuid)
                              : [...prev, tool.toolUuid]
                          );
                        }}
                        className={`flex items-start gap-3 p-4 border rounded-sm cursor-pointer transition-all ${
                          isChecked
                            ? "border-zinc-950 bg-zinc-50/80 shadow-xs"
                            : "border-zinc-200 hover:border-zinc-300 bg-white"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
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
        </Tabs>
      </form>
    </div>
  );
}
