import { Recording, RecordingAudio } from "@/types";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtDateTime } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import { toast } from "sonner";

export default function Recordings() {
  const [rows, setRows] = useState<Recording[]>([]);
  const [audio, setAudio] = useState<RecordingAudio | null>(null);
  const nav = useNavigate();
  useEffect(() => { api.get("/recordings").then((r) => setRows(r.data)).catch(() => {}); }, []);

  const play = async (rid: string | number) => {
    try {
      const r = await api.get(`/recordings/${rid}/signed-url`);
      setAudio({ id: rid, url: r.data.url, filename: r.data.filename });
      toast.success("Signed URL generated (expires in 60s)");
    } catch { toast.error("Failed to generate URL"); }
  };

  const columns = [
    { key: "filename", label: "File", render: (r: Recording) => <span className="font-mono-stat text-xs">{r.filename}</span> },
    { key: "duration", label: "Duration", render: (r: Recording) => <span className="font-mono-stat text-xs">{Math.floor(r.duration/60)}:{String(r.duration%60).padStart(2,"0")}</span> },
    { key: "size", label: "Size", render: (r: Recording) => <span className="font-mono-stat text-xs">{(r.size/1024/1024).toFixed(1)} MB</span> },
    { key: "createdAt", label: "Captured", render: (r: Recording) => <span className="font-mono-stat text-xs">{fmtDateTime(r.createdAt)}</span> },
    { key: "actions", label: "", render: (r: Recording) => (
      <div className="flex gap-2">
        <button data-testid={`play-rec-${r.id}`} onClick={(e) => { e.stopPropagation(); play(r.id); }} className="px-2.5 py-1 bg-zinc-950 text-white text-xs rounded-sm hover:bg-zinc-800">Play</button>
        <button onClick={(e) => { e.stopPropagation(); nav(`/conversations/${r.conversationId}`); }} className="px-2.5 py-1 border border-zinc-300 text-xs rounded-sm hover:bg-zinc-50">Open</button>
      </div>
    )},
  ];

  return (
    <div data-testid="recordings-page">
      <PageHeader title="Recordings library" subtitle="Secure S3-signed playback for all voice interactions" />
      {audio && (
        <div className="bg-white border border-zinc-200 p-4 mb-4 flex items-center gap-3" data-testid="active-player">
          <div className="flex-1">
            <div className="label-tiny">NOW PLAYING</div>
            <div className="font-mono-stat text-sm">{audio.filename}</div>
          </div>
          <audio data-testid="recordings-audio" controls autoPlay src={audio.url} className="flex-1" />
        </div>
      )}
      <DataTable testId="recordings-table" columns={columns} rows={rows} searchKeys={["filename"]} />
    </div>
  );
}
