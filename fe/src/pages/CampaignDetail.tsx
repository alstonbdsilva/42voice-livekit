import React, { useState, useMemo, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  Bot,
  Search,
  Plus,
  Upload,
  Trash2,
  Phone,
  Mail,
  Building,
  User,
  Play,
  Pause,
  CheckCircle2,
  FileText,
  Copy,
  AlertCircle,
  Users,
  Clock,
  Sparkles,
  PhoneCall
} from "lucide-react";
import { AppModal } from "@/components/AppModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCampaignStore } from "@/store/campaignStore";

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Zustand Store
  const campaigns = useCampaignStore((state) => state.campaigns);
  const leads = useCampaignStore((state) => state.leads);
  const updateCampaignStatus = useCampaignStore((state) => state.updateCampaignStatus);
  const addLead = useCampaignStore((state) => state.addLead);
  const addBulkLeads = useCampaignStore((state) => state.addBulkLeads);
  const deleteLead = useCampaignStore((state) => state.deleteLead);
  const triggerCallLead = useCampaignStore((state) => state.triggerCallLead);
  const triggerCallAllPending = useCampaignStore((state) => state.triggerCallAllPending);

  // Find target campaign
  const campaign = useMemo(() => {
    return campaigns.find((c) => c.id === id);
  }, [campaigns, id]);

  // Lead search & filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modal states
  const [isAddLeadOpen, setIsAddLeadOpen] = useState(false);
  const [isBulkUploadOpen, setIsBulkUploadOpen] = useState(false);

  // Add Single Lead Form State
  const [leadName, setLeadName] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadCompany, setLeadCompany] = useState("");

  // Bulk Upload State
  const [uploadMode, setUploadMode] = useState<"file" | "paste">("file");
  const [rawCsvText, setRawCsvText] = useState("");
  const [parsedPreview, setParsedPreview] = useState<{ name: string; phone: string; email?: string; company?: string }[]>([]);
  const [fileName, setFileName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Campaign Leads for this specific campaign
  const campaignLeads = useMemo(() => {
    if (!id) return [];
    return leads.filter((l) => l.campaignId === id);
  }, [leads, id]);

  // Filtered Leads based on search query and status filter
  const filteredLeads = useMemo(() => {
    return campaignLeads.filter((l) => {
      const matchesSearch =
        l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        l.phone.includes(searchQuery) ||
        (l.email && l.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (l.company && l.company.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus = statusFilter === "all" || l.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [campaignLeads, searchQuery, statusFilter]);

  if (!campaign) {
    return (
      <div className="space-y-6 py-12 text-center" data-testid="campaign-not-found">
        <AlertCircle className="w-12 h-12 text-zinc-400 mx-auto" />
        <h2 className="text-lg font-bold text-zinc-800">Campaign Not Found</h2>
        <p className="text-xs text-zinc-500">The campaign you are looking for does not exist or has been removed.</p>
        <Button onClick={() => navigate("/campaigns")} variant="outline" size="sm">
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Campaigns
        </Button>
      </div>
    );
  }

  // Handle single lead submit
  const handleAddLeadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadName.trim() || !leadPhone.trim()) {
      toast.error("Please provide both Lead Name and Phone Number.");
      return;
    }

    addLead({
      campaignId: campaign.id,
      campaignName: campaign.name,
      name: leadName.trim(),
      phone: leadPhone.trim(),
      email: leadEmail.trim() || undefined,
      company: leadCompany.trim() || undefined,
      status: "pending",
      attempts: 0,
    });

    toast.success(`Lead '${leadName.trim()}' added successfully!`);
    setLeadName("");
    setLeadPhone("");
    setLeadEmail("");
    setLeadCompany("");
    setIsAddLeadOpen(false);
  };

  // Helper to parse CSV string into items array
  const parseCsvLines = (text: string) => {
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (lines.length === 0) return [];

    const items: { name: string; phone: string; email?: string; company?: string }[] = [];

    // Check if first line is a header
    const firstLineLower = lines[0].toLowerCase();
    const hasHeader =
      firstLineLower.includes("name") ||
      firstLineLower.includes("phone") ||
      firstLineLower.includes("email") ||
      firstLineLower.includes("company");

    const dataLines = hasHeader ? lines.slice(1) : lines;

    dataLines.forEach((line) => {
      // Split by comma or tab
      const parts = line.split(/[,;\t]/).map((p) => p.trim().replace(/^["']|["']$/g, ""));
      if (parts.length >= 2 && parts[0] && parts[1]) {
        items.push({
          name: parts[0],
          phone: parts[1],
          email: parts[2] || undefined,
          company: parts[3] || undefined,
        });
      } else if (parts.length === 1 && parts[0]) {
        // Single line fallback format
        items.push({
          name: parts[0],
          phone: "+1 (555) 000-0000",
        });
      }
    });

    return items;
  };

  // Handle file select for bulk upload
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const parsed = parseCsvLines(content);
      setParsedPreview(parsed);
    };
    reader.readAsText(file);
  };

  // Handle raw text paste change
  const handleRawTextChange = (text: string) => {
    setRawCsvText(text);
    const parsed = parseCsvLines(text);
    setParsedPreview(parsed);
  };

  // Submit bulk leads
  const handleBulkUploadSubmit = () => {
    if (parsedPreview.length === 0) {
      toast.error("No valid lead entries found to import.");
      return;
    }

    addBulkLeads(campaign.id, campaign.name, parsedPreview);
    toast.success(`Successfully imported ${parsedPreview.length} leads to ${campaign.name}!`);

    // Reset Bulk Upload modal state
    setRawCsvText("");
    setParsedPreview([]);
    setFileName("");
    setIsBulkUploadOpen(false);
  };

  // Copy CSV template string
  const handleCopyTemplate = () => {
    const template = `Name,Phone,Email,Company\nJohn Doe,+1 (555) 019-2831,john@acme.com,Acme Corp\nSarah Connor,+1 (555) 024-9182,sarah@cyber.io,Cyberdyne`;
    navigator.clipboard.writeText(template);
    toast.success("CSV Template copied to clipboard!");
  };

  const percentComplete =
    campaign.totalLeads > 0
      ? Math.min(100, Math.round((campaign.completedLeads / campaign.totalLeads) * 100))
      : 0;

  return (
    <div className="space-y-6" data-testid="campaign-detail-page">
      {/* Back button */}
      <div>
        <button
          onClick={() => navigate("/campaigns")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-950 transition-colors mb-2"
          data-testid="back-to-campaigns-btn"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Campaigns</span>
        </button>
      </div>

      {/* Page Header with Campaign Controls */}
      <div className="bg-white border border-zinc-200 rounded-sm p-6 space-y-4 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-zinc-950">{campaign.name}</h1>
              <span
                className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider ${
                  campaign.channel === "voice"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                    : campaign.channel === "sms"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-purple-50 text-purple-700 border border-purple-200"
                }`}
              >
                {campaign.channel}
              </span>
              <span
                className={`px-2.5 py-0.5 text-[10px] font-bold rounded-full uppercase tracking-wide border flex items-center gap-1.5 ${
                  campaign.status === "active"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : campaign.status === "paused"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : campaign.status === "completed"
                    ? "bg-blue-50 text-blue-700 border-blue-200"
                    : "bg-zinc-100 text-zinc-700 border-zinc-200"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    campaign.status === "active"
                      ? "bg-emerald-500 animate-pulse"
                      : campaign.status === "paused"
                      ? "bg-amber-500"
                      : "bg-blue-500"
                  }`}
                />
                {campaign.status}
              </span>
            </div>
            <p className="text-xs text-zinc-500">{campaign.description}</p>
          </div>

          {/* Quick Actions / Status Switches */}
          <div className="flex items-center gap-2">
            {campaign.status === "active" ? (
              <button
                onClick={() => {
                  updateCampaignStatus(campaign.id, "paused");
                  toast.info(`Campaign '${campaign.name}' paused`);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 text-xs font-semibold rounded-sm transition-colors"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Pause Campaign</span>
              </button>
            ) : (
              <button
                onClick={() => {
                  updateCampaignStatus(campaign.id, "active");
                  toast.success(`Campaign '${campaign.name}' activated!`);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-semibold rounded-sm transition-colors shadow-xs"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Start / Resume</span>
              </button>
            )}

            {campaign.status !== "completed" && (
              <button
                onClick={() => {
                  updateCampaignStatus(campaign.id, "completed");
                  toast.success(`Marked '${campaign.name}' as completed`);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-100 text-zinc-700 border border-zinc-200 hover:bg-zinc-200 text-xs font-semibold rounded-sm transition-colors"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-zinc-500" />
                <span>Mark Completed</span>
              </button>
            )}
          </div>
        </div>

        {/* Campaign Info Cards Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-3 border-t border-zinc-100 text-xs">
          <div>
            <span className="text-zinc-400 block text-[10px] uppercase tracking-wider font-semibold">Assigned Agent</span>
            <div className="flex items-center gap-1.5 mt-0.5 font-semibold text-zinc-800">
              <Bot className="w-3.5 h-3.5 text-zinc-500" />
              <span>{campaign.agent}</span>
            </div>
          </div>

          <div>
            <span className="text-zinc-400 block text-[10px] uppercase tracking-wider font-semibold">Caller ID</span>
            <div className="flex items-center gap-1.5 mt-0.5 font-mono text-zinc-800 font-semibold">
              <PhoneCall className="w-3.5 h-3.5 text-zinc-500" />
              <span>{campaign.callerId}</span>
            </div>
          </div>

          <div>
            <span className="text-zinc-400 block text-[10px] uppercase tracking-wider font-semibold">Schedule</span>
            <div className="flex items-center gap-1.5 mt-0.5 text-zinc-800 font-semibold truncate">
              <Clock className="w-3.5 h-3.5 text-zinc-500" />
              <span className="truncate">{campaign.schedule}</span>
            </div>
          </div>

          <div>
            <span className="text-zinc-400 block text-[10px] uppercase tracking-wider font-semibold">Concurrency & Retries</span>
            <div className="mt-0.5 text-zinc-800 font-semibold">
              <span>{campaign.concurrencyLimit || 10} concurrent</span> • <span>Max {campaign.maxRetries || 2} retries</span>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-zinc-200 p-4 rounded-sm space-y-2">
          <div className="flex justify-between items-center text-xs text-zinc-500 font-semibold">
            <span>TOTAL LEADS</span>
            <Users className="w-4 h-4 text-zinc-400" />
          </div>
          <div className="text-2xl font-bold font-mono-stat text-zinc-900">{campaign.totalLeads}</div>
          <div className="text-[11px] text-zinc-400">Total prospects in queue</div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm space-y-2">
          <div className="flex justify-between items-center text-xs text-zinc-500 font-semibold">
            <span>COMPLETED LEADS</span>
            <CheckCircle2 className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold font-mono-stat text-zinc-900">{campaign.completedLeads}</div>
          <div className="w-full bg-zinc-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${percentComplete}%` }}
            />
          </div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm space-y-2">
          <div className="flex justify-between items-center text-xs text-zinc-500 font-semibold">
            <span>ANSWER RATE</span>
            <Phone className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold font-mono-stat text-zinc-900">
            {campaign.answerRate > 0 ? `${campaign.answerRate}%` : "0%"}
          </div>
          <div className="text-[11px] text-emerald-600 font-semibold">Calls answered by recipient</div>
        </div>

        <div className="bg-white border border-zinc-200 p-4 rounded-sm space-y-2">
          <div className="flex justify-between items-center text-xs text-zinc-500 font-semibold">
            <span>CONVERSION RATE</span>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold font-mono-stat text-emerald-700">
            {campaign.conversionRate > 0 ? `${campaign.conversionRate}%` : "0%"}
          </div>
          <div className="text-[11px] text-zinc-400">Successful goal completions</div>
        </div>
      </div>

      {/* LEADS SECTION */}
      <div className="space-y-4">
        {/* Leads Table Controls Bar */}
        <div className="bg-white border border-zinc-200 p-4 rounded-sm flex flex-col md:flex-row justify-between items-stretch md:items-center gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            {/* Search Input */}
            <div className="relative w-full max-w-sm">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search leads by name, phone, email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white transition-colors"
                data-testid="search-leads-input"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-zinc-50 border border-zinc-200 rounded-sm px-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
              data-testid="status-filter-select"
            >
              <option value="all">All Lead Statuses</option>
              <option value="pending">Pending</option>
              <option value="calling">Calling</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="voicemail">Voicemail</option>
              <option value="opted_out">Opted Out</option>
            </select>
          </div>          {/* Action Buttons: Add Lead, Bulk Upload & Trigger Calls */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => {
                const count = triggerCallAllPending(campaign.id);
                if (count > 0) {
                  toast.success(`Triggered AI outbound calls for ${count} leads!`);
                } else {
                  toast.info("No pending leads available to call.");
                }
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-sm transition-colors shadow-xs"
              data-testid="trigger-batch-calls-btn"
              title="Trigger AI calls for all pending leads in queue"
            >
              <PhoneCall className="w-3.5 h-3.5" />
              <span>Trigger Calls</span>
            </button>

            <button
              onClick={() => setIsBulkUploadOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-300 text-xs font-semibold rounded-sm transition-colors"
              data-testid="bulk-upload-btn"
            >
              <Upload className="w-3.5 h-3.5 text-zinc-600" />
              <span>Bulk Upload</span>
            </button>

            <button
              onClick={() => setIsAddLeadOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm transition-colors shadow-xs"
              data-testid="add-lead-btn"
            >
              <Plus className="w-4 h-4" />
              <span>Add Lead</span>
            </button>
          </div>
        </div>

        {/* Leads Table */}
        <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
          <div className="px-5 py-3 border-b border-zinc-200 flex justify-between items-center bg-zinc-50/50">
            <h3 className="text-xs font-bold text-zinc-800 uppercase tracking-wider">Campaign Leads</h3>
            <span className="text-xs font-mono-stat text-zinc-500">
              Showing <strong>{filteredLeads.length}</strong> of <strong>{campaignLeads.length}</strong> leads
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                  <th className="px-5 py-3 text-left">Lead Name</th>
                  <th className="px-5 py-3 text-left">Phone Number</th>
                  <th className="px-5 py-3 text-left">Email / Company</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-center">Attempts</th>
                  <th className="px-5 py-3 text-left">Last Called</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-zinc-200">
                {filteredLeads.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-zinc-400 space-y-2">
                      <Users className="w-8 h-8 text-zinc-300 mx-auto" />
                      <p className="text-xs font-semibold text-zinc-600">No leads found in this campaign.</p>
                      <p className="text-[11px] text-zinc-400">Add a lead or upload a CSV to populate your queue.</p>
                      <div className="pt-2 flex justify-center gap-2">
                        <Button size="sm" variant="outline" onClick={() => setIsAddLeadOpen(true)}>
                          <Plus className="w-3.5 h-3.5 mr-1" /> Add Lead
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setIsBulkUploadOpen(true)}>
                          <Upload className="w-3.5 h-3.5 mr-1" /> Bulk Upload CSV
                        </Button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-zinc-50/70 transition-colors">
                      {/* Name */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-zinc-100 text-zinc-700 flex items-center justify-center text-xs font-bold border border-zinc-200">
                            {lead.name.charAt(0).toUpperCase()}
                          </div>
                          <span className="font-semibold text-zinc-900">{lead.name}</span>
                        </div>
                      </td>

                      {/* Phone */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span className="font-mono-stat text-xs font-semibold text-zinc-800">{lead.phone}</span>
                      </td>

                      {/* Email / Company */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-xs text-zinc-600">
                        <div>{lead.email || "—"}</div>
                        {lead.company && (
                          <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                            <Building className="w-3 h-3" />
                            <span>{lead.company}</span>
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wide border ${
                            lead.status === "completed"
                              ? "bg-blue-50 text-blue-700 border-blue-200"
                              : lead.status === "calling"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : lead.status === "failed"
                              ? "bg-red-50 text-red-700 border-red-200"
                              : lead.status === "voicemail"
                              ? "bg-amber-50 text-amber-700 border-amber-200"
                              : lead.status === "opted_out"
                              ? "bg-purple-50 text-purple-700 border-purple-200"
                              : "bg-zinc-100 text-zinc-600 border-zinc-200"
                          }`}
                        >
                          {lead.status}
                        </span>
                      </td>

                      {/* Attempts */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-center font-mono-stat text-xs font-semibold text-zinc-800">
                        {lead.attempts}
                      </td>

                      {/* Last Called */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-xs text-zinc-500 font-mono-stat">
                        {lead.lastCalled || "Not called yet"}
                      </td>

                      {/* Action */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => {
                              triggerCallLead(lead.id);
                              toast.success(`Triggered call to ${lead.name} (${lead.phone})`);
                            }}
                            className="flex items-center gap-1 px-2 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 text-xs font-semibold rounded-sm transition-colors"
                            title={`Trigger Call to ${lead.name}`}
                            data-testid={`trigger-call-lead-${lead.id}`}
                          >
                            <PhoneCall className="w-3 h-3 text-emerald-600" />
                            <span>Call</span>
                          </button>
                          <button
                            onClick={() => {
                              deleteLead(lead.id);
                              toast.success(`Removed lead '${lead.name}'`);
                            }}
                            className="p-1 text-zinc-400 hover:text-red-600 hover:bg-red-50 rounded-sm transition-colors"
                            title="Delete Lead"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ADD SINGLE LEAD MODAL */}
      <AppModal
        open={isAddLeadOpen}
        onClose={() => setIsAddLeadOpen(false)}
        title="Add Single Lead"
        description={`Add a new lead manually to campaign '${campaign.name}'`}
        showFooter={false}
      >
        <form onSubmit={handleAddLeadSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1">
              <User className="w-3.5 h-3.5" /> Lead Full Name <span className="text-red-500">*</span>
            </Label>
            <Input
              type="text"
              placeholder="e.g. John Doe"
              value={leadName}
              onChange={(e) => setLeadName(e.target.value)}
              required
              className="text-xs"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1">
              <Phone className="w-3.5 h-3.5" /> Phone Number <span className="text-red-500">*</span>
            </Label>
            <Input
              type="text"
              placeholder="e.g. +1 (555) 234-5678"
              value={leadPhone}
              onChange={(e) => setLeadPhone(e.target.value)}
              required
              className="text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1">
                <Mail className="w-3.5 h-3.5" /> Email (Optional)
              </Label>
              <Input
                type="email"
                placeholder="john@example.com"
                value={leadEmail}
                onChange={(e) => setLeadEmail(e.target.value)}
                className="text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-zinc-700 flex items-center gap-1">
                <Building className="w-3.5 h-3.5" /> Company (Optional)
              </Label>
              <Input
                type="text"
                placeholder="Acme Corp"
                value={leadCompany}
                onChange={(e) => setLeadCompany(e.target.value)}
                className="text-xs"
              />
            </div>
          </div>

          <div className="pt-3 border-t border-zinc-100 flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsAddLeadOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" className="bg-zinc-950 text-white hover:bg-zinc-800">
              <Plus className="w-3.5 h-3.5 mr-1" /> Add Lead
            </Button>
          </div>
        </form>
      </AppModal>

      {/* BULK UPLOAD LEADS MODAL */}
      <AppModal
        open={isBulkUploadOpen}
        onClose={() => setIsBulkUploadOpen(false)}
        title="Bulk Upload Leads"
        description={`Import multiple lead contacts to '${campaign.name}' using CSV or raw text.`}
        maxWidth="sm:max-w-[650px]"
        showFooter={false}
      >
        <div className="space-y-4 pt-1">
          {/* Mode Selector Tabs */}
          <div className="flex border-b border-zinc-200">
            <button
              onClick={() => setUploadMode("file")}
              className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                uploadMode === "file"
                  ? "border-zinc-950 text-zinc-950 font-bold"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload CSV File</span>
            </button>
            <button
              onClick={() => setUploadMode("paste")}
              className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
                uploadMode === "paste"
                  ? "border-zinc-950 text-zinc-950 font-bold"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Paste CSV / Text</span>
            </button>
          </div>

          {/* Template helper info */}
          <div className="bg-zinc-50 border border-zinc-200 p-3 rounded-sm text-xs flex justify-between items-center">
            <div>
              <span className="font-semibold text-zinc-800">Supported CSV Format:</span>
              <p className="text-[11px] font-mono text-zinc-500 mt-0.5">Name, Phone, Email, Company</p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={handleCopyTemplate} className="text-xs h-7">
              <Copy className="w-3 h-3 mr-1" /> Copy Format
            </Button>
          </div>

          {/* File Upload Option */}
          {uploadMode === "file" && (
            <div className="space-y-3">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-zinc-300 hover:border-zinc-500 bg-zinc-50/50 hover:bg-zinc-50 p-6 rounded-sm text-center cursor-pointer transition-colors space-y-2"
              >
                <Upload className="w-8 h-8 text-zinc-400 mx-auto" />
                <p className="text-xs font-semibold text-zinc-700">
                  {fileName ? `Selected: ${fileName}` : "Click to browse or drop your CSV file here"}
                </p>
                <p className="text-[10px] text-zinc-400">Accepts .csv, .txt files formatted with columns</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
            </div>
          )}

          {/* Paste Raw Text Option */}
          {uploadMode === "paste" && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-zinc-700">Paste Raw CSV Content:</Label>
              <textarea
                rows={5}
                placeholder={`Name, Phone, Email, Company\nJohn Doe, +1 (555) 019-2831, john@acme.com, Acme Corp\nJane Smith, +1 (555) 024-9182, jane@techflow.io, TechFlow`}
                value={rawCsvText}
                onChange={(e) => handleRawTextChange(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-3 font-mono text-xs focus:outline-none focus:border-zinc-950 focus:bg-white"
              />
            </div>
          )}

          {/* Parsed Preview Table */}
          {parsedPreview.length > 0 && (
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-zinc-800">
                  Parsed Leads Preview ({parsedPreview.length} entries detected)
                </span>
              </div>

              <div className="max-h-40 overflow-y-auto border border-zinc-200 rounded-sm text-xs">
                <table className="w-full text-left">
                  <thead className="bg-zinc-100 text-zinc-600 text-[10px] uppercase font-bold sticky top-0">
                    <tr>
                      <th className="p-2">Name</th>
                      <th className="p-2">Phone</th>
                      <th className="p-2">Email</th>
                      <th className="p-2">Company</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 font-mono text-[11px]">
                    {parsedPreview.map((item, idx) => (
                      <tr key={idx} className="hover:bg-zinc-50">
                        <td className="p-2 font-semibold text-zinc-900">{item.name}</td>
                        <td className="p-2 text-zinc-700">{item.phone}</td>
                        <td className="p-2 text-zinc-500">{item.email || "—"}</td>
                        <td className="p-2 text-zinc-500">{item.company || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Modal Footer Actions */}
          <div className="pt-3 border-t border-zinc-100 flex justify-between items-center">
            <span className="text-xs text-zinc-500">
              Ready to import <strong>{parsedPreview.length}</strong> leads
            </span>

            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsBulkUploadOpen(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={handleBulkUploadSubmit}
                disabled={parsedPreview.length === 0}
                className="bg-zinc-950 text-white hover:bg-zinc-800"
              >
                <Upload className="w-3.5 h-3.5 mr-1" /> Import {parsedPreview.length} Leads
              </Button>
            </div>
          </div>
        </div>
      </AppModal>
    </div>
  );
}
