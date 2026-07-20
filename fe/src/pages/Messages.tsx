import { Message } from "@/types";
import React, { useEffect, useState } from "react";
import { api, fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";

export default function Messages() {
  const [rows, setRows] = useState<Message[]>([]);
  useEffect(() => { api.get("/messages").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "createdAt", label: "When", render: (r: Message) => <span className="font-mono-stat text-xs">{fmtDateTime(r.createdAt)}</span> },
    { key: "from", label: "From", render: (r: Message) => <div className="font-medium text-sm">{r.from}</div> },
    { key: "channel", label: "Channel", render: (r: Message) => <span className="px-1.5 py-0.5 bg-zinc-100 text-[10px] font-mono-stat rounded-sm">{r.channel}</span> },
    { key: "preview", label: "Preview", render: (r: Message) => <span className="text-sm text-zinc-700 truncate inline-block max-w-md">{r.preview}</span> },
    { key: "unread", label: "Status", render: (r: Message) => r.unread
      ? <span className="px-2 py-0.5 bg-zinc-950 text-white text-[10px] rounded-sm">UNREAD</span>
      : <span className="text-xs text-zinc-400">read</span> },
  ];

  return (
    <div data-testid="messages-page">
      <PageHeader title="Messages inbox" subtitle="Unified WhatsApp, SMS, Web chat & email queue" />
      <DataTable testId="messages-table" columns={columns} rows={rows} searchKeys={["from", "preview"]}
        filters={[{ key: "channel", label: "Channel", options: [
          { value: "whatsapp", label: "WhatsApp" }, { value: "sms", label: "SMS" },
          { value: "web_chat", label: "Web chat" }, { value: "email", label: "Email" }
        ]}]}
      />
    </div>
  );
}
