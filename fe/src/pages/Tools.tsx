import { Wrench, Phone, Mic, Globe, Mail, Calendar, MessageCircle, Database, Zap, Plug } from "lucide-react";
import PageHeader from "@/components/PageHeader";

interface ToolCard {
  name: string;
  description: string;
  icon: typeof Wrench;
  status: "available" | "coming_soon";
  category: string;
}

const tools: ToolCard[] = [
  {
    name: "LiveKit Phone Bridge",
    description: "Connect SIP trunks to LiveKit rooms for real-time voice AI calls.",
    icon: Phone,
    status: "available",
    category: "Voice",
  },
  {
    name: "Speech-to-Text",
    description: "Real-time transcription powered by Deepgram for live call captions.",
    icon: Mic,
    status: "available",
    category: "Voice",
  },
  {
    name: "Text-to-Speech",
    description: "Natural voice synthesis with multiple languages and voice options.",
    icon: Zap,
    status: "available",
    category: "Voice",
  },
  {
    name: "Web Search",
    description: "Let agents look up real-time information from the web during calls.",
    icon: Globe,
    status: "coming_soon",
    category: "Integrations",
  },
  {
    name: "Email Gateway",
    description: "Send and receive emails through your agent workflow automatically.",
    icon: Mail,
    status: "coming_soon",
    category: "Integrations",
  },
  {
    name: "Calendar Sync",
    description: "Book, reschedule, and manage appointments via Google or Outlook.",
    icon: Calendar,
    status: "coming_soon",
    category: "Integrations",
  },
  {
    name: "WhatsApp Business",
    description: "Connect WhatsApp Business API for messaging-based agent interactions.",
    icon: MessageCircle,
    status: "coming_soon",
    category: "Integrations",
  },
  {
    name: "Knowledge Base RAG",
    description: "Upload documents and let agents retrieve answers from your custom KB.",
    icon: Database,
    status: "available",
    category: "AI",
  },
  {
    name: "Function Calling",
    description: "Define custom tools/functions your agent can invoke during conversations.",
    icon: Plug,
    status: "coming_soon",
    category: "AI",
  },
];

const categories = ["All", "Voice", "Integrations", "AI"];

export default function Tools() {
  return (
    <div data-testid="tools-page">
      <PageHeader
        title="Tools"
        subtitle="Integrations and capabilities available for your voice agents"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {tools.map((tool) => {
          const Icon = tool.icon;
          return (
            <div
              key={tool.name}
              className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs space-y-3 flex flex-col"
            >
              <div className="flex items-start justify-between">
                <div className="w-9 h-9 rounded-md bg-zinc-900 text-white flex items-center justify-center">
                  <Icon className="w-4 h-4" />
                </div>
                {tool.status === "coming_soon" ? (
                  <span className="text-[9px] font-bold bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded-xs uppercase tracking-wide">
                    Soon
                  </span>
                ) : (
                  <span className="text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded-xs uppercase tracking-wide">
                    Active
                  </span>
                )}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-950">{tool.name}</h3>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{tool.description}</p>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-zinc-100 mt-auto">
                <span className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider">{tool.category}</span>
                <button
                  disabled={tool.status === "coming_soon"}
                  className="text-xs font-medium text-zinc-700 hover:text-zinc-950 disabled:text-zinc-300 disabled:cursor-not-allowed transition-colors"
                >
                  {tool.status === "coming_soon" ? "Notify Me" : "Configure"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
