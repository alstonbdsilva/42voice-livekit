import React, { useState } from "react";
import {
  Send,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Code2,
  Copy,
  Check,
  RefreshCw,
  Sparkles,
  ArrowRight,
  ShieldAlert,
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
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  status: "active" | "paused";
  events: string[];
  authType: "none" | "bearer_token" | "api_key" | "basic_auth" | "custom_header";
  secret?: string;
  createdAt: string;
  lastTriggered?: string;
  successRate: number;
}

interface WebhookTestModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhook: WebhookEndpoint | null;
}

const SAMPLE_PAYLOADS: Record<string, object> = {
  "call.started": {
    event: "call.started",
    timestamp: "2026-08-17T08:55:00Z",
    call_id: "call_98f7a1b2c3d4",
    agent_id: "sarah_sdr_01",
    customer_phone: "+1 (555) 234-5678",
    direction: "outbound",
    campaign_id: "camp_enterprise_q3",
  },
  "call.completed": {
    event: "call.completed",
    timestamp: "2026-08-17T08:58:30Z",
    call_id: "call_98f7a1b2c3d4",
    duration_seconds: 210,
    disposition: "qualified_lead",
    summary: "Customer expressed interest in enterprise tier pricing for 50 seats. Requested demo follow-up.",
    recording_url: "https://api.42voice.com/v1/recordings/rec_883921.mp3",
    metrics: {
      latency_ms: 135,
      interruption_count: 1,
      sentiment: "positive",
    },
  },
  "transcript.completed": {
    event: "transcript.completed",
    timestamp: "2026-08-17T08:58:35Z",
    call_id: "call_98f7a1b2c3d4",
    transcript: [
      { speaker: "agent", text: "Hello! This is Sarah from 42Voice, calling regarding your enterprise demo request." },
      { speaker: "customer", text: "Hi Sarah, yes! We are looking to automate our sales team's call workflows." },
    ],
  },
  "analysis.completed": {
    event: "analysis.completed",
    timestamp: "2026-08-17T08:59:00Z",
    call_id: "call_98f7a1b2c3d4",
    extracted_data: {
      budget: "$50,000/year",
      decision_maker: true,
      timeline: "Q3 2026",
      competitor_mention: "Vapi",
    },
  },
};

export default function WebhookTestModal({
  open,
  onOpenChange,
  webhook,
}: WebhookTestModalProps) {
  const [selectedEvent, setSelectedEvent] = useState<string>("call.completed");
  const [payloadText, setPayloadText] = useState<string>(
    JSON.stringify(SAMPLE_PAYLOADS["call.completed"], null, 2)
  );
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: number;
    statusText: string;
    durationMs: number;
    requestHeaders: Record<string, string>;
    responseHeaders: Record<string, string>;
    responseBody: object;
  } | null>(null);

  const handleEventChange = (eventName: string) => {
    setSelectedEvent(eventName);
    const sample = SAMPLE_PAYLOADS[eventName] || SAMPLE_PAYLOADS["call.completed"];
    setPayloadText(JSON.stringify(sample, null, 2));
    setTestResult(null);
  };

  const handleCopyPayload = () => {
    navigator.clipboard.writeText(payloadText);
    setCopied(true);
    toast.success("Payload copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSendTest = () => {
    if (!webhook) return;
    setIsLoading(true);

    try {
      // Validate JSON syntax
      JSON.parse(payloadText);
    } catch {
      toast.error("Invalid JSON payload format");
      setIsLoading(false);
      return;
    }

    setTimeout(() => {
      setIsLoading(false);
      setTestResult({
        status: 200,
        statusText: "OK",
        durationMs: Math.floor(Math.random() * 120) + 85,
        requestHeaders: {
          "Content-Type": "application/json",
          "User-Agent": "42Voice-Webhook-DeliveryEngine/2.0",
          "X-42Voice-Event": selectedEvent,
          "X-42Voice-Delivery": `del_${Math.random().toString(36).substring(2, 11)}`,
          "X-42Voice-Signature": `t=${Math.floor(Date.now() / 1000)},v1=${Math.random().toString(36).substring(2, 22)}`,
        },
        responseHeaders: {
          "Content-Type": "application/json; charset=utf-8",
          Server: "nginx/1.24.0",
          "X-Request-Id": `req_${Math.random().toString(36).substring(2, 10)}`,
        },
        responseBody: {
          received: true,
          status: "processed",
          event: selectedEvent,
          timestamp: new Date().toISOString(),
          message: "Test webhook payload received and validated successfully.",
        },
      });
      toast.success("Test webhook delivered successfully (200 OK)!");
    }, 900);
  };

  if (!webhook) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-bold text-zinc-950">
            <Send className="w-4 h-4 text-indigo-600" />
            Test Webhook Endpoint
          </DialogTitle>
          <DialogDescription className="text-xs text-zinc-500">
            Send a simulated event payload to verify endpoint connectivity, response latency, and payload parsing.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Endpoint Summary Card */}
          <div className="bg-zinc-50 border border-zinc-200 p-3 rounded-sm space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-zinc-900">{webhook.name}</span>
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-full">
                {webhook.status.toUpperCase()}
              </span>
            </div>
            <div className="text-xs font-mono bg-white p-2 rounded-xs border border-zinc-200 text-zinc-700 truncate">
              {webhook.url}
            </div>
          </div>

          {/* Select Event Type */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-zinc-700">Select Event Payload</Label>
            <div className="flex flex-wrap gap-2">
              {Object.keys(SAMPLE_PAYLOADS).map((evt) => (
                <button
                  key={evt}
                  type="button"
                  onClick={() => handleEventChange(evt)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-sm border transition-all ${
                    selectedEvent === evt
                      ? "bg-zinc-950 text-white border-zinc-950 shadow-xs"
                      : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
                  }`}
                >
                  {evt}
                </button>
              ))}
            </div>
          </div>

          {/* JSON Payload Editor / Viewer */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
                <Code2 className="w-3.5 h-3.5 text-zinc-500" />
                Request Payload (JSON)
              </Label>
              <button
                type="button"
                onClick={handleCopyPayload}
                className="text-[11px] text-zinc-600 hover:text-zinc-900 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? "Copied" : "Copy Payload"}</span>
              </button>
            </div>
            <textarea
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              rows={8}
              className="w-full font-mono text-xs p-3 bg-zinc-950 text-emerald-400 rounded-sm border border-zinc-800 focus:outline-hidden focus:ring-1 focus:ring-zinc-700 leading-relaxed shadow-inner"
            />
          </div>

          {/* Execution Result Box */}
          {testResult && (
            <div className="space-y-3 bg-zinc-50 border border-zinc-200 p-4 rounded-sm animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-bold text-zinc-900">Execution Result</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 text-xs font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-sm">
                    {testResult.status} {testResult.statusText}
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-zinc-400" />
                    {testResult.durationMs} ms
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                  Response Body
                </span>
                <pre className="text-xs font-mono bg-white p-3 rounded-sm border border-zinc-200 text-zinc-800 overflow-x-auto max-h-40">
                  {JSON.stringify(testResult.responseBody, null, 2)}
                </pre>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                  Request Headers Sent
                </span>
                <div className="bg-white p-2.5 rounded-sm border border-zinc-200 space-y-1">
                  {Object.entries(testResult.requestHeaders).map(([hk, hv]) => (
                    <div key={hk} className="flex text-[11px] font-mono">
                      <span className="text-zinc-500 w-44 font-semibold shrink-0">{hk}:</span>
                      <span className="text-zinc-900 truncate">{hv}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} className="text-xs">
            Close
          </Button>
          <Button
            onClick={handleSendTest}
            disabled={isLoading}
            className="text-xs bg-zinc-950 hover:bg-zinc-800 text-white flex items-center gap-1.5"
          >
            {isLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            <span>{isLoading ? "Delivering..." : "Send Test Webhook"}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
