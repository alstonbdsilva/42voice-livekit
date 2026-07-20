import { Conversation, Transcript, Recording } from "@/types";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, fmtDateTime, fmtCurrency } from "@/services/api";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { ArrowLeft, Download } from "lucide-react";

export default function ConversationDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [c, setC] = useState<Conversation | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);

  useEffect(() => {
    api.get(`/conversations/${id}`).then((r) => setC(r.data)).catch(() => {});
    api.get(`/transcripts/${id}`).then((r) => setTranscript(r.data)).catch(() => {});
    api.get(`/recordings`).then((r) => setRecordings(r.data.filter((x: Recording) => x.conversationId.toString() === id?.toString()))).catch(() => {});
  }, [id]);

  const playRecording = async (rid: string | number) => {
    try {
      const r = await api.get(`/recordings/${rid}/signed-url`);
      setSignedUrl(r.data.url);
    } catch (err) {
      console.error("Failed to load signed recording URL", err);
    }
  };

  if (!c) return <div className="label-tiny">Loading…</div>;

  return (
    <div data-testid="conversation-detail">
      <button onClick={() => nav(-1)} className="label-tiny text-zinc-500 hover:text-zinc-950 mb-2 flex items-center gap-1">
        <ArrowLeft className="w-3 h-3" /> BACK
      </button>
      <PageHeader
        title={`Conversation with ${c.customerName}`}
        subtitle={`${c.agentName} • ${c.channel} • ${fmtDateTime(c.startedAt)} • ${fmtCurrency(c.cost)}`}
        actions={<div className="flex items-center gap-2"><StatusBadge value={c.sentiment} /><StatusBadge value={c.outcome} /></div>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {/* Recording */}
          {recordings.length > 0 && (
            <div className="bg-white border border-zinc-200 p-5" data-testid="recording-card">
              <div className="label-tiny mb-3">RECORDING</div>
              {recordings.map((r) => (
                <div key={r.id} className="flex items-center gap-3 mb-3">
                  <div className="flex-1">
                    <div className="text-sm font-mono-stat">{r.filename}</div>
                    <div className="text-xs text-zinc-500">{Math.floor(r.duration/60)}:{String(r.duration%60).padStart(2,"0")} • secure playback</div>
                  </div>
                  <button data-testid={`play-${r.id}`} onClick={() => playRecording(r.id)} className="px-3 py-1.5 bg-zinc-950 text-white text-xs rounded-sm hover:bg-zinc-800">
                    Generate signed URL
                  </button>
                </div>
              ))}
              {signedUrl && (
                <audio data-testid="audio-player" controls src={signedUrl} className="w-full mt-2" />
              )}
            </div>
          )}

          {/* Transcript */}
          <div className="bg-white border border-zinc-200">
            <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
              <div className="label-tiny">TRANSCRIPT</div>
              {transcript && (
                <a
                  href={`data:text/plain;charset=utf-8,${encodeURIComponent(transcript.fullText)}`}
                  download={`transcript-${id}.txt`}
                  className="text-xs text-zinc-500 hover:text-zinc-950 flex items-center gap-1"
                  data-testid="download-transcript"
                >
                  <Download className="w-3 h-3" /> DOWNLOAD
                </a>
              )}
            </div>
            <div className="p-5 space-y-3">
              {transcript ? transcript.lines.map((l, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`label-tiny w-20 shrink-0 ${l.speaker === "agent" ? "text-zinc-950" : "text-zinc-500"}`}>
                    {l.speaker.toUpperCase()}
                  </div>
                  <div className="text-sm text-zinc-700">{l.text}</div>
                </div>
              )) : <div className="text-sm text-zinc-400">No transcript</div>}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="bg-white border border-zinc-200 p-5">
            <div className="label-tiny mb-3">AI SUMMARY</div>
            <p className="text-sm text-zinc-700 leading-relaxed">{c.summary}</p>
          </div>
          <div className="bg-white border border-zinc-200 p-5 space-y-3">
            <div>
              <div className="label-tiny">CUSTOMER INTENT</div>
              <div className="text-sm font-medium mt-1">{c.intent?.replace("_", " ")}</div>
            </div>
            <div>
              <div className="label-tiny">LEAD SCORE</div>
              <div className="font-mono-stat text-xl font-semibold mt-1">{c.leadScore}/100</div>
            </div>
            <div>
              <div className="label-tiny">SENTIMENT SCORE</div>
              <div className="font-mono-stat text-xl font-semibold mt-1">{c.sentimentScore}</div>
            </div>
            {(transcript?.actionItems?.length ?? 0) > 0 && (
              <div>
                <div className="label-tiny">ACTION ITEMS</div>
                <ul className="mt-2 text-sm space-y-1">
                  {transcript?.actionItems?.map((a: string, i: number) => <li key={i} className="flex gap-2"><span className="text-zinc-400">▸</span>{a}</li>)}
                </ul>
              </div>
            )}
            {c.humanHandoff && (
              <div>
                <div className="label-tiny text-rose-700">ESCALATION REASON</div>
                <div className="text-sm mt-1">{c.escalationReason}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
