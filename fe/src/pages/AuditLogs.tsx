import { AuditLog } from "@/types";
import React, { useEffect, useState } from "react";
import { api, fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";

export default function AuditLogs() {
  const [rows, setRows] = useState<AuditLog[]>([]);
  useEffect(() => { api.get("/audit-logs").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const columns = [
    { key: "createdAt", label: "When", render: (r: AuditLog) => <span className="font-mono-stat text-xs">{fmtDateTime(r.createdAt)}</span> },
    { key: "actorEmail", label: "Actor" },
    { key: "actorRole", label: "Role", render: (r: AuditLog) => <span className="text-[10px] uppercase font-mono-stat">{r.actorRole}</span> },
    { key: "action", label: "Action", render: (r: AuditLog) => <span className="font-mono-stat text-xs">{r.action}</span> },
    { key: "target", label: "Target", render: (r: AuditLog) => <span className="font-mono-stat text-xs text-zinc-500">{r.target}</span> },
  ];

  return (
    <div data-testid="audit-page">
      <PageHeader title="Audit logs" subtitle="System-wide trail of sensitive actions" />
      <DataTable testId="audit-table" columns={columns} rows={rows} searchKeys={["actorEmail", "action", "target"]} />
    </div>
  );
}
