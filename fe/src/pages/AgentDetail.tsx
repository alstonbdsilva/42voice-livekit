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
  ShieldCheck,
  Phone,
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  RefreshCw,
  Download,
  Loader2,
  Bot,
  Send,
  Radio
} from "lucide-react";

import {
  Room,
  RoomEvent,
  Track,
  LocalAudioTrack,
  RemoteParticipant,
  createLocalAudioTrack
} from "livekit-client";


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

  // Dograh-Style Tester State
  const [testerMode, setTesterMode] = useState<"audio" | "text">("audio");
  
  // Real LiveKit WebRTC Audio State (Dograh EmbeddedVoiceTester style)
  const [lkRoom, setLkRoom] = useState<Room | null>(null);
  const [isCallActive, setIsCallActive] = useState(false);
  const [isConnectingCall, setIsConnectingCall] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);
  const [livekitStatus, setLivekitStatus] = useState<"idle" | "connecting" | "active" | "failed" | "ended">("idle");
  const [livekitStatusText, setLivekitStatusText] = useState<string>("Disconnected");
  const audioContainerRef = React.useRef<HTMLDivElement>(null);
  const localTrackRef = React.useRef<LocalAudioTrack | null>(null);

  // Text Mode Chat State (Dograh ManualTextChatPanel style)
  const [testSessionId, setTestSessionId] = useState<string>(`test-${Date.now()}`);
  const [testInput, setTestInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [testMessages, setTestMessages] = useState<Array<{ id: string; speaker: "user" | "agent"; text: string; timestamp: string }>>([]);
  const chatBottomRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeTab === "test") {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [testMessages, isThinking, activeTab]);


  const addOrUpdateTranscriptMessage = (speaker: "user" | "agent", text: string) => {
    const cleanText = text.trim();
    if (!cleanText) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    setTestMessages((prev) => {
      if (prev.length === 0) {
        return [
          {
            id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
            speaker,
            text: cleanText,
            timestamp: timeStr,
          },
        ];
      }

      const lastMsg = prev[prev.length - 1];

      // If the last message is from the SAME speaker, update it in-place!
      if (lastMsg.speaker === speaker) {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...lastMsg,
          text: cleanText,
          timestamp: timeStr,
        };
        return updated;
      }

      // Otherwise, it's a new speaker turn -> append
      return [
        ...prev,
        {
          id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          speaker,
          text: cleanText,
          timestamp: timeStr,
        },
      ];
    });
  };

  const startLivekitVoiceCall = async () => {
    if (!id || !a) return;
    setTestMessages([]);

    setIsConnectingCall(true);
    setLivekitStatus("connecting");
    setLivekitStatusText("Requesting connection token...");

    try {
      const roomName = `test-room-${id.substring(0, 8)}`;
      const tokenRes = await api.post("/livekit/token", {
        roomName,
        agentId: id,
        agentName: a.name,
        identity: `web-user-${Date.now().toString(36)}`,
        name: "Web Tester",
      });

      const token = tokenRes?.token || tokenRes?.data?.token;
      const url = tokenRes?.url || tokenRes?.data?.url || "ws://localhost:7880";

      if (!token) throw new Error("Failed to receive token from backend");

      setLivekitStatusText("Connecting to WebRTC server...");

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      room.on(RoomEvent.Connected, () => {
        setLivekitStatus("active");
        setLivekitStatusText("Call Active 🟢");
        setIsCallActive(true);
        setIsConnectingCall(false);
        toast.success("LiveKit WebRTC Call Connected!");
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        setLivekitStatus("ended");
        setLivekitStatusText(`Call Ended (${reason || "User hung up"})`);
        setIsCallActive(false);
        setIsConnectingCall(false);
        setLkRoom(null);
        toast.info("Call disconnected");
      });

      room.on(RoomEvent.TrackSubscribed, (track: Track, publication, participant: RemoteParticipant) => {
        if (track.kind === Track.Kind.Audio) {
          setLivekitStatusText(`Agent Speaking (${participant.name || participant.identity || a.name})`);
          const audioElement = track.attach();
          audioElement.id = `lk-audio-${participant.sid}`;
          if (audioContainerRef.current) {
            audioContainerRef.current.appendChild(audioElement);
          }
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track: Track) => {
        track.detach().forEach((el) => el.remove());
      });

      room.on(RoomEvent.DataReceived, (payload: Uint8Array, participant, _kind, topic) => {
        try {
          const str = new TextDecoder().decode(payload);
          const data = JSON.parse(str);
          if ((data.type === "transcription" || data.text) && data.text?.trim()) {
            const speaker = data.speaker === "user" || data.speaker === "customer" ? "user" as const : "agent" as const;
            addOrUpdateTranscriptMessage(speaker, data.text);
          }
        } catch (err) {
          // ignore non-json data
        }
      });

      room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        segments.forEach((seg) => {
          if (seg.text && seg.text.trim()) {
            const isUser = participant ? participant.identity === room.localParticipant.identity : false;
            const speaker = isUser ? "user" as const : "agent" as const;
            addOrUpdateTranscriptMessage(speaker, seg.text);
          }
        });
      });



      await room.connect(url, token);

      try {
        const localAudioTrack = await createLocalAudioTrack();
        await room.localParticipant.publishTrack(localAudioTrack);
        localTrackRef.current = localAudioTrack;
      } catch (micErr) {
        console.warn("Microphone capture issue:", micErr);
        toast.warning("Call connected, but microphone access was denied.");
      }

      setLkRoom(room);
    } catch (err: any) {
      console.error("LiveKit Call Failed:", err);
      setLivekitStatus("failed");
      setLivekitStatusText("Connection Failed");
      setIsConnectingCall(false);
      setIsCallActive(false);
      toast.error("LiveKit connection error: " + (err?.message || "Check LiveKit server"));
    }
  };

  const endLivekitVoiceCall = async () => {
    if (localTrackRef.current) {
      localTrackRef.current.stop();
      localTrackRef.current = null;
    }
    if (lkRoom) {
      await lkRoom.disconnect();
      setLkRoom(null);
    }
    setIsCallActive(false);
    setIsConnectingCall(false);
    setLivekitStatus("ended");
    setLivekitStatusText("Disconnected");
  };

  const toggleMuteMic = () => {
    if (localTrackRef.current) {
      if (isMicMuted) {
        localTrackRef.current.unmute();
        setIsMicMuted(false);
        toast.info("Microphone unmuted");
      } else {
        localTrackRef.current.mute();
        setIsMicMuted(true);
        toast.info("Microphone muted");
      }
    }
  };

  const handleSendTestMessage = async (msgOverride?: string) => {
    const msgToSend = (msgOverride || testInput).trim();
    if (!msgToSend || !id) return;

    const userMsgObj = {
      id: `msg-${Date.now()}-user`,
      speaker: "user" as const,
      text: msgToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setTestMessages((prev) => [...prev, userMsgObj]);
    setTestInput("");
    setIsThinking(true);

    try {
      const historyForApi = testMessages.map((m) => ({ speaker: m.speaker, text: m.text }));
      const result = await AgentService.testChat(id, msgToSend, testSessionId, historyForApi);

      if (result.sessionId) setTestSessionId(result.sessionId);

      const agentMsgObj = {
        id: `msg-${Date.now()}-agent`,
        speaker: "agent" as const,
        text: result.response || "No response received.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setTestMessages((prev) => [...prev, agentMsgObj]);
    } catch (err: any) {
      toast.error("Error communicating with agent: " + (err?.message || "Unknown error"));
    } finally {
      setIsThinking(false);
    }
  };

  const handleClearTestChat = () => {
    const newSessionId = `test-${Date.now()}`;
    setTestSessionId(newSessionId);
    setTestMessages([
      {
        id: `init-${Date.now()}`,
        speaker: "agent",
        text: `Hello! Chat reset. How can I assist you today?`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    toast.info("Test chat session reset");
  };

  const handleDownloadTranscript = () => {
    const fullText = testMessages
      .map((m) => `[${m.timestamp}] ${m.speaker.toUpperCase()}: ${m.text}`)
      .join("\n");
    const blob = new Blob([fullText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const linkAnchor = document.createElement("a");
    linkAnchor.href = url;
    linkAnchor.download = `transcript-${a?.name || "agent"}-${testSessionId}.txt`;
    linkAnchor.click();
    URL.revokeObjectURL(url);
  };


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
    }).catch(() => { });
    api.get(`/conversations?agentId=${id}&limit=20`).then((r) => setConvs(r.data)).catch(() => { });
  };

  useEffect(() => {
    load();
    fetchNumbers();
    fetchTools();
    if (isAdmin) {
      ResellerService.getAll().then(setAllResellers).catch(() => { });
      ClientService.getAll().then(setAllClients).catch(() => { });
    } else if (isReseller) {
      ClientService.getAll().then(setAllClients).catch(() => { });
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
          <Button
            type="button"
            className="bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 cursor-pointer"
            onClick={() => setActiveTab("test")}
          >
            <Phone className="w-3.5 h-3.5" />
            Test Agent
          </Button>
          {canEdit && (
            <Button type="button" variant="outline" onClick={toggleStatus}>
              {a.status === "active" ? <><Pause className="w-3.5 h-3.5 mr-1.5" /> Pause</> : <><Play className="w-3.5 h-3.5 mr-1.5" /> Resume</>}
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
        <TabsList className="grid w-full grid-cols-8 mb-6 bg-zinc-100 p-0.5 rounded-sm">
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
          <TabsTrigger
            value="test"
            className="flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold border border-transparent data-[state=active]:bg-purple-600 data-[state=active]:text-white shadow-none text-purple-700"
          >
            <Phone className="w-3.5 h-3.5" />
            Test Agent
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
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${editCallType === "inbound"
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
                  className={`flex items-center justify-center gap-1.5 py-2 px-3 text-xs border rounded-sm transition-all ${editCallType === "outbound"
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
                className={`flex flex-col items-center justify-center gap-1.5 py-6 px-4 border-2 border-dashed rounded-sm cursor-pointer transition-colors text-center ${isDraggingFile
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
                          className={`flex items-center justify-between text-xs p-1.5 rounded cursor-pointer transition-colors ${isChecked ? "bg-amber-100/60 text-amber-900 font-medium" : "text-zinc-700 hover:bg-zinc-100"
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
                          className={`flex items-center justify-between text-xs p-1.5 rounded cursor-pointer transition-colors ${isChecked ? "bg-purple-100/60 text-purple-900 font-medium" : "text-zinc-700 hover:bg-zinc-100"
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
                      className={`flex items-start gap-3 p-4 border rounded-sm transition-all ${isChecked
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

        {/* ── Dograh-Inspired Agent Tester Tab ──────────────────────── */}
        <TabsContent value="test" className="outline-none space-y-4">
          <div className="bg-white border border-zinc-200 rounded-sm shadow-xs overflow-hidden">
            {/* Header with Mode Switcher (Dograh style: Audio Mode vs Text Mode) */}
            <div className="px-5 py-3.5 border-b border-zinc-200 bg-zinc-50/70 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-900 flex items-center gap-1.5">
                  <Bot className="w-4 h-4 text-purple-600" />
                  Agent Tester Workspace
                </span>
                <span className="text-[10px] font-mono bg-zinc-200 px-2 py-0.5 rounded text-zinc-700">
                  ID: {a.id}
                </span>
              </div>

              {/* Mode Toggle Switcher */}
              <div className="flex items-center bg-zinc-200/80 p-0.5 rounded-md text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setTesterMode("audio")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-sm transition-all cursor-pointer ${
                    testerMode === "audio"
                      ? "bg-white text-zinc-900 shadow-2xs font-semibold"
                      : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  <Phone className="w-3.5 h-3.5 text-purple-600" />
                  Audio Call Mode
                </button>
                <button
                  type="button"
                  onClick={() => setTesterMode("text")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-sm transition-all cursor-pointer ${
                    testerMode === "text"
                      ? "bg-white text-zinc-900 shadow-2xs font-semibold"
                      : "text-zinc-600 hover:text-zinc-900"
                  }`}
                >
                  <MessageSquareText className="w-3.5 h-3.5 text-purple-600" />
                  Text Chat Mode
                </button>
              </div>
            </div>

            {/* MODE 1: Audio Call Mode (Dograh EmbeddedVoiceTester style) */}
            {testerMode === "audio" && (
              <div className="p-6 space-y-5 bg-slate-50/60 border-t border-zinc-200 min-h-[480px] flex flex-col justify-between">
                <div className="space-y-4">
                  {/* Status Banner Card */}
                  <div className="flex items-center justify-between p-4 rounded-lg bg-white border border-zinc-200 shadow-2xs">
                    <div className="flex items-center gap-3.5">
                      <div className={`p-3 rounded-full transition-all ${isCallActive ? "bg-emerald-50 text-emerald-600 border border-emerald-200 animate-pulse shadow-xs" : "bg-purple-50 text-purple-600 border border-purple-100"}`}>
                        <Radio className={`w-6 h-6 ${isCallActive ? "animate-pulse" : ""}`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-zinc-900 tracking-wide">Live WebRTC Voice Call</h3>
                          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${isCallActive ? "bg-emerald-100 text-emerald-800 border border-emerald-300 animate-pulse" : "bg-zinc-100 text-zinc-600 border border-zinc-200"}`}>
                            {livekitStatusText}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-500 mt-0.5">
                          Stream live audio directly to <span className="font-semibold text-zinc-800">{a.name}</span> using local WebRTC worker
                        </p>
                      </div>
                    </div>

                    {isCallActive && (
                      <div className="hidden sm:flex items-center gap-1.5 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-200">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                        <span className="text-[11px] font-mono font-semibold text-emerald-700">LIVE AUDIO STREAM</span>
                      </div>
                    )}
                  </div>

                  {/* Realtime Feedback Speech Timeline Container */}
                  <div className="bg-white border border-zinc-200 rounded-lg p-4 h-[300px] overflow-y-auto space-y-3 shadow-inner">
                    <div className="flex items-center justify-between border-b border-zinc-150 pb-2">
                      <span className="text-[10px] font-bold font-mono text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                        Realtime Speech Timeline
                      </span>
                      {testMessages.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setTestMessages([])}
                          className="text-[10px] font-medium text-zinc-400 hover:text-zinc-700 transition-colors"
                        >
                          Clear Timeline
                        </button>
                      )}
                    </div>

                    {testMessages.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-48 text-center space-y-2">
                        <div className="w-12 h-12 rounded-full bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 shadow-2xs">
                          <Mic className="w-6 h-6" />
                        </div>
                        <p className="text-xs font-semibold text-zinc-800">No audio exchanges recorded yet</p>
                        <p className="text-[11px] text-zinc-500 max-w-sm">
                          Click <span className="font-semibold text-purple-700">"Start Voice Test Call"</span> below to connect your microphone and speak directly with <span className="font-semibold">{a.name}</span>.
                        </p>
                      </div>
                    ) : (
                      testMessages.map((m) => (
                        <div key={m.id} className="flex items-start gap-3 text-xs animate-in fade-in slide-in-from-bottom-1 duration-200">
                          <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded-md shrink-0 shadow-2xs ${
                            m.speaker === "user" 
                              ? "bg-purple-100 text-purple-800 border border-purple-200" 
                              : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          }`}>
                            {m.speaker === "user" ? "YOU" : "AGENT"}
                          </span>
                          <div className={`flex-1 p-2.5 rounded-lg border text-zinc-800 font-medium leading-relaxed ${
                            m.speaker === "user"
                              ? "bg-purple-50/50 border-purple-100/80"
                              : "bg-emerald-50/50 border-emerald-100/80"
                          }`}>
                            {m.text}
                          </div>
                          <span className="text-[10px] text-zinc-400 font-mono self-center shrink-0">{m.timestamp}</span>
                        </div>
                      ))
                    )}
                    <div ref={chatBottomRef} />
                  </div>
                </div>

                {/* Call Controller Footer */}
                <div className="pt-3 border-t border-zinc-200 flex items-center gap-3">
                  {!isCallActive ? (
                    <Button
                      type="button"
                      onClick={startLivekitVoiceCall}
                      disabled={isConnectingCall}
                      className="w-full bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 hover:from-purple-700 hover:to-indigo-800 text-white font-bold h-12 text-sm shadow-md cursor-pointer transition-all"
                    >
                      {isConnectingCall ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          Establishing WebRTC Connection...
                        </>
                      ) : (
                        <>
                          <Phone className="w-4 h-4 mr-2" />
                          Start Voice Test Call
                        </>
                      )}
                    </Button>
                  ) : (
                    <div className="flex items-center gap-3 w-full">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={toggleMuteMic}
                        className={`h-12 px-5 text-xs font-semibold rounded-md transition-all ${
                          isMicMuted 
                            ? "bg-rose-50 border-rose-300 text-rose-700 hover:bg-rose-100" 
                            : "bg-white border-zinc-300 text-zinc-800 hover:bg-zinc-50"
                        }`}
                      >
                        {isMicMuted ? <><MicOff className="w-4 h-4 mr-2 text-rose-600" /> Unmute Mic</> : <><Mic className="w-4 h-4 mr-2 text-emerald-600" /> Mute Mic</>}
                      </Button>
                      <Button
                        type="button"
                        onClick={endLivekitVoiceCall}
                        className="flex-1 bg-rose-600 hover:bg-rose-700 text-white font-bold h-12 text-sm shadow-md cursor-pointer rounded-md transition-all"
                      >
                        <PhoneOff className="w-4 h-4 mr-2" />
                        End Voice Call
                      </Button>
                    </div>
                  )}
                </div>
                <div ref={audioContainerRef} className="hidden" />
              </div>
            )}

            {/* MODE 2: Text Chat Mode (Dograh ManualTextChatPanel style) */}
            {testerMode === "text" && (
              <div className="flex flex-col h-[520px] bg-white">
                {/* Transcript Action Header */}
                <div className="px-4 py-2 border-b border-zinc-100 bg-zinc-50 flex items-center justify-between">
                  <span className="text-[11px] text-zinc-500 font-mono">Session ID: {testSessionId}</span>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleClearTestChat}
                      className="h-7 text-xs text-zinc-600"
                    >
                      <RefreshCw className="w-3 h-3 mr-1" /> Reset
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleDownloadTranscript}
                      className="h-7 text-xs text-zinc-600"
                    >
                      <Download className="w-3 h-3 mr-1" /> Export Transcript
                    </Button>
                  </div>
                </div>

                {/* Message Log */}
                <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-zinc-50/40">
                  {testMessages.map((m) => (
                    <div
                      key={m.id}
                      className={`flex flex-col ${m.speaker === "user" ? "items-end" : "items-start"}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[10px] font-bold uppercase text-zinc-400 font-mono">
                          {m.speaker === "user" ? "YOU" : a.name.toUpperCase()}
                        </span>
                        <span className="text-[10px] text-zinc-400 font-mono">{m.timestamp}</span>
                      </div>
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-2.5 text-xs leading-relaxed shadow-2xs ${
                          m.speaker === "user"
                            ? "bg-purple-600 text-white rounded-br-none"
                            : "bg-white border border-zinc-200 text-zinc-800 rounded-bl-none font-medium"
                        }`}
                      >
                        {m.text}
                      </div>
                    </div>
                  ))}

                  {isThinking && (
                    <div className="flex flex-col items-start">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[10px] font-bold uppercase text-purple-600 font-mono">{a.name.toUpperCase()}</span>
                        <span className="text-[10px] text-zinc-400 font-mono">Thinking...</span>
                      </div>
                      <div className="bg-white border border-zinc-200 rounded-lg px-4 py-3 text-xs text-zinc-500 flex items-center gap-2 shadow-2xs">
                        <div className="w-2 h-2 rounded-full bg-purple-600 animate-bounce" />
                        <div className="w-2 h-2 rounded-full bg-purple-600 animate-bounce [animation-delay:0.2s]" />
                        <div className="w-2 h-2 rounded-full bg-purple-600 animate-bounce [animation-delay:0.4s]" />
                        <span className="ml-1 text-[11px] font-medium text-zinc-400">Generating response...</span>
                      </div>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>

                {/* Sample Prompts */}
                <div className="px-4 py-2 bg-white border-t border-zinc-100 flex items-center gap-2 overflow-x-auto">
                  <span className="text-[10px] font-bold uppercase text-zinc-400 shrink-0">Sample prompts:</span>
                  {[
                    "Hello, introduce yourself!",
                    "What services can you help me with?",
                    "Can you guide me on booking an appointment?",
                    "Tell me about your features."
                  ].map((sample, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSendTestMessage(sample)}
                      disabled={isThinking}
                      className="text-[11px] bg-zinc-100 hover:bg-zinc-200 text-zinc-700 px-2.5 py-1 rounded border border-zinc-200 shrink-0 transition-colors cursor-pointer"
                    >
                      {sample}
                    </button>
                  ))}
                </div>

                {/* Chat Composer */}
                <div className="p-3 border-t border-zinc-200 bg-white flex items-center gap-2">
                  <Input
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendTestMessage();
                      }
                    }}
                    disabled={isThinking}
                    placeholder={`Type a message to test ${a.name}... (Press Enter)`}
                    className="text-xs h-10 bg-white"
                  />
                  <Button
                    type="button"
                    onClick={() => handleSendTestMessage()}
                    disabled={isThinking || !testInput.trim()}
                    className="bg-purple-600 hover:bg-purple-700 text-white h-10 px-4 shrink-0 cursor-pointer"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

    </div>
  );
}
