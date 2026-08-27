import React, { useState, useEffect } from "react";
import {
  Webhook,
  Key,
  ShieldCheck,
  RefreshCw,
  Plus,
  Info,
  Check,
  Lock,
  Globe,
  Sliders,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { WebhookEndpoint } from "./WebhookTestModal";

interface WebhookFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhookToEdit?: WebhookEndpoint | null;
  onSave: (webhook: WebhookEndpoint) => void;
}

const AVAILABLE_EVENTS = [
  { id: "call.started", label: "Call Started", desc: "Triggered when a call session initiates" },
  { id: "call.completed", label: "Call Completed", desc: "Triggered when call ends with disposition summary" },
  { id: "transcript.completed", label: "Transcript Completed", desc: "Delivers full turn-by-turn conversation text" },
  { id: "analysis.completed", label: "Analysis & Data Extracted", desc: "Delivers extracted CRM variables & intent analysis" },
  { id: "recording.ready", label: "Recording Ready", desc: "Delivers signed MP3 audio download link" },
  { id: "lead.disqualified", label: "Lead Disqualified", desc: "Triggered if call outcome fails qualification criteria" },
];

export default function WebhookFormModal({
  open,
  onOpenChange,
  webhookToEdit,
  onSave,
}: WebhookFormModalProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [authType, setAuthType] = useState<WebhookEndpoint["authType"]>("bearer_token");
  const [bearerToken, setBearerToken] = useState("");
  const [apiKeyHeader, setApiKeyHeader] = useState("X-API-Key");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [basicUser, setBasicUser] = useState("");
  const [basicPass, setBasicPass] = useState("");
  const [customHeaderName, setCustomHeaderName] = useState("");
  const [customHeaderVal, setCustomHeaderVal] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([
    "call.completed",
    "transcript.completed",
  ]);

  useEffect(() => {
    if (webhookToEdit) {
      setName(webhookToEdit.name);
      setUrl(webhookToEdit.url);
      setAuthType(webhookToEdit.authType || "bearer_token");
      setSelectedEvents(webhookToEdit.events || ["call.completed"]);
      setSecret(webhookToEdit.secret || `whsec_${Math.random().toString(36).substring(2, 18)}`);
    } else {
      setName("");
      setUrl("");
      setAuthType("bearer_token");
      setBearerToken("");
      setApiKeyHeader("X-API-Key");
      setApiKeyValue("");
      setBasicUser("");
      setBasicPass("");
      setCustomHeaderName("");
      setCustomHeaderVal("");
      setSelectedEvents(["call.completed", "transcript.completed"]);
      setSecret(`whsec_${Math.random().toString(36).substring(2, 18)}`);
    }
  }, [webhookToEdit, open]);

  const handleGenerateSecret = () => {
    const newSec = `whsec_${Math.random().toString(36).substring(2, 20)}${Math.random().toString(36).substring(2, 10)}`;
    setSecret(newSec);
    toast.success("Generated new HMAC signing secret");
  };

  const toggleEvent = (evtId: string) => {
    if (selectedEvents.includes(evtId)) {
      if (selectedEvents.length === 1) {
        toast.error("At least one event trigger must be selected");
        return;
      }
      setSelectedEvents(selectedEvents.filter((e) => e !== evtId));
    } else {
      setSelectedEvents([...selectedEvents, evtId]);
    }
  };

  const handleSave = () => {
    if (!name.trim()) {
      toast.error("Please enter a webhook name");
      return;
    }

    if (!url.trim() || !url.startsWith("http")) {
      toast.error("Please enter a valid target URL starting with http:// or https://");
      return;
    }

    const saved: WebhookEndpoint = {
      id: webhookToEdit?.id || `wh_${Math.random().toString(36).substring(2, 10)}`,
      name: name.trim(),
      url: url.trim(),
      status: webhookToEdit?.status || "active",
      events: selectedEvents,
      authType,
      secret,
      createdAt: webhookToEdit?.createdAt || new Date().toISOString().split("T")[0],
      lastTriggered: webhookToEdit?.lastTriggered || "Just now",
      successRate: webhookToEdit?.successRate || 100,
    };

    onSave(saved);
    toast.success(webhookToEdit ? "Webhook endpoint updated successfully" : "Webhook endpoint created successfully");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-bold text-zinc-950">
            <Webhook className="w-4 h-4 text-indigo-600" />
            {webhookToEdit ? "Edit Webhook Endpoint" : "Add Webhook Endpoint"}
          </DialogTitle>
          <DialogDescription className="text-xs text-zinc-500">
            Configure target destination endpoint and security parameters to receive automated voice event callbacks.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Webhook Name & Target URL */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-zinc-700">Webhook Name *</Label>
              <Input
                placeholder="e.g. HubSpot CRM Sync Webhook"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-zinc-700">Target Endpoint URL *</Label>
              <Input
                placeholder="https://api.yourdomain.com/webhooks/voice"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="text-xs font-mono"
              />
            </div>
          </div>

          {/* Event Triggers Checklist */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold text-zinc-700">Subscribed Event Triggers *</Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {AVAILABLE_EVENTS.map((evt) => {
                const isSelected = selectedEvents.includes(evt.id);
                return (
                  <div
                    key={evt.id}
                    onClick={() => toggleEvent(evt.id)}
                    className={`p-2.5 border rounded-sm cursor-pointer transition-all flex items-start gap-2.5 ${
                      isSelected
                        ? "border-zinc-950 bg-zinc-50 ring-1 ring-zinc-950 shadow-xs"
                        : "border-zinc-200 bg-white hover:bg-zinc-50/50"
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-xs border flex items-center justify-center mt-0.5 shrink-0 ${
                        isSelected ? "bg-zinc-950 border-zinc-950 text-white" : "border-zinc-300 bg-white"
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                    </div>
                    <div>
                      <div className="text-xs font-bold text-zinc-900">{evt.label}</div>
                      <div className="text-[10px] text-zinc-500 leading-tight mt-0.5">{evt.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Authentication Type */}
          <div className="space-y-2 border-t border-zinc-200 pt-3">
            <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-zinc-500" />
              Authentication & Credentials
            </Label>
            <select
              value={authType}
              onChange={(e) => setAuthType(e.target.value as any)}
              className="w-full text-xs h-9 rounded-sm border border-zinc-300 bg-white px-2.5 shadow-xs focus:outline-hidden focus:ring-1 focus:ring-zinc-950"
            >
              <option value="bearer_token">Bearer Token (Authorization: Bearer ...)</option>
              <option value="api_key">API Key Header (X-API-Key: ...)</option>
              <option value="basic_auth">HTTP Basic Authentication (Username & Password)</option>
              <option value="custom_header">Custom Header & Value</option>
              <option value="none">No Authentication Header</option>
            </select>

            {/* Dynamic Credential Fields */}
            {authType === "bearer_token" && (
              <div className="space-y-1.5 bg-zinc-50 p-3 rounded-sm border border-zinc-200">
                <Label className="text-xs font-medium text-zinc-700">Bearer Token</Label>
                <Input
                  type="password"
                  placeholder="your-secret-bearer-token"
                  value={bearerToken}
                  onChange={(e) => setBearerToken(e.target.value)}
                  className="text-xs font-mono bg-white"
                />
              </div>
            )}

            {authType === "api_key" && (
              <div className="grid grid-cols-2 gap-2 bg-zinc-50 p-3 rounded-sm border border-zinc-200">
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">Header Name</Label>
                  <Input
                    placeholder="X-API-Key"
                    value={apiKeyHeader}
                    onChange={(e) => setApiKeyHeader(e.target.value)}
                    className="text-xs bg-white"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">API Key Value</Label>
                  <Input
                    type="password"
                    placeholder="key_secret_..."
                    value={apiKeyValue}
                    onChange={(e) => setApiKeyValue(e.target.value)}
                    className="text-xs font-mono bg-white"
                  />
                </div>
              </div>
            )}

            {authType === "basic_auth" && (
              <div className="grid grid-cols-2 gap-2 bg-zinc-50 p-3 rounded-sm border border-zinc-200">
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">Username</Label>
                  <Input
                    placeholder="webhook_user"
                    value={basicUser}
                    onChange={(e) => setBasicUser(e.target.value)}
                    className="text-xs bg-white"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">Password</Label>
                  <Input
                    type="password"
                    placeholder="••••••••••••"
                    value={basicPass}
                    onChange={(e) => setBasicPass(e.target.value)}
                    className="text-xs bg-white"
                  />
                </div>
              </div>
            )}

            {authType === "custom_header" && (
              <div className="grid grid-cols-2 gap-2 bg-zinc-50 p-3 rounded-sm border border-zinc-200">
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">Custom Header Name</Label>
                  <Input
                    placeholder="X-Custom-Auth"
                    value={customHeaderName}
                    onChange={(e) => setCustomHeaderName(e.target.value)}
                    className="text-xs bg-white"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-zinc-700">Header Value</Label>
                  <Input
                    type="password"
                    placeholder="value..."
                    value={customHeaderVal}
                    onChange={(e) => setCustomHeaderVal(e.target.value)}
                    className="text-xs font-mono bg-white"
                  />
                </div>
              </div>
            )}
          </div>

          {/* HMAC Signature Secret */}
          <div className="space-y-1.5 border-t border-zinc-200 pt-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                HMAC-SHA256 Secret Key (X-42Voice-Signature)
              </Label>
              <button
                type="button"
                onClick={handleGenerateSecret}
                className="text-[11px] text-zinc-600 hover:text-zinc-900 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Regenerate</span>
              </button>
            </div>
            <Input
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className="text-xs font-mono bg-zinc-50"
            />
            <p className="text-[10px] text-zinc-400">
              Use this secret key on your server to verify payload authenticity and prevent replay attacks.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs">
            Cancel
          </Button>
          <Button onClick={handleSave} className="text-xs bg-zinc-950 hover:bg-zinc-800 text-white">
            {webhookToEdit ? "Update Webhook" : "Create Webhook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
