import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { 
  Phone, Plus, Shield, CheckCircle, RefreshCw, 
  HelpCircle, ToggleLeft, ToggleRight, Sparkles,
  Settings2, Search, Trash2, ArrowRight, Server, Check, AlertCircle,
  Users, DollarSign, ExternalLink, Key, Settings, PlayCircle
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import AgentService from "@/services/agent.service";
import { Agent } from "@/types";
import { useAuth } from "@/store/authStore";

interface PhoneNumberItem {
  id: string;
  number: string;
  name: string;
  agentId: string; // References Agent.id
  status: "active" | "available" | "pending_sip" | "inactive";
  capabilities: { voice: boolean; sms: boolean };
  provider: "Twilio" | "CITL";
  monthlyCost: string;
  setupCost?: string;
  ownerId?: string | number; // References user.clientId or user.id
  ownerName?: string; // Client/Company Name
  sipConfig?: {
    domain: string;
    authUsername: string;
    password?: string;
    proxy: string;
    dtmfMode: string;
    preferredCodec: string;
  };
  createdAt?: string;
}

const INITIAL_NUMBERS: PhoneNumberItem[] = [
  {
    id: "num-1",
    number: "+64 9 888 1234",
    name: "CITL Main Support Line",
    agentId: "",
    status: "active",
    capabilities: { voice: true, sms: true },
    provider: "CITL",
    monthlyCost: "$5.00",
    setupCost: "$0.00",
    ownerId: "client-123",
    ownerName: "Acme Corporates",
    sipConfig: {
      domain: "phone.c-tel.co.nz",
      authUsername: "+6498881234",
      proxy: "phone.c-tel.co.nz",
      dtmfMode: "RFC2833",
      preferredCodec: "G.711a"
    }
  },
  {
    id: "num-2",
    number: "+1 (855) 428-6423",
    name: "Twilio Outbound Sales",
    agentId: "",
    status: "available",
    capabilities: { voice: true, sms: false },
    provider: "Twilio",
    monthlyCost: "$2.00",
    setupCost: "$1.00",
    sipConfig: {
      domain: "phone.twilio.com",
      authUsername: "+18554286423",
      proxy: "phone.twilio.com",
      dtmfMode: "RFC2833",
      preferredCodec: "G.711u"
    }
  },
  {
    id: "num-3",
    number: "+64 9 888 5678",
    name: "Auckland Helpdesk DID",
    agentId: "",
    status: "pending_sip",
    capabilities: { voice: true, sms: true },
    provider: "CITL",
    monthlyCost: "$4.50",
    setupCost: "$0.00"
  }
];

export default function PhoneNumbers() {
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const isSuperAdmin = user?.role === "super_admin" || user?.role === "finance_admin";

  const [activeTab, setActiveTab] = useState<"numbers" | "browse">("numbers");
  const [superadminTab, setSuperadminTab] = useState<"published" | "drafts" | "disconnected">("published");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [numbers, setNumbers] = useState<PhoneNumberItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");



  // Client Rental State
  const [selectedRentNumber, setSelectedRentNumber] = useState<PhoneNumberItem | null>(null);
  const [rentFriendlyName, setRentFriendlyName] = useState("");
  const [rentAgentId, setRentAgentId] = useState("");

  // Load numbers, agents, and settings on mount
  useEffect(() => {
    // 1. Fetch Agents
    AgentService.getAll()
      .then((data) => {
        setAgents(data);
      })
      .catch(() => {});

    // 2. Load local numbers first
    let localList: PhoneNumberItem[] = INITIAL_NUMBERS;
    const storedNumbers = localStorage.getItem("42voice_phone_numbers");
    if (storedNumbers) {
      localList = JSON.parse(storedNumbers);
      setNumbers(localList);
    } else {
      setNumbers(INITIAL_NUMBERS);
      localStorage.setItem("42voice_phone_numbers", JSON.stringify(INITIAL_NUMBERS));
    }
  }, []);

  // Update tab selection automatically when user role changes
  useEffect(() => {
    setActiveTab("numbers");
    setSuperadminTab("published");
  }, [user?.role]);

  const saveNumbers = (newNumbers: PhoneNumberItem[]) => {
    setNumbers(newNumbers);
    localStorage.setItem("42voice_phone_numbers", JSON.stringify(newNumbers));
  };



  const toggleStatus = (id: string) => {
    const updated = numbers.map(num => {
      if (num.id === id) {
        const nextStatus = num.status === "active" ? "inactive" : "active";
        toast.success(`Number status toggled to ${nextStatus}`);
        return { ...num, status: nextStatus as any };
      }
      return num;
    });
    saveNumbers(updated);
  };

  const handleAgentChange = (id: string, agentId: string) => {
    const updated = numbers.map(num => {
      if (num.id === id) {
        const agentName = agents.find(a => a.id === agentId)?.name || "Unassigned";
        toast.success(`DID assigned to AI Agent: ${agentName}`);
        return { ...num, agentId };
      }
      return num;
    });
    saveNumbers(updated);
  };

  const handleReleaseNumber = (id: string, numStr: string) => {
    if (window.confirm(`Are you sure you want to release / delete number ${numStr}? This cannot be undone.`)) {
      const updated = numbers.filter(num => num.id !== id);
      saveNumbers(updated);
      toast.success(`Released phone number ${numStr}`);
    }
  };

  // Client returning rented number
  const handleClientReleaseNumber = (id: string, numStr: string) => {
    if (window.confirm(`Are you sure you want to release ${numStr}? It will be returned to the superadmin pool.`)) {
      const updated = numbers.map(num => {
        if (num.id === id) {
          toast.success(`Released line ${numStr} back to public pool.`);
          return {
            ...num,
            status: "available" as const,
            ownerId: "",
            ownerName: "",
            agentId: ""
          };
        }
        return num;
      });
      saveNumbers(updated);
    }
  };

  const handleRentConfirm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRentNumber) return;

    const updated = numbers.map(num => {
      if (num.id === selectedRentNumber.id) {
        return {
          ...num,
          status: "active" as const,
          ownerId: user?.clientId || user?.id || "client-123",
          ownerName: user?.name || "Client Enterprise",
          name: rentFriendlyName.trim() || num.name,
          agentId: rentAgentId
        };
      }
      return num;
    });

    saveNumbers(updated);
    toast.success(`Successfully rented and activated ${selectedRentNumber.number}!`);
    setSelectedRentNumber(null);
    setRentFriendlyName("");
    setRentAgentId("");
    setActiveTab("numbers");
  };

  // Filtering based on search query
  const filteredNumbers = numbers.filter(num => {
    const query = searchQuery.toLowerCase();
    return (
      num.number.toLowerCase().includes(query) ||
      num.name.toLowerCase().includes(query) ||
      num.provider.toLowerCase().includes(query) ||
      (num.ownerName && num.ownerName.toLowerCase().includes(query))
    );
  });

  // Split logic based on roles
  const publishedNumbers = filteredNumbers.filter(n => n.status === "available" || n.status === "active");
  const draftNumbers = filteredNumbers.filter(n => n.status === "pending_sip" || n.status === "inactive");
  const disconnectedNumbers = filteredNumbers.filter(
    n => !n.sipConfig || !n.sipConfig.password || !n.sipConfig.domain || n.status === "pending_sip" || n.status === "inactive"
  );
  const clientNumbers = filteredNumbers.filter(num => num.ownerId === (user?.clientId || user?.id || "client-123"));
  const availableToRent = filteredNumbers.filter(num => num.status === "available");

  return (
    <div className="space-y-6" data-testid="phone-numbers-page">
      {/* Header section with DEMO Switcher */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-zinc-200 pb-5">
        <div>
          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest bg-zinc-100 px-2 py-0.5 rounded-sm">DID Portal</span>
          <h1 className="text-2xl font-bold text-zinc-950 mt-1 font-display tracking-tight">
            Phone Numbers
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            {isSuperAdmin 
              ? "Register, publish, and monitor phone numbers across client accounts."
              : "Manage your active voice lines, configure agent routing, and lease new numbers."
            }
          </p>
        </div>

      </div>

      {/* SUPERADMIN INTERFACE */}
      {isSuperAdmin && (
        <div className="space-y-6">
          {/* Superadmin KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Total Registered DIDs</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">{numbers.length}</h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Leased DIDs</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">
                {numbers.filter(n => n.status === "active").length}
              </h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Available for rent</p>
              <h3 className="text-xl font-bold text-emerald-600 mt-1 font-mono-stat">
                {numbers.filter(n => n.status === "available").length}
              </h3>
            </div>
            <div className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs">
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Estimated System Yield</p>
              <h3 className="text-xl font-bold text-zinc-950 mt-1 font-mono-stat">
                ${numbers
                  .filter(n => n.status === "active")
                  .reduce((acc, n) => acc + parseFloat(n.monthlyCost.replace("$", "")), 0)
                  .toFixed(2)}/mo
              </h3>
            </div>
          </div>

          {/* Superadmin Tabs */}
          <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
            <button
              onClick={() => setSuperadminTab("published")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "published" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Published Numbers ({publishedNumbers.length})
            </button>
            <button
              onClick={() => setSuperadminTab("drafts")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "drafts" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Draft Numbers ({draftNumbers.length})
            </button>
            <button
              onClick={() => setSuperadminTab("disconnected")}
              className={`pb-3 border-b-2 transition-all ${
                superadminTab === "disconnected" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Not Connected to LiveKit ({disconnectedNumbers.length})
            </button>
          </div>

          {/* REGISTERED DIDs TABLE */}
          <div className="space-y-4">
            <div className="flex justify-between items-center gap-3">
              {/* Search Bar */}
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search DIDs, friendly names, or clients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-zinc-200 rounded-sm pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                />
              </div>

              <button
                onClick={() => navigate("/phone-numbers/add")}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors shadow-xs"
              >
                <Plus className="w-4 h-4" />
                <span>Register Purchased DID</span>
              </button>
            </div>

            {superadminTab === "published" && (
              publishedNumbers.length === 0 ? (
                <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
                  <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
                  <h3 className="font-bold text-sm text-zinc-950">No published DIDs</h3>
                  <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
                    You haven't registered or published any numbers. Get started by registering one.
                  </p>
                </div>
              ) : (
                <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                        <th className="px-5 py-3 text-left">Phone Number</th>
                        <th className="px-5 py-3 text-left">Friendly Label</th>
                        <th className="px-5 py-3 text-left">Carrier</th>
                        <th className="px-5 py-3 text-left">Client Lease</th>
                        <th className="px-5 py-3 text-left font-mono">Routing (Agent)</th>
                        <th className="px-5 py-3 text-center">Status</th>
                        <th className="px-5 py-3 text-right">Price</th>
                        <th className="px-5 py-3 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200">
                      {publishedNumbers.map((num) => (
                        <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-zinc-400" />
                              <span className="font-mono font-medium text-zinc-900">{num.number}</span>
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium text-xs">{num.name}</td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wider ${
                              num.provider === "Twilio" 
                                ? "bg-red-50 text-red-600 border border-red-200/50" 
                                : "bg-zinc-100 text-zinc-800 border border-zinc-200"
                            }`}>
                              {num.provider}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            {num.ownerId ? (
                              <div className="flex items-center gap-1.5 text-zinc-900 font-semibold text-xs">
                                <Users className="w-3.5 h-3.5 text-zinc-400" />
                                <span>{num.ownerName}</span>
                              </div>
                            ) : (
                              <span className="text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/50 px-2 py-0.5 rounded-sm">
                                Available to Rent
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <select
                              value={num.agentId}
                              disabled={!num.ownerId}
                              onChange={(e) => handleAgentChange(num.id, e.target.value)}
                              className="bg-zinc-50 border border-zinc-200 rounded-sm px-2 py-1 text-xs text-zinc-800 focus:outline-none focus:border-zinc-950 font-medium disabled:opacity-50"
                            >
                              <option value="">-- Sandbox Router --</option>
                              {agents.map((agent) => (
                                <option key={agent.id} value={agent.id}>
                                  {agent.name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <span className={`inline-block px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider border ${
                              num.status === "active"
                                ? "bg-green-50 text-green-700 border-green-200"
                                : "bg-blue-50 text-blue-700 border-blue-200"
                            }`}>
                              {num.status === "active" ? "Leased" : "Available"}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-900 font-medium font-mono text-xs">
                            {num.monthlyCost}/mo
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <button
                              onClick={() => handleReleaseNumber(num.id, num.number)}
                              className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                              title="Delete/Release DID"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {superadminTab === "drafts" && (
              draftNumbers.length === 0 ? (
                <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
                  <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
                  <h3 className="font-bold text-sm text-zinc-950">No draft DIDs</h3>
                  <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
                    Create a draft number by choosing "Save as Draft" during registration.
                  </p>
                </div>
              ) : (
                <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                        <th className="px-5 py-3 text-left">Phone Number</th>
                        <th className="px-5 py-3 text-left">Friendly Label</th>
                        <th className="px-5 py-3 text-left">Carrier</th>
                        <th className="px-5 py-3 text-center">Status</th>
                        <th className="px-5 py-3 text-right">Price</th>
                        <th className="px-5 py-3 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200">
                      {draftNumbers.map((num) => (
                        <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-zinc-400" />
                              <span className="font-mono font-medium text-zinc-900">{num.number}</span>
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium text-xs">{num.name}</td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
                              {num.provider}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider border bg-amber-50 text-amber-700 border-amber-200">
                              Draft / Offline
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-900 font-medium font-mono text-xs">
                            {num.monthlyCost}/mo
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <button
                              onClick={() => handleReleaseNumber(num.id, num.number)}
                              className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                              title="Delete/Release DID"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {superadminTab === "disconnected" && (
              disconnectedNumbers.length === 0 ? (
                <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
                  <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
                  <h3 className="font-bold text-sm text-zinc-950">All DIDs Connected</h3>
                  <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
                    Every registered number contains complete LiveKit SIP settings.
                  </p>
                </div>
              ) : (
                <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                        <th className="px-5 py-3 text-left">Phone Number</th>
                        <th className="px-5 py-3 text-left">Friendly Label</th>
                        <th className="px-5 py-3 text-left">Carrier</th>
                        <th className="px-5 py-3 text-left">Connection Problem</th>
                        <th className="px-5 py-3 text-center">Status</th>
                        <th className="px-5 py-3 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200">
                      {disconnectedNumbers.map((num) => (
                        <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-zinc-400" />
                              <span className="font-mono font-medium text-zinc-900">{num.number}</span>
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium text-xs">{num.name}</td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
                              {num.provider}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-xs text-red-650 font-semibold">
                            <div className="flex items-center gap-1.5 text-red-700">
                              <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                              <span>
                                {!num.sipConfig
                                  ? "No SIP credentials configured"
                                  : !num.sipConfig.password
                                  ? "SIP password unconfigured"
                                  : "Pending LiveKit registrar binding"}
                              </span>
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <span className="inline-block px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wider border bg-red-50 text-red-700 border-red-200">
                              Not Connected
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <button
                              onClick={() => handleReleaseNumber(num.id, num.number)}
                              className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                              title="Delete/Release DID"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {/* CLIENT / CUSTOMER INTERFACE */}
      {!isSuperAdmin && (
        <div className="space-y-6">
          
          {/* Client Tabs */}
          <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
            <button
              onClick={() => setActiveTab("numbers")}
              className={`pb-3 border-b-2 transition-all ${
                activeTab === "numbers" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              My Rented Numbers ({clientNumbers.length})
            </button>
            <button
              onClick={() => setActiveTab("browse")}
              className={`pb-3 border-b-2 transition-all ${
                activeTab === "browse" 
                  ? "border-zinc-950 text-zinc-950 font-bold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-950"
              }`}
            >
              Browse & Rent Lines ({availableToRent.length})
            </button>
          </div>

          {/* TAB: MY RENTED NUMBERS */}
          {activeTab === "numbers" && (
            <div className="space-y-4">
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search my numbers..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-zinc-200 rounded-sm pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                />
              </div>

              {clientNumbers.length === 0 ? (
                <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
                  <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
                  <h3 className="font-bold text-sm text-zinc-950">No leased numbers</h3>
                  <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
                    You haven't leased any voice numbers yet. Check out the available pool to get started.
                  </p>
                  <button
                    onClick={() => setActiveTab("browse")}
                    className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm"
                  >
                    Browse Available Pool
                  </button>
                </div>
              ) : (
                <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                        <th className="px-5 py-3 text-left">Phone Number</th>
                        <th className="px-5 py-3 text-left">Friendly Name</th>
                        <th className="px-5 py-3 text-left">Carrier</th>
                        <th className="px-5 py-3 text-left">Connected AI Agent</th>
                        <th className="px-5 py-3 text-left">Capabilities</th>
                        <th className="px-5 py-3 text-center">Status</th>
                        <th className="px-5 py-3 text-right">Rent Cost</th>
                        <th className="px-5 py-3 text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200">
                      {clientNumbers.map((num) => (
                        <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-zinc-400" />
                              <span className="font-mono font-medium text-zinc-900">{num.number}</span>
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium text-xs">{num.name}</td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <span className="px-1.5 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wider bg-zinc-100 text-zinc-800 border border-zinc-200">
                              {num.provider}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <select
                              value={num.agentId}
                              onChange={(e) => handleAgentChange(num.id, e.target.value)}
                              className="bg-zinc-50 border border-zinc-200 rounded-sm px-2 py-1 text-xs text-zinc-800 focus:outline-none focus:border-zinc-950 font-medium"
                            >
                              <option value="">-- Sandbox Router --</option>
                              {agents.map((agent) => (
                                <option key={agent.id} value={agent.id}>
                                  {agent.name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex gap-1">
                              {num.capabilities.voice && (
                                <span className="px-1.5 py-0.5 bg-zinc-150 text-zinc-700 rounded-sm text-[9px] uppercase font-bold tracking-wider">Voice</span>
                              )}
                              {num.capabilities.sms && (
                                <span className="px-1.5 py-0.5 bg-zinc-150 text-zinc-700 rounded-sm text-[9px] uppercase font-bold tracking-wider">SMS</span>
                              )}
                            </div>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <button 
                              onClick={() => toggleStatus(num.id)}
                              className="inline-flex focus:outline-none transition-colors"
                            >
                              {num.status === "active" ? (
                                <ToggleRight className="w-7 h-7 text-emerald-600" />
                              ) : (
                                <ToggleLeft className="w-7 h-7 text-zinc-300" />
                              )}
                            </button>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-900 font-medium font-mono text-xs">
                            {num.monthlyCost}/mo
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-center">
                            <button
                              onClick={() => handleClientReleaseNumber(num.id, num.number)}
                              className="text-zinc-400 hover:text-red-600 p-1 transition-colors text-xs font-semibold"
                              title="Return Line"
                            >
                              Release
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB: BROWSE & RENT NUMBERS */}
          {activeTab === "browse" && (
            <div className="space-y-4">
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Filter available pool..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-zinc-200 rounded-sm pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                />
              </div>

              {availableToRent.length === 0 ? (
                <div className="border border-zinc-200 bg-white p-12 text-center rounded-sm">
                  <Server className="w-10 h-10 text-zinc-350 mx-auto mb-2" />
                  <p className="text-xs text-zinc-500 font-medium">All numbers leased or none are currently registered by superadmin.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {availableToRent.map((item) => (
                    <div key={item.id} className="bg-white border border-zinc-200 p-4 rounded-sm flex flex-col justify-between hover:border-zinc-400 transition-colors shadow-xs">
                      <div>
                        <div className="flex items-center justify-between">
                          <span className={`inline-block px-1.5 py-0.5 text-[8px] font-bold rounded-sm uppercase tracking-wider ${
                            item.provider === "Twilio" 
                              ? "bg-red-50 text-red-700 border border-red-200/50" 
                              : "bg-zinc-100 text-zinc-800"
                          }`}>
                            {item.provider}
                          </span>
                          <span className="text-[10px] text-zinc-400 font-mono-stat flex items-center gap-1">
                            <Check className="w-3 h-3 text-emerald-500" /> SIP Activated
                          </span>
                        </div>
                        <h4 className="text-lg font-bold text-zinc-950 font-mono mt-2">{item.number}</h4>
                        <p className="text-[11px] text-zinc-500 mt-0.5">{item.name}</p>
                        
                        <div className="flex gap-1.5 mt-3">
                          {item.capabilities.voice && (
                            <span className="px-1.5 py-0.2 bg-zinc-50 border border-zinc-200 text-zinc-600 rounded-sm text-[9px] uppercase font-bold tracking-wider">Voice</span>
                          )}
                          {item.capabilities.sms && (
                            <span className="px-1.5 py-0.2 bg-zinc-50 border border-zinc-200 text-zinc-600 rounded-sm text-[9px] uppercase font-bold tracking-wider">SMS</span>
                          )}
                        </div>
                      </div>

                      <div className="mt-5 border-t border-zinc-100 pt-3 flex items-center justify-between">
                        <div>
                          <div className="text-sm font-bold text-zinc-950 font-mono-stat">{item.monthlyCost}</div>
                          <div className="text-[9px] text-zinc-400 font-medium">per month {parseFloat(item.setupCost?.replace("$", "") || "0") > 0 ? `+ ${item.setupCost} setup` : ""}</div>
                        </div>
                        <button
                          onClick={() => setSelectedRentNumber(item)}
                          className="px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-all"
                        >
                          Rent Line
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* RENTAL CONFIRMATION OVERLAY MODAL */}
          {selectedRentNumber && (
            <div className="fixed inset-0 bg-zinc-950/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
              <div className="bg-white border border-zinc-200 max-w-md w-full p-6 shadow-xl rounded-sm">
                <h3 className="text-base font-bold text-zinc-950 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                  <span>Rent DID Line</span>
                </h3>
                <p className="text-xs text-zinc-500 mt-1">
                  You are leasing the phone number <strong className="font-mono text-zinc-900">{selectedRentNumber.number}</strong>. This line will route incoming SIP trunk calls to your 42Voice dashboard.
                </p>

                <form onSubmit={handleRentConfirm} className="mt-4 space-y-4">
                  {/* Friendly Name */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600 mb-1">Friendly Name / Label</label>
                    <input
                      type="text"
                      placeholder="e.g. Sales Hotline, VIP support"
                      value={rentFriendlyName}
                      onChange={(e) => setRentFriendlyName(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                    />
                  </div>

                  {/* Route to Agent */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600 mb-1">Link to AI Voice Agent</label>
                    <select
                      value={rentAgentId}
                      onChange={(e) => setRentAgentId(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950"
                    >
                      <option value="">-- Sandbox Router (LiveKit SIP Call) --</option>
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Price breakdown */}
                  <div className="bg-zinc-50 border border-zinc-150 p-3 rounded-sm text-xs text-zinc-600 space-y-1.5 font-medium">
                    <div className="flex justify-between">
                      <span>Monthly DID Lease:</span>
                      <span className="font-mono text-zinc-950 font-semibold">{selectedRentNumber.monthlyCost}</span>
                    </div>
                    {parseFloat(selectedRentNumber.setupCost?.replace("$", "") || "0") > 0 && (
                      <div className="flex justify-between">
                        <span>One-time Setup Fee:</span>
                        <span className="font-mono text-zinc-950 font-semibold">{selectedRentNumber.setupCost}</span>
                      </div>
                    )}
                    <div className="flex justify-between border-t border-zinc-200 pt-1.5 text-zinc-900 font-bold">
                      <span>Total Due Now:</span>
                      <span>
                        ${(
                          parseFloat(selectedRentNumber.monthlyCost.replace("$", "")) + 
                          parseFloat(selectedRentNumber.setupCost?.replace("$", "") || "0")
                        ).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex gap-2 justify-end pt-2 border-t border-zinc-150">
                    <button
                      type="button"
                      onClick={() => setSelectedRentNumber(null)}
                      className="px-3.5 py-1.5 border border-zinc-200 text-zinc-600 hover:bg-zinc-50 text-xs font-semibold rounded-sm bg-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm shadow-xs"
                    >
                      Confirm Rental
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
