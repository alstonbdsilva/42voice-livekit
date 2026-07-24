import React, { useState, useMemo } from "react";
import { toast } from "sonner";
import { 
  PhoneCall, UploadCloud, Play, Pause, TrendingUp, Clock, CheckCircle2, 
  Trash2, UserPlus, FileSpreadsheet, Plus, Search, Database, Users, 
  HelpCircle, Sparkles, Filter, ChevronRight, X
} from "lucide-react";
import PageHeader from "@/components/PageHeader";

// Types
interface LeadItem {
  id: string;
  name: string;
  phone: string;
  campaign: string;
  status: "pending" | "completed" | "failed" | "voicemail" | "calling";
  attempts: number;
}

interface CampaignItem {
  id: string;
  name: string;
  agent: string;
  status: "running" | "paused" | "completed";
  totalLeads: number;
  completedLeads: number;
  callsMade: number;
}

// Initial Mock Data
const INITIAL_CAMPAIGNS: CampaignItem[] = [
  {
    id: "camp-1",
    name: "Q3 Cold Outreach Campaign",
    agent: "Sales Outreach Agent",
    status: "running",
    totalLeads: 250,
    completedLeads: 172,
    callsMade: 198,
  },
  {
    id: "camp-2",
    name: "Customer Feedback Surveys",
    agent: "Feedback Router",
    status: "paused",
    totalLeads: 500,
    completedLeads: 120,
    callsMade: 145,
  },
  {
    id: "camp-3",
    name: "Expired Membership Renewals",
    agent: "Renewal Specialist Agent",
    status: "completed",
    totalLeads: 85,
    completedLeads: 85,
    callsMade: 112,
  }
];

const INITIAL_LEADS: LeadItem[] = [
  { id: "lead-1", name: "David Miller", phone: "+1 (555) 019-2831", campaign: "Q3 Cold Outreach Campaign", status: "completed", attempts: 1 },
  { id: "lead-2", name: "Sarah Jenkins", phone: "+1 (555) 024-9182", campaign: "Q3 Cold Outreach Campaign", status: "calling", attempts: 2 },
  { id: "lead-3", name: "Michael Chang", phone: "+1 (555) 081-3921", campaign: "Customer Feedback Surveys", status: "pending", attempts: 0 },
  { id: "lead-4", name: "Elena Rostova", phone: "+1 (555) 074-1290", campaign: "Expired Membership Renewals", status: "completed", attempts: 1 },
  { id: "lead-5", name: "Marcus Thompson", phone: "+1 (555) 043-8891", campaign: "Customer Feedback Surveys", status: "failed", attempts: 3 },
  { id: "lead-6", name: "Amina Al-Mansoor", phone: "+1 (555) 092-4412", campaign: "Q3 Cold Outreach Campaign", status: "voicemail", attempts: 1 },
  { id: "lead-7", name: "Gregory Peck", phone: "+1 (555) 031-6677", campaign: "Q3 Cold Outreach Campaign", status: "pending", attempts: 0 }
];

export default function Outbound() {
  const [activeTab, setActiveTab] = useState<"overview" | "leads" | "upload">("overview");
  
  // State
  const [campaigns, setCampaigns] = useState<CampaignItem[]>(INITIAL_CAMPAIGNS);
  const [leads, setLeads] = useState<LeadItem[]>(INITIAL_LEADS);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCampaignFilter, setSelectedCampaignFilter] = useState("all");

  // Single Lead Form State
  const [singleName, setSingleName] = useState("");
  const [singlePhone, setSinglePhone] = useState("");
  const [singleCampaign, setSingleCampaign] = useState(INITIAL_CAMPAIGNS[0]?.name || "");

  // Quick Bulk Upload State
  const [bulkText, setBulkText] = useState("");
  const [bulkCampaign, setBulkCampaign] = useState(INITIAL_CAMPAIGNS[0]?.name || "");
  const [csvPreview, setCsvPreview] = useState<{ name: string; phone: string }[]>([]);

  // Toggle Campaign Status
  const toggleCampaign = (id: string) => {
    setCampaigns(prev => prev.map(c => {
      if (c.id === id) {
        const nextStatus: "running" | "paused" = c.status === "running" ? "paused" : "running";
        toast.success(`Campaign '${c.name}' has been ${nextStatus === "running" ? "resumed" : "paused"}`);
        return { ...c, status: nextStatus };
      }
      return c;
    }));
  };

  // Add Single Lead
  const handleAddSingleLead = (e: React.FormEvent) => {
    e.preventDefault();
    if (!singleName.trim() || !singlePhone.trim()) {
      return toast.error("Please fill in both name and phone number.");
    }

    const newLead: LeadItem = {
      id: `lead-${Date.now()}`,
      name: singleName.trim(),
      phone: singlePhone.trim(),
      campaign: singleCampaign,
      status: "pending",
      attempts: 0
    };

    setLeads(prev => [newLead, ...prev]);
    toast.success(`Lead '${newLead.name}' added to queue!`);

    // Reset Form
    setSingleName("");
    setSinglePhone("");
  };

  // Parse bulk paste text (Quick Upload)
  const handleParseText = () => {
    if (!bulkText.trim()) {
      return toast.error("Please paste CSV data or phone numbers list first.");
    }

    // Split lines, parse comma/semicolon/tab/space formats
    const lines = bulkText.split("\n");
    const parsed: { name: string; phone: string }[] = [];

    lines.forEach(line => {
      if (!line.trim()) return;
      
      let name = "";
      let phone = "";

      // Try split by comma
      if (line.includes(",")) {
        const parts = line.split(",");
        name = parts[0]?.trim() || "";
        phone = parts[1]?.trim() || "";
      } else {
        // Fallback: treat whole line as phone or name and phone
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 2) {
          name = parts.slice(0, parts.length - 1).join(" ");
          phone = parts[parts.length - 1];
        } else {
          phone = line.trim();
          name = `Lead - ${phone.slice(-4)}`;
        }
      }

      if (phone) {
        parsed.push({ name, phone });
      }
    });

    if (parsed.length === 0) {
      toast.error("Could not parse any valid name/phone pairs.");
    } else {
      setCsvPreview(parsed);
      toast.success(`Successfully parsed ${parsed.length} records! Review details below.`);
    }
  };

  // Import parsed bulk leads
  const handleImportBulk = () => {
    if (csvPreview.length === 0) return;

    const newLeads: LeadItem[] = csvPreview.map((item, idx) => ({
      id: `lead-bulk-${Date.now()}-${idx}`,
      name: item.name || `Lead ${idx + 1}`,
      phone: item.phone,
      campaign: bulkCampaign,
      status: "pending",
      attempts: 0
    }));

    setLeads(prev => [...newLeads, ...prev]);
    toast.success(`Imported ${newLeads.length} leads to '${bulkCampaign}'!`);
    
    // Clear Bulk fields
    setBulkText("");
    setCsvPreview([]);
    setActiveTab("leads");
  };

  // Delete individual lead
  const handleDeleteLead = (id: string, name: string) => {
    setLeads(prev => prev.filter(l => l.id !== id));
    toast.success(`Deleted lead '${name}'`);
  };

  // Statistics Computations
  const totalCalls = useMemo(() => campaigns.reduce((acc, c) => acc + c.callsMade, 0), [campaigns]);
  const activeCampaignsCount = useMemo(() => campaigns.filter(c => c.status === "running").length, [campaigns]);
  const totalLeadsCount = useMemo(() => leads.length, [leads]);

  // Filter & Search Leads list
  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      const matchesSearch = l.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                            l.phone.includes(searchQuery);
      const matchesCampaign = selectedCampaignFilter === "all" || l.campaign === selectedCampaignFilter;
      return matchesSearch && matchesCampaign;
    });
  }, [leads, searchQuery, selectedCampaignFilter]);

  return (
    <div className="space-y-6" data-testid="outbound-page">
      <PageHeader 
        title="Outbound Dialer" 
        subtitle="Manage automated voice campaigns, upload lead dial queues, and review agent dialer logs"
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("upload")}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 text-sm font-semibold rounded-sm transition-colors"
            >
              <UploadCloud className="w-4 h-4 text-zinc-500" />
              <span>Bulk Upload</span>
            </button>
            <button
              onClick={() => {
                setActiveTab("upload");
                toast.info("Scroll down to the 'Single Lead' form to add one manual lead.");
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-sm font-semibold rounded-sm transition-colors shadow-sm"
            >
              <UserPlus className="w-4 h-4" />
              <span>Add Lead</span>
            </button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("overview")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "overview" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Campaigns Overview
        </button>
        <button
          onClick={() => setActiveTab("leads")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "leads" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Lead Directory ({leads.length})
        </button>
        <button
          onClick={() => setActiveTab("upload")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "upload" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Add Leads / Quick Upload
        </button>
      </div>

      {/* TAB 1: OVERVIEW & DASHBOARD */}
      {activeTab === "overview" && (
        <div className="space-y-6 animate-in fade-in duration-150">
          {/* Quick Statistics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Outbound Dials</p>
                  <h3 className="text-2xl font-bold font-display text-zinc-950 mt-1">{totalCalls}</h3>
                </div>
                <div className="p-2 bg-zinc-950 text-white rounded-sm">
                  <PhoneCall className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2 text-xs text-zinc-500 flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                <span className="font-semibold text-emerald-600">+12.4%</span>
                <span>vs last week</span>
              </div>
            </div>

            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Contact Answer Rate</p>
                  <h3 className="text-2xl font-bold font-display text-zinc-950 mt-1">68.4%</h3>
                </div>
                <div className="p-2 bg-emerald-50 text-emerald-600 rounded-sm">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2 text-xs text-zinc-500 flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Industry Standard: 45%</span>
              </div>
            </div>

            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Avg AI Call Duration</p>
                  <h3 className="text-2xl font-bold font-display text-zinc-950 mt-1">2m 14s</h3>
                </div>
                <div className="p-2 bg-indigo-50 text-indigo-600 rounded-sm">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2 text-xs text-zinc-500 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                <span>Extended conversations active</span>
              </div>
            </div>

            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Active Campaigns</p>
                  <h3 className="text-2xl font-bold font-display text-zinc-950 mt-1">{activeCampaignsCount} / {campaigns.length}</h3>
                </div>
                <div className="p-2 bg-amber-50 text-amber-600 rounded-sm">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2 text-xs text-zinc-500 flex items-center gap-1">
                <span>{totalLeadsCount} active queue records</span>
              </div>
            </div>
          </div>

          {/* Active Campaigns Management */}
          <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
            <div className="px-5 py-3.5 border-b border-zinc-200 flex justify-between items-center bg-zinc-50/50">
              <h4 className="font-bold text-sm text-zinc-800">Campaign Dialing Lists</h4>
              <span className="text-xs text-zinc-500 font-medium">Automatic Retry Queue Running</span>
            </div>
            
            <div className="divide-y divide-zinc-200">
              {campaigns.map((camp) => {
                const percent = Math.round((camp.completedLeads / camp.totalLeads) * 100);
                return (
                  <div key={camp.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-6 hover:bg-zinc-50/30 transition-colors">
                    <div className="space-y-1.5 md:max-w-md w-full">
                      <div className="flex items-center gap-2">
                        <h5 className="font-bold text-sm text-zinc-950">{camp.name}</h5>
                        <span className={`px-2 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wide border ${
                          camp.status === "running"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : camp.status === "paused"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-zinc-100 text-zinc-600 border-zinc-200"
                        }`}>
                          {camp.status}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-500">Connected Agent: <strong className="text-zinc-800 font-semibold">{camp.agent}</strong></p>
                    </div>

                    {/* Progress bar */}
                    <div className="flex-1 max-w-xs space-y-1">
                      <div className="flex justify-between text-xs font-semibold text-zinc-600">
                        <span>Dial Completion</span>
                        <span>{percent}% ({camp.completedLeads}/{camp.totalLeads} leads)</span>
                      </div>
                      <div className="w-full h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-500 ${
                            camp.status === "running" ? "bg-zinc-950" : "bg-zinc-400"
                          }`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>

                    {/* Quick Info */}
                    <div className="flex items-center gap-6">
                      <div className="text-left md:text-right">
                        <span className="block text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Outbound Dials</span>
                        <span className="text-sm font-bold text-zinc-900 font-mono-stat">{camp.callsMade} calls</span>
                      </div>
                      
                      {/* Controller Buttons */}
                      <div>
                        {camp.status === "completed" ? (
                          <span className="text-xs text-zinc-400 italic font-medium">Completed</span>
                        ) : (
                          <button
                            onClick={() => toggleCampaign(camp.id)}
                            className={`p-2 rounded-sm border transition-colors ${
                              camp.status === "running"
                                ? "border-amber-200 bg-amber-50/50 text-amber-700 hover:bg-amber-100"
                                : "border-emerald-200 bg-emerald-50/50 text-emerald-700 hover:bg-emerald-100"
                            }`}
                            title={camp.status === "running" ? "Pause Campaign" : "Resume Campaign"}
                          >
                            {camp.status === "running" ? (
                              <Pause className="w-4 h-4" />
                            ) : (
                              <Play className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: LEAD DIRECTORY */}
      {activeTab === "leads" && (
        <div className="space-y-4 animate-in fade-in duration-150">
          {/* Controls & Search */}
          <div className="bg-white border border-zinc-200 p-4 rounded-sm flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search lead name or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-1.5 text-xs w-60 focus:outline-none focus:border-zinc-950 focus:bg-white"
                />
              </div>

              {/* Campaign Filter Select */}
              <div className="relative flex items-center">
                <Filter className="w-3.5 h-3.5 absolute left-2.5 text-zinc-400" />
                <select
                  value={selectedCampaignFilter}
                  onChange={(e) => setSelectedCampaignFilter(e.target.value)}
                  className="appearance-none bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-8 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                >
                  <option value="all">Filter: All Campaigns</option>
                  {campaigns.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="text-xs text-zinc-500 font-mono-stat">
              Showing {filteredLeads.length} of {leads.length} leads
            </div>
          </div>

          {/* Table */}
          <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                    <th className="px-5 py-3 text-left">Contact Name</th>
                    <th className="px-5 py-3 text-left">Phone Number</th>
                    <th className="px-5 py-3 text-left">Campaign Assigned</th>
                    <th className="px-5 py-3 text-center">Status</th>
                    <th className="px-5 py-3 text-center">Attempts</th>
                    <th className="px-5 py-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200">
                  {filteredLeads.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-zinc-400 italic">
                        No matching leads found.
                      </td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="px-5 py-4 whitespace-nowrap text-zinc-950 font-semibold">{lead.name}</td>
                        <td className="px-5 py-4 whitespace-nowrap">
                          <span className="font-mono-stat font-medium text-zinc-700">{lead.phone}</span>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-zinc-500 text-xs font-medium">{lead.campaign}</td>
                        <td className="px-5 py-4 whitespace-nowrap text-center">
                          <span className={`px-2 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wide ${
                            lead.status === "completed"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200/50"
                              : lead.status === "calling"
                              ? "bg-blue-50 text-blue-700 border border-blue-200/50 animate-pulse"
                              : lead.status === "failed"
                              ? "bg-red-50 text-red-700 border border-red-200/50"
                              : lead.status === "voicemail"
                              ? "bg-amber-50 text-amber-700 border border-amber-200/50"
                              : "bg-zinc-50 text-zinc-600 border border-zinc-200/50"
                          }`}>
                            {lead.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-center font-mono-stat font-bold text-zinc-600 text-xs">{lead.attempts}</td>
                        <td className="px-5 py-4 whitespace-nowrap text-center">
                          <button
                            onClick={() => handleDeleteLead(lead.id, lead.name)}
                            className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                            title="Remove Lead"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: ADD LEADS / QUICK UPLOAD */}
      {activeTab === "upload" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in fade-in duration-150">
          
          {/* Quick Copy-Paste Bulk Upload Column */}
          <div className="bg-white border border-zinc-200 p-6 rounded-sm space-y-4">
            <div>
              <h3 className="font-bold text-base text-zinc-950 flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-indigo-500" />
                <span>Quick Bulk Upload</span>
              </h3>
              <p className="text-xs text-zinc-500">Paste names and phone numbers list to dynamically register dial items.</p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Target Campaign</label>
                <select
                  value={bulkCampaign}
                  onChange={(e) => setBulkCampaign(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                >
                  {campaigns.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Paste CSV Data or List</label>
                <p className="text-[10px] text-zinc-400 mb-1">Enter Name and Phone comma-separated or space-separated (one lead per line):</p>
                <textarea
                  rows={8}
                  value={bulkText}
                  onChange={(e) => setBulkText(e.target.value)}
                  placeholder="John Doe, +15550192831&#10;Jane Smith, +15550249182&#10;Michael Chang, +15550813921"
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-3 text-xs focus:outline-none focus:border-zinc-950 font-mono focus:bg-white"
                />
              </div>

              <button
                onClick={handleParseText}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-sm transition-colors"
              >
                Parse & Map Columns
              </button>
            </div>

            {/* Parse Preview Container */}
            {csvPreview.length > 0 && (
              <div className="border border-indigo-150 bg-indigo-50/20 p-4 rounded-sm space-y-3">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-xs text-indigo-950">Parsed Queue Preview ({csvPreview.length} leads)</span>
                  <button 
                    onClick={() => setCsvPreview([])} 
                    className="text-zinc-400 hover:text-zinc-600"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                
                <div className="max-h-48 overflow-y-auto border border-zinc-200 bg-white rounded-sm">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-zinc-50 text-zinc-500 font-bold border-b border-zinc-200">
                        <th className="px-3 py-1.5">Column 0 (Name)</th>
                        <th className="px-3 py-1.5">Column 1 (Phone)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-150">
                      {csvPreview.slice(0, 10).map((item, idx) => (
                        <tr key={idx}>
                          <td className="px-3 py-1.5 text-zinc-700">{item.name}</td>
                          <td className="px-3 py-1.5 text-zinc-900 font-mono-stat">{item.phone}</td>
                        </tr>
                      ))}
                      {csvPreview.length > 10 && (
                        <tr>
                          <td colSpan={2} className="px-3 py-1.5 text-zinc-400 text-center italic">
                            ... and {csvPreview.length - 10} more records
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <button
                  onClick={handleImportBulk}
                  className="w-full py-2 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm transition-colors flex items-center justify-center gap-1.5"
                >
                  <Database className="w-3.5 h-3.5" />
                  <span>Import {csvPreview.length} Leads to Dialer Queue</span>
                </button>
              </div>
            )}
          </div>

          {/* Add Single Lead manually */}
          <div className="bg-white border border-zinc-200 p-6 rounded-sm space-y-4 h-fit">
            <div>
              <h3 className="font-bold text-base text-zinc-950 flex items-center gap-2">
                <Plus className="w-5 h-5 text-emerald-500" />
                <span>Single Dialing Lead</span>
              </h3>
              <p className="text-xs text-zinc-500">Insert an individual customer payload manually into a running queue</p>
            </div>

            <form onSubmit={handleAddSingleLead} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. John Doe"
                  value={singleName}
                  onChange={(e) => setSingleName(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Phone Number</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. +1 (555) 123-4567"
                  value={singlePhone}
                  onChange={(e) => setSinglePhone(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono-stat"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Target Campaign</label>
                <select
                  value={singleCampaign}
                  onChange={(e) => setSingleCampaign(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                >
                  {campaigns.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>

              <button
                type="submit"
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-sm transition-colors flex items-center justify-center gap-1"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Add Single Customer to Dialer</span>
              </button>
            </form>
          </div>

        </div>
      )}
    </div>
  );
}
