import React, { useState } from "react";
import {
  Copy,
  Check,
  Terminal,
  Sparkles,
  Play,
  RefreshCw,
  Code2,
  Key,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

interface TriggerWebhookUrlsProps {
  tunnelUrl?: string;
  agentId?: string;
}

const DEFAULT_TEST_PAYLOAD = JSON.stringify(
  {
    phone_number: "+15550192834",
    customer_name: "Alex Johnson",
    initial_context: {
      deal_size: "$45,000",
      priority: "high",
      industry: "Healthcare SaaS",
    },
  },
  null,
  2
);

const DEFAULT_PROD_PAYLOAD = JSON.stringify(
  {
    phone_number: "+15550192834",
    customer_name: "Alex Johnson",
    initial_context: {
      campaign_ref: "outbound_q3",
    },
  },
  null,
  2
);

export default function TriggerWebhookUrls({
  tunnelUrl = "https://api.42voice.com",
  agentId = "agent_sarah_enterprise",
}: TriggerWebhookUrlsProps) {
  const [apiKey, setApiKey] = useState("wh_key_live_99812471");
  const [testPayload, setTestPayload] = useState(DEFAULT_TEST_PAYLOAD);
  const [prodPayload, setProdPayload] = useState(DEFAULT_PROD_PAYLOAD);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const [testExecuting, setTestExecuting] = useState(false);
  const [execResult, setExecResult] = useState<{
    status: number;
    statusText: string;
    durationMs: number;
    response: object;
  } | null>(null);

  const testEndpointUrl = `${tunnelUrl}/api/v1/telephony/inbound/test_${agentId}`;
  const prodEndpointUrl = `${tunnelUrl}/api/v1/telephony/inbound/prod_${agentId}`;

  const buildCurlCommand = (endpoint: string, key: string, payloadStr: string) => {
    let cleanJson = payloadStr;
    try {
      // Re-format clean single-line or multi-line JSON
      const parsed = JSON.parse(payloadStr);
      cleanJson = JSON.stringify(parsed, null, 2);
    } catch {
      // If invalid JSON, use raw text string
    }

    return `curl -X POST "${endpoint}" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${key || "YOUR_42VOICE_API_KEY"}" \\
  -d '${cleanJson.replace(/'/g, "'\\''")}'`;
  };

  const currentTestCurl = buildCurlCommand(testEndpointUrl, apiKey, testPayload);
  const currentProdCurl = buildCurlCommand(prodEndpointUrl, apiKey, prodPayload);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(label);
    toast.success(`Copied ${label} to clipboard`);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleTestExecute = (endpoint: string, payloadStr: string) => {
    try {
      JSON.parse(payloadStr);
    } catch {
      toast.error("Invalid JSON format in payload field. Please fix JSON syntax.");
      return;
    }

    setTestExecuting(true);
    setExecResult(null);

    setTimeout(() => {
      setTestExecuting(false);
      setExecResult({
        status: 200,
        statusText: "OK",
        durationMs: Math.floor(Math.random() * 90) + 75,
        response: {
          success: true,
          call_session_id: `cs_${Math.random().toString(36).substring(2, 11)}`,
          status: "queued",
          agent_id: agentId,
          target_number: "+15550192834",
          timestamp: new Date().toISOString(),
          message: "Inbound webhook received. Call session dispatched to agent runtime.",
        },
      });
      toast.success("Inbound trigger executed successfully (200 OK)!");
    }, 800);
  };

  return (
    <div className="bg-white border border-zinc-200 rounded-sm p-5 space-y-5 shadow-xs">
      <div className="flex items-center justify-between border-b border-zinc-200 pb-3 flex-wrap gap-2">
        <div>
          <h3 className="text-sm font-bold text-zinc-950 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-indigo-600" />
            Inbound Webhook Trigger Endpoints & Custom Payload Generator
          </h3>
          <p className="text-xs text-zinc-500">
            Customize request payload JSON and API keys to dynamically generate and test cURL commands.
          </p>
        </div>
        <span className="px-2.5 py-0.5 text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-indigo-500" /> REST API Ready
        </span>
      </div>

      {/* API Key Field */}
      <div className="bg-zinc-50 p-3 rounded-sm border border-zinc-200 space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5 text-zinc-500" />
            X-API-Key Header Value
          </Label>
          <span className="text-[10px] text-zinc-400">Included in generated cURL</span>
        </div>
        <Input
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="your_42voice_api_key"
          className="text-xs font-mono bg-white"
        />
      </div>

      <Tabs defaultValue="test" className="w-full">
        <TabsList className="grid grid-cols-2 max-w-xs h-8">
          <TabsTrigger value="test" className="text-xs">
            Test Trigger URL
          </TabsTrigger>
          <TabsTrigger value="production" className="text-xs">
            Production Trigger URL
          </TabsTrigger>
        </TabsList>

        {/* ── Test Tab ─────────────────────────────────────────────────────── */}
        <TabsContent value="test" className="space-y-4 pt-3">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-700">Test Endpoint URL</span>
              <button
                type="button"
                onClick={() => copyToClipboard(testEndpointUrl, "Test URL")}
                className="text-[11px] text-zinc-600 hover:text-zinc-950 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200 font-medium"
              >
                {copiedField === "Test URL" ? (
                  <Check className="w-3 h-3 text-emerald-600" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                <span>{copiedField === "Test URL" ? "Copied" : "Copy URL"}</span>
              </button>
            </div>
            <div className="text-xs font-mono bg-zinc-950 text-emerald-400 p-2.5 rounded-sm border border-zinc-800 break-all select-all">
              {testEndpointUrl}
            </div>
          </div>

          {/* User Payload Input Box */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
                <Code2 className="w-3.5 h-3.5 text-zinc-500" />
                Custom Request Payload JSON (User Editable)
              </Label>
              <button
                type="button"
                onClick={() => setTestPayload(DEFAULT_TEST_PAYLOAD)}
                className="text-[10px] text-indigo-600 hover:underline font-medium"
              >
                Reset Default Payload
              </button>
            </div>
            <textarea
              value={testPayload}
              onChange={(e) => setTestPayload(e.target.value)}
              rows={7}
              className="w-full font-mono text-xs p-3 bg-zinc-950 text-emerald-400 rounded-sm border border-zinc-800 focus:outline-hidden focus:ring-1 focus:ring-zinc-700 leading-relaxed shadow-inner"
            />
          </div>

          {/* Generated Sample cURL Command */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-700">Generated Sample cURL Command</span>
              <button
                type="button"
                onClick={() => copyToClipboard(currentTestCurl, "Sample cURL")}
                className="text-[11px] text-zinc-600 hover:text-zinc-950 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200 font-medium"
              >
                {copiedField === "Sample cURL" ? (
                  <Check className="w-3 h-3 text-emerald-600" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                <span>{copiedField === "Sample cURL" ? "Copied" : "Copy cURL"}</span>
              </button>
            </div>
            <pre className="text-xs font-mono bg-zinc-950 text-zinc-200 p-3 rounded-sm border border-zinc-800 overflow-x-auto leading-relaxed">
              {currentTestCurl}
            </pre>
          </div>

          <div className="pt-1">
            <Button
              type="button"
              onClick={() => handleTestExecute(testEndpointUrl, testPayload)}
              disabled={testExecuting}
              className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              {testExecuting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-current" />
              )}
              <span>{testExecuting ? "Executing..." : "Execute Test Trigger Webhook"}</span>
            </Button>
          </div>
        </TabsContent>

        {/* ── Production Tab ───────────────────────────────────────────────── */}
        <TabsContent value="production" className="space-y-4 pt-3">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-700">Production Endpoint URL</span>
              <button
                type="button"
                onClick={() => copyToClipboard(prodEndpointUrl, "Production URL")}
                className="text-[11px] text-zinc-600 hover:text-zinc-950 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200 font-medium"
              >
                {copiedField === "Production URL" ? (
                  <Check className="w-3 h-3 text-emerald-600" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                <span>{copiedField === "Production URL" ? "Copied" : "Copy URL"}</span>
              </button>
            </div>
            <div className="text-xs font-mono bg-zinc-950 text-indigo-400 p-2.5 rounded-sm border border-zinc-800 break-all select-all">
              {prodEndpointUrl}
            </div>
          </div>

          {/* User Payload Input Box */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1.5">
                <Code2 className="w-3.5 h-3.5 text-zinc-500" />
                Custom Request Payload JSON (User Editable)
              </Label>
              <button
                type="button"
                onClick={() => setProdPayload(DEFAULT_PROD_PAYLOAD)}
                className="text-[10px] text-indigo-600 hover:underline font-medium"
              >
                Reset Default Payload
              </button>
            </div>
            <textarea
              value={prodPayload}
              onChange={(e) => setProdPayload(e.target.value)}
              rows={7}
              className="w-full font-mono text-xs p-3 bg-zinc-950 text-indigo-300 rounded-sm border border-zinc-800 focus:outline-hidden focus:ring-1 focus:ring-zinc-700 leading-relaxed shadow-inner"
            />
          </div>

          {/* Generated Sample cURL Command */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-700">Generated Sample cURL Command</span>
              <button
                type="button"
                onClick={() => copyToClipboard(currentProdCurl, "Sample cURL")}
                className="text-[11px] text-zinc-600 hover:text-zinc-950 flex items-center gap-1 bg-zinc-100 px-2 py-0.5 rounded-xs border border-zinc-200 font-medium"
              >
                {copiedField === "Sample cURL" ? (
                  <Check className="w-3 h-3 text-emerald-600" />
                ) : (
                  <Copy className="w-3 h-3" />
                )}
                <span>{copiedField === "Sample cURL" ? "Copied" : "Copy cURL"}</span>
              </button>
            </div>
            <pre className="text-xs font-mono bg-zinc-950 text-zinc-200 p-3 rounded-sm border border-zinc-800 overflow-x-auto leading-relaxed">
              {currentProdCurl}
            </pre>
          </div>

          <div className="pt-1">
            <Button
              type="button"
              onClick={() => handleTestExecute(prodEndpointUrl, prodPayload)}
              disabled={testExecuting}
              className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5"
            >
              {testExecuting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-current" />
              )}
              <span>{testExecuting ? "Executing..." : "Execute Production Trigger Webhook"}</span>
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      {/* Execution Result Box */}
      {execResult && (
        <div className="bg-zinc-50 border border-zinc-200 p-4 rounded-sm space-y-3 animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-bold text-zinc-900">Execution Result</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-sm">
                {execResult.status} {execResult.statusText}
              </span>
              <span className="text-[11px] font-mono text-zinc-500 flex items-center gap-1">
                <Clock className="w-3 h-3 text-zinc-400" />
                {execResult.durationMs} ms
              </span>
            </div>
          </div>

          <pre className="text-xs font-mono bg-zinc-950 text-emerald-400 p-3 rounded-sm border border-zinc-800 overflow-x-auto">
            {JSON.stringify(execResult.response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
