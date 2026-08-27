import React, { useState } from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  Filter,
  Eye,
  RefreshCw,
  ArrowUpRight,
  Code2,
  AlertCircle,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export interface WebhookLogItem {
  id: string;
  webhookName: string;
  targetUrl: string;
  eventName: string;
  status: number;
  statusText: string;
  durationMs: number;
  attempts: number;
  timestamp: string;
  payload: object;
  response: object;
}

const INITIAL_LOGS: WebhookLogItem[] = [
  {
    id: "del_99812a3",
    webhookName: "HubSpot CRM Lead Sync",
    targetUrl: "https://api.hubspot.com/webhooks/v1/42voice-leads",
    eventName: "call.completed",
    status: 200,
    statusText: "OK",
    durationMs: 142,
    attempts: 1,
    timestamp: "2026-08-17 08:52:14",
    payload: {
      event: "call.completed",
      call_id: "call_987123",
      disposition: "qualified_lead",
      customer_phone: "+1 (555) 019-2831",
      duration_seconds: 245,
    },
    response: { success: true, record_id: "hs_rec_998231" },
  },
  {
    id: "del_99812a4",
    webhookName: "Slack Outbound Alert Bot",
    targetUrl: "https://hooks.slack.com/services/T0000/B000/XXXXXX",
    eventName: "call.started",
    status: 200,
    statusText: "OK",
    durationMs: 98,
    attempts: 1,
    timestamp: "2026-08-17 08:50:02",
    payload: {
      event: "call.started",
      call_id: "call_987123",
      agent_id: "sarah_sdr",
    },
    response: { ok: true },
  },
  {
    id: "del_99812a5",
    webhookName: "Salesforce Activity Logger",
    targetUrl: "https://my-instance.salesforce.com/services/apexrest/VoiceEvents",
    eventName: "transcript.completed",
    status: 500,
    statusText: "Internal Server Error",
    durationMs: 320,
    attempts: 3,
    timestamp: "2026-08-17 08:44:19",
    payload: {
      event: "transcript.completed",
      call_id: "call_987109",
    },
    response: { error: "DUPLICATE_VALUE: record already exists in database." },
  },
  {
    id: "del_99812a6",
    webhookName: "Zendesk Ticket Creator",
    targetUrl: "https://company.zendesk.com/api/v2/tickets.json",
    eventName: "analysis.completed",
    status: 201,
    statusText: "Created",
    durationMs: 185,
    attempts: 1,
    timestamp: "2026-08-17 08:31:05",
    payload: {
      event: "analysis.completed",
      call_id: "call_986991",
      urgent_flag: true,
    },
    response: { ticket: { id: 88412, status: "open" } },
  },
];

export default function WebhookLogsTable() {
  const [logs, setLogs] = useState<WebhookLogItem[]>(INITIAL_LOGS);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">("all");
  const [selectedLog, setSelectedLog] = useState<WebhookLogItem | null>(null);

  const filteredLogs = logs.filter((log) => {
    const matchSearch =
      log.webhookName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.targetUrl.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.eventName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "success" && log.status >= 200 && log.status < 300) ||
      (statusFilter === "error" && log.status >= 400);

    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-4">
      {/* Search & Filter Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 border border-zinc-200 rounded-sm shadow-xs">
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-zinc-400" />
          <Input
            placeholder="Search delivery logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 text-xs h-8 bg-zinc-50/50"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="flex items-center border border-zinc-200 rounded-sm bg-zinc-50 p-0.5">
            {(["all", "success", "error"] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 text-[11px] font-semibold rounded-xs transition-colors capitalize ${
                  statusFilter === st
                    ? "bg-white text-zinc-950 shadow-xs font-bold"
                    : "text-zinc-600 hover:text-zinc-950"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-200 text-[11px] font-bold uppercase tracking-wider text-zinc-600">
              <th className="py-2.5 px-3">Delivery ID</th>
              <th className="py-2.5 px-3">Webhook / Destination</th>
              <th className="py-2.5 px-3">Event Type</th>
              <th className="py-2.5 px-3">HTTP Status</th>
              <th className="py-2.5 px-3">Latency</th>
              <th className="py-2.5 px-3">Timestamp</th>
              <th className="py-2.5 px-3 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200">
            {filteredLogs.map((log) => {
              const isSuccess = log.status >= 200 && log.status < 300;
              return (
                <tr key={log.id} className="hover:bg-zinc-50/60 transition-colors">
                  <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-500">{log.id}</td>
                  <td className="py-2.5 px-3">
                    <div className="font-semibold text-zinc-900">{log.webhookName}</div>
                    <div className="font-mono text-[10px] text-zinc-400 truncate max-w-xs">{log.targetUrl}</div>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 text-[10px] font-mono font-medium bg-zinc-100 border border-zinc-200 text-zinc-700 rounded-xs">
                      {log.eventName}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded-sm inline-flex items-center gap-1 ${
                        isSuccess
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {isSuccess ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      {log.status} {log.statusText}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-zinc-500 text-[11px]">{log.durationMs} ms</td>
                  <td className="py-2.5 px-3 text-zinc-500 text-[11px]">{log.timestamp}</td>
                  <td className="py-2.5 px-3 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedLog(log)}
                      className="h-7 px-2 text-[11px] bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100"
                    >
                      <Eye className="w-3 h-3 mr-1" /> View Payload
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {filteredLogs.length === 0 && (
          <div className="py-12 text-center text-zinc-400 space-y-1">
            <AlertCircle className="w-6 h-6 mx-auto opacity-40" />
            <p className="text-xs font-semibold text-zinc-600">No delivery logs found</p>
          </div>
        )}
      </div>

      {/* Payload Inspector Modal */}
      {selectedLog && (
        <Dialog open={!!selectedLog} onOpenChange={() => setSelectedLog(null)}>
          <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-base font-bold text-zinc-950">
                <Code2 className="w-4 h-4 text-indigo-600" />
                Delivery Inspector: {selectedLog.id}
              </DialogTitle>
              <DialogDescription className="text-xs text-zinc-500">
                Detailed request payload and response headers for {selectedLog.webhookName}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-2 text-xs bg-zinc-50 p-3 rounded-sm border border-zinc-200">
                <div>
                  <span className="text-zinc-500">Target URL:</span>
                  <div className="font-mono text-[11px] text-zinc-900 truncate">{selectedLog.targetUrl}</div>
                </div>
                <div>
                  <span className="text-zinc-500">Event:</span>
                  <div className="font-mono font-bold text-zinc-900">{selectedLog.eventName}</div>
                </div>
                <div>
                  <span className="text-zinc-500">HTTP Status:</span>
                  <div className="font-bold text-emerald-600">{selectedLog.status} {selectedLog.statusText}</div>
                </div>
                <div>
                  <span className="text-zinc-500">Duration:</span>
                  <div className="font-mono text-zinc-800">{selectedLog.durationMs} ms</div>
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="text-xs font-bold text-zinc-800">Sent Request Payload</span>
                <pre className="text-xs font-mono bg-zinc-950 text-emerald-400 p-3 rounded-sm border border-zinc-800 overflow-x-auto">
                  {JSON.stringify(selectedLog.payload, null, 2)}
                </pre>
              </div>

              <div className="space-y-1.5">
                <span className="text-xs font-bold text-zinc-800">Received Response Body</span>
                <pre className="text-xs font-mono bg-zinc-950 text-zinc-200 p-3 rounded-sm border border-zinc-800 overflow-x-auto">
                  {JSON.stringify(selectedLog.response, null, 2)}
                </pre>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
