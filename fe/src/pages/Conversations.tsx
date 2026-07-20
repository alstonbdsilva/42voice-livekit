import { Conversation } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtDateTime, fmtCurrency } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import StatusBadge from "@/components/StatusBadge";

export default function Conversations() {
  const [rows, setRows] = useState<Conversation[]>([]);
  const nav = useNavigate();
  useEffect(() => { api.get("/conversations").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "startedAt", label: "When", render: (r: Conversation) => <span className="font-mono-stat text-xs">{fmtDateTime(r.startedAt)}</span> },
    { key: "customerName", label: "Customer", render: (r: Conversation) => (
      <div>
        <div className="font-medium">{r.customerName}</div>
        <div className="text-xs text-zinc-500 font-mono-stat">{r.customerContact}</div>
      </div>
    )},
    { key: "agentName", label: "Agent", render: (r: Conversation) => <span className="text-xs">{r.agentName}</span> },
    { key: "channel", label: "Channel", render: (r: Conversation) => <span className="px-1.5 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">{r.channel}</span> },
    { key: "duration", label: "Duration", render: (r: Conversation) => <span className="font-mono-stat text-xs">{Math.floor((r.duration ?? 0) / 60)}:{String((r.duration ?? 0) % 60).padStart(2, "0")}</span> },
    { key: "cost", label: "Cost", render: (r: Conversation) => <span className="font-mono-stat text-xs">{fmtCurrency(r.cost)}</span> },
    { key: "sentiment", label: "Sentiment", render: (r: Conversation) => <StatusBadge value={r.sentiment} /> },
    { key: "outcome", label: "Outcome", render: (r: Conversation) => <StatusBadge value={r.outcome} /> },
  ];

  return (
    <div data-testid="conversations-page">
      <PageHeader title="Conversations" subtitle="Every voice & messaging interaction your AI handles" />
      <DataTable
        testId="conversations-table" columns={columns} rows={rows}
        searchKeys={["customerName", "customerContact", "summary", "agentName"]}
        filters={[
          { key: "channel", label: "Channel", options: [
            { value: "voice", label: "Voice" }, { value: "whatsapp", label: "WhatsApp" },
            { value: "sms", label: "SMS" }, { value: "web_chat", label: "Web chat" }, { value: "email", label: "Email" }
          ]},
          { key: "outcome", label: "Outcome", options: [
            { value: "resolved", label: "Resolved" }, { value: "booked_appointment", label: "Booked" },
            { value: "lead_captured", label: "Lead" }, { value: "escalated_to_human", label: "Escalated" },
            { value: "callback_scheduled", label: "Callback" }, { value: "abandoned", label: "Abandoned" }
          ]},
        ]}
        onRowClick={(r) => nav(`/conversations/${r.id}`)}
      />
    </div>
  );
}
