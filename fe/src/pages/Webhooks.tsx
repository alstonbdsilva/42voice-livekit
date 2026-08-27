import React, { useState } from "react";
import PageHeader from "@/components/PageHeader";
import {
  Webhook,
  Plus,
  Send,
  CheckCircle2,
  Clock,
  Activity,
  SlidersHorizontal,
  Key,
  ShieldCheck,
  Trash2,
  Edit3,
  Terminal,
  RefreshCw,
  Copy,
  Check,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import WebhookFormModal from "@/components/webhook/WebhookFormModal";
import WebhookTestModal, { WebhookEndpoint } from "@/components/webhook/WebhookTestModal";
import TriggerWebhookUrls from "@/components/webhook/TriggerWebhookUrls";
import WebhookLogsTable from "@/components/webhook/WebhookLogsTable";

const INITIAL_ENDPOINTS: WebhookEndpoint[] = [
  {
    id: "wh_01h9a82b",
    name: "HubSpot CRM Lead Sync",
    url: "https://api.hubspot.com/webhooks/v1/42voice-leads",
    status: "active",
    events: ["call.completed", "transcript.completed", "analysis.completed"],
    authType: "bearer_token",
    secret: "whsec_hubspot_9981247192837419",
    createdAt: "2026-08-01",
    lastTriggered: "2 mins ago",
    successRate: 99.8,
  },
  {
    id: "wh_02k918bc",
    name: "Slack Outbound Alert Bot",
    url: "https://hooks.slack.com/services/T0000/B000/XXXXXX",
    status: "active",
    events: ["call.started", "call.completed"],
    authType: "none",
    secret: "whsec_slack_10284719283749",
    createdAt: "2026-08-05",
    lastTriggered: "4 mins ago",
    successRate: 100,
  },
  {
    id: "wh_03m719cc",
    name: "Salesforce Activity Logger",
    url: "https://my-instance.salesforce.com/services/apexrest/VoiceEvents",
    status: "paused",
    events: ["transcript.completed", "recording.ready"],
    authType: "api_key",
    secret: "whsec_salesforce_991823749",
    createdAt: "2026-08-10",
    lastTriggered: "1 hour ago",
    successRate: 94.2,
  },
];

export default function Webhooks() {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>(INITIAL_ENDPOINTS);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookEndpoint | null>(null);
  const [testingWebhook, setTestingWebhook] = useState<WebhookEndpoint | null>(null);

  const handleToggleStatus = (id: string) => {
    setEndpoints((prev) =>
      prev.map((ep) => {
        if (ep.id === id) {
          const nextStatus = ep.status === "active" ? "paused" : "active";
          toast.success(`Webhook "${ep.name}" set to ${nextStatus.toUpperCase()}`);
          return { ...ep, status: nextStatus };
        }
        return ep;
      })
    );
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Are you sure you want to delete the webhook "${name}"?`)) {
      setEndpoints((prev) => prev.filter((ep) => ep.id !== id));
      toast.success(`Deleted webhook "${name}"`);
    }
  };

  const handleSaveEndpoint = (saved: WebhookEndpoint) => {
    setEndpoints((prev) => {
      const exists = prev.some((e) => e.id === saved.id);
      if (exists) {
        return prev.map((e) => (e.id === saved.id ? saved : e));
      }
      return [saved, ...prev];
    });
  };

  const activeCount = endpoints.filter((e) => e.status === "active").length;

  return (
    <div data-testid="webhooks-page" className="w-full space-y-6">
      <PageHeader
        title="Webhooks & API Triggers"
        subtitle="Manage HTTP webhook destinations, incoming event triggers, payload signing keys, and delivery logs."
        actions={
          <Button
            onClick={() => {
              setEditingWebhook(null);
              setIsFormOpen(true);
            }}
            className="text-xs bg-zinc-950 hover:bg-zinc-800 text-white"
          >
            <Plus className="w-3.5 h-3.5 mr-1" /> Add Webhook Endpoint
          </Button>
        }
      />

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-1">
          <div className="flex items-center justify-between text-zinc-500 text-xs font-semibold uppercase tracking-wider">
            <span>Active Webhooks</span>
            <Webhook className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-zinc-950 font-display">
            {activeCount} <span className="text-xs text-zinc-400 font-normal">/ {endpoints.length} Total</span>
          </div>
          <div className="text-[11px] text-zinc-500 font-medium">Configured endpoints receiving events</div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-1">
          <div className="flex items-center justify-between text-zinc-500 text-xs font-semibold uppercase tracking-wider">
            <span>Total Deliveries</span>
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-zinc-950 font-display">14,290</div>
          <div className="text-[11px] text-emerald-600 font-medium">+1,420 events in last 24h</div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-1">
          <div className="flex items-center justify-between text-zinc-500 text-xs font-semibold uppercase tracking-wider">
            <span>Delivery Success Rate</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-zinc-950 font-display">99.4%</div>
          <div className="text-[11px] text-zinc-500 font-medium">Automatic retry enabled (max 3 retries)</div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-1">
          <div className="flex items-center justify-between text-zinc-500 text-xs font-semibold uppercase tracking-wider">
            <span>Avg Response Latency</span>
            <Clock className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-zinc-950 font-display">142 ms</div>
          <div className="text-[11px] text-zinc-500 font-medium">Sub-second webhook execution time</div>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="endpoints" className="w-full">
        <TabsList className="grid grid-cols-3 max-w-[540px] mb-6">
          <TabsTrigger value="endpoints" className="flex items-center justify-center gap-2 text-xs">
            <Webhook className="w-3.5 h-3.5" /> Webhook Endpoints ({endpoints.length})
          </TabsTrigger>
          <TabsTrigger value="inbound" className="flex items-center justify-center gap-2 text-xs">
            <Terminal className="w-3.5 h-3.5" /> Inbound Triggers
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex items-center justify-center gap-2 text-xs">
            <Activity className="w-3.5 h-3.5" /> Delivery Logs
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Webhook Endpoints */}
        <TabsContent value="endpoints" className="space-y-4 outline-none">
          <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
            <div className="p-4 border-b border-zinc-200 flex items-center justify-between flex-wrap gap-2">
              <div>
                <h3 className="text-sm font-bold text-zinc-950">Active Outbound Webhooks</h3>
                <p className="text-xs text-zinc-500">Real-time HTTP callbacks fired when voice events occur.</p>
              </div>
              <Button
                onClick={() => {
                  setEditingWebhook(null);
                  setIsFormOpen(true);
                }}
                className="text-xs bg-zinc-950 hover:bg-zinc-800 text-white"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Add Webhook
              </Button>
            </div>

            <div className="divide-y divide-zinc-200">
              {endpoints.map((ep) => (
                <div key={ep.id} className="p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 hover:bg-zinc-50/50 transition-colors">
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-bold text-sm text-zinc-950">{ep.name}</span>
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded-full ${
                          ep.status === "active"
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                            : "bg-amber-100 text-amber-800 border border-amber-200"
                        }`}
                      >
                        {ep.status}
                      </span>
                      <span className="text-[11px] text-zinc-400 font-mono">ID: {ep.id}</span>
                    </div>

                    <div className="text-xs font-mono text-indigo-600 truncate max-w-xl bg-zinc-50 p-1.5 rounded-xs border border-zinc-200">
                      {ep.url}
                    </div>

                    <div className="flex items-center gap-2 flex-wrap pt-1">
                      <span className="text-[11px] font-semibold text-zinc-500">Subscribed Events:</span>
                      {ep.events.map((evt) => (
                        <span key={evt} className="px-2 py-0.5 text-[10px] font-mono font-medium bg-zinc-100 text-zinc-700 rounded-xs border border-zinc-200">
                          {evt}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right hidden lg:block">
                      <div className="text-xs font-semibold text-emerald-600">{ep.successRate}% Success</div>
                      <div className="text-[10px] text-zinc-400">Last: {ep.lastTriggered}</div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setTestingWebhook(ep)}
                        className="text-xs h-8 bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      >
                        <Send className="w-3.5 h-3.5 mr-1 text-indigo-600" /> Test
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setEditingWebhook(ep);
                          setIsFormOpen(true);
                        }}
                        className="text-xs h-8 bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </Button>
                      <Switch
                        checked={ep.status === "active"}
                        onCheckedChange={() => handleToggleStatus(ep.id)}
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(ep.id, ep.name)}
                        className="text-xs h-8 border-zinc-200 text-rose-600 hover:bg-rose-50 hover:border-rose-300"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Inbound Trigger URLs */}
        <TabsContent value="inbound" className="outline-none">
          <TriggerWebhookUrls />
        </TabsContent>

        {/* Tab 3: Delivery Audit Logs */}
        <TabsContent value="logs" className="outline-none">
          <WebhookLogsTable />
        </TabsContent>
      </Tabs>

      {/* Form Modal */}
      <WebhookFormModal
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        webhookToEdit={editingWebhook}
        onSave={handleSaveEndpoint}
      />

      {/* Test Modal */}
      <WebhookTestModal
        open={!!testingWebhook}
        onOpenChange={() => setTestingWebhook(null)}
        webhook={testingWebhook}
      />
    </div>
  );
}
