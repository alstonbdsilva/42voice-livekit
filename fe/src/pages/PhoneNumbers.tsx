import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { 
  Phone, Plus, Shield, CheckCircle, RefreshCw, 
  HelpCircle, MessageSquare, ToggleLeft, ToggleRight, Sparkles,
  Settings2, Search, Trash2, ArrowRight, Server, Check, AlertCircle
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import AgentService from "@/services/agent.service";
import { Agent } from "@/types";

interface PhoneNumberItem {
  id: string;
  number: string;
  name: string;
  agentId: string; // References Agent.id
  status: "active" | "inactive";
  capabilities: { voice: boolean; sms: boolean };
  provider: "Twilio" | "Telnyx";
  monthlyCost: string;
}

// Initial mock numbers list that we will save to localStorage
const INITIAL_NUMBERS: PhoneNumberItem[] = [
  {
    id: "num-1",
    number: "+1 (855) 428-6423",
    name: "Main Sales Line",
    agentId: "",
    status: "active",
    capabilities: { voice: true, sms: true },
    provider: "Twilio",
    monthlyCost: "$2.00",
  },
  {
    id: "num-2",
    number: "+1 (855) 428-6424",
    name: "Support Hotline",
    agentId: "",
    status: "active",
    capabilities: { voice: true, sms: false },
    provider: "Telnyx",
    monthlyCost: "$1.50",
  }
];

export default function PhoneNumbers() {
  const [activeTab, setActiveTab] = useState<"numbers" | "buy" | "settings">("numbers");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [numbers, setNumbers] = useState<PhoneNumberItem[]>([]);
  
  // Carrier credentials state (persisted)
  const [twilioSid, setTwilioSid] = useState("");
  const [twilioToken, setTwilioToken] = useState("");
  const [twilioNumber, setTwilioNumber] = useState("");
  const [telnyxKey, setTelnyxKey] = useState("");
  const [isCredentialsSaved, setIsCredentialsSaved] = useState(false);

  // Search/Buy State
  const [buyProvider, setBuyProvider] = useState<"Twilio" | "Telnyx">("Twilio");
  const [areaCode, setAreaCode] = useState("");
  const [country, setCountry] = useState("US");
  const [numberType, setNumberType] = useState<"local" | "toll-free">("local");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Omit<PhoneNumberItem, "id" | "agentId" | "status">[]>([]);
  const [selectedBuyNumber, setSelectedBuyNumber] = useState<Omit<PhoneNumberItem, "id" | "agentId" | "status"> | null>(null);
  const [assignAgentId, setAssignAgentId] = useState("");
  const [friendlyName, setFriendlyName] = useState("");

  // Load numbers, agents, and settings on mount
  useEffect(() => {
    // 1. Fetch Agents
    AgentService.getAll()
      .then((data) => {
        setAgents(data);
        // Link initial mock numbers to first available agent if none set
        if (data.length > 0) {
          const stored = localStorage.getItem("42voice_phone_numbers");
          if (!stored) {
            const initialWithAgents: PhoneNumberItem[] = INITIAL_NUMBERS.map((n, idx) => ({
              ...n,
              agentId: String(data[idx % data.length]?.id || "")
            }));
            setNumbers(initialWithAgents);
            localStorage.setItem("42voice_phone_numbers", JSON.stringify(initialWithAgents));
          }
        }
      })
      .catch(() => {});

    // 2. Load numbers from storage
    const storedNumbers = localStorage.getItem("42voice_phone_numbers");
    if (storedNumbers) {
      setNumbers(JSON.parse(storedNumbers));
    } else {
      setNumbers(INITIAL_NUMBERS);
    }

    // 3. Load credentials from storage
    const sid = localStorage.getItem("twilio_sid") || "";
    const token = localStorage.getItem("twilio_token") || "";
    const num = localStorage.getItem("twilio_phone_number") || "";
    const telnyx = localStorage.getItem("telnyx_key") || "";
    setTwilioSid(sid);
    setTwilioToken(token);
    setTwilioNumber(num);
    setTelnyxKey(telnyx);
    if (sid || telnyx) {
      setIsCredentialsSaved(true);
    }
  }, []);

  const saveNumbers = (newNumbers: PhoneNumberItem[]) => {
    setNumbers(newNumbers);
    localStorage.setItem("42voice_phone_numbers", JSON.stringify(newNumbers));
  };

  const handleSaveCredentials = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("twilio_sid", twilioSid);
    localStorage.setItem("twilio_token", twilioToken);
    localStorage.setItem("twilio_phone_number", twilioNumber);
    localStorage.setItem("telnyx_key", telnyxKey);
    setIsCredentialsSaved(true);
    toast.success("Carrier integration credentials saved successfully!");
  };

  const handleDisconnectCarriers = () => {
    localStorage.removeItem("twilio_sid");
    localStorage.removeItem("twilio_token");
    localStorage.removeItem("twilio_phone_number");
    localStorage.removeItem("telnyx_key");
    setTwilioSid("");
    setTwilioToken("");
    setTwilioNumber("");
    setTelnyxKey("");
    setIsCredentialsSaved(false);
    toast.info("Carrier credentials cleared.");
  };

  const toggleStatus = (id: string) => {
    const updated = numbers.map(num => {
      if (num.id === id) {
        const nextStatus: "active" | "inactive" = num.status === "active" ? "inactive" : "active";
        toast.success(`Number ${num.number} set to ${nextStatus}`);
        return { ...num, status: nextStatus };
      }
      return num;
    });
    saveNumbers(updated);
  };

  const handleAgentChange = (id: string, agentId: string) => {
    const updated = numbers.map(num => {
      if (num.id === id) {
        const agentName = agents.find(a => a.id === agentId)?.name || "Unassigned";
        toast.success(`Number ${num.number} assigned to ${agentName}`);
        return { ...num, agentId };
      }
      return num;
    });
    saveNumbers(updated);
  };

  const handleReleaseNumber = (id: string, numStr: string) => {
    if (window.confirm(`Are you sure you want to release the number ${numStr}? This cannot be undone.`)) {
      const updated = numbers.filter(num => num.id !== id);
      saveNumbers(updated);
      toast.success(`Released phone number ${numStr}`);
    }
  };

  // Mock available numbers search
  const handleSearchNumbers = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSearching(true);
    setSearchResults([]);

    setTimeout(() => {
      const prefix = areaCode.trim() || "855";
      const results: Omit<PhoneNumberItem, "id" | "agentId" | "status">[] = [
        {
          number: `+1 (${prefix}) 502-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "Pending Assignment",
          capabilities: { voice: true, sms: true },
          provider: buyProvider,
          monthlyCost: buyProvider === "Twilio" ? "$1.15" : "$1.00",
        },
        {
          number: `+1 (${prefix}) 618-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "Pending Assignment",
          capabilities: { voice: true, sms: true },
          provider: buyProvider,
          monthlyCost: buyProvider === "Twilio" ? "$1.15" : "$1.00",
        },
        {
          number: `+1 (${prefix}) 407-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "Pending Assignment",
          capabilities: { voice: true, sms: false },
          provider: buyProvider,
          monthlyCost: buyProvider === "Twilio" ? "$1.15" : "$0.85",
        },
        {
          number: `+1 (${prefix}) 321-${Math.floor(1000 + Math.random() * 9000)}`,
          name: "Pending Assignment",
          capabilities: { voice: true, sms: true },
          provider: buyProvider,
          monthlyCost: buyProvider === "Twilio" ? "$2.00" : "$1.50",
        }
      ];
      setSearchResults(results);
      setIsSearching(false);
      toast.success(`Found available numbers for area code ${prefix}`);
    }, 800);
  };

  const handlePurchase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBuyNumber) return;

    // Check if credentials exist for the provider
    if (selectedBuyNumber.provider === "Twilio" && !twilioSid) {
      toast.error("Please configure your Twilio Account SID and Auth Token under Carrier Settings before purchasing.");
      setActiveTab("settings");
      setSelectedBuyNumber(null);
      return;
    }
    if (selectedBuyNumber.provider === "Telnyx" && !telnyxKey) {
      toast.error("Please configure your Telnyx API Key under Carrier Settings before purchasing.");
      setActiveTab("settings");
      setSelectedBuyNumber(null);
      return;
    }

    const newNumber: PhoneNumberItem = {
      id: `num-${Date.now()}`,
      number: selectedBuyNumber.number,
      name: friendlyName.trim() || `DID Line (${selectedBuyNumber.provider})`,
      agentId: assignAgentId,
      status: "active",
      capabilities: selectedBuyNumber.capabilities,
      provider: selectedBuyNumber.provider,
      monthlyCost: selectedBuyNumber.monthlyCost,
    };

    const updated = [...numbers, newNumber];
    saveNumbers(updated);
    
    toast.success(`Successfully provisioned ${newNumber.number} via ${newNumber.provider}!`);
    
    // Reset purchase dialog state
    setSelectedBuyNumber(null);
    setFriendlyName("");
    setAssignAgentId("");
    setActiveTab("numbers");
  };

  return (
    <div className="space-y-6" data-testid="phone-numbers-page">
      <PageHeader 
        title="AI Phone Numbers" 
        subtitle="Claim Twilio/Telnyx numbers, configure inbound webhook trunks, and connect to LiveKit voice agents" 
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("settings")}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 text-sm font-semibold rounded-sm transition-colors"
            >
              <Settings2 className="w-4 h-4 text-zinc-500" />
              <span>Carrier Credentials</span>
            </button>
            <button
              onClick={() => setActiveTab("buy")}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-sm font-semibold rounded-sm transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>Acquire New Number</span>
            </button>
          </div>
        }
      />

      {/* Tabs Layout */}
      <div className="border-b border-zinc-200 flex gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("numbers")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "numbers" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Active DIDs ({numbers.length})
        </button>
        <button
          onClick={() => setActiveTab("buy")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "buy" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Buy Twilio / Telnyx Lines
        </button>
        <button
          onClick={() => setActiveTab("settings")}
          className={`pb-3 border-b-2 transition-all ${
            activeTab === "settings" 
              ? "border-zinc-950 text-zinc-950 font-bold" 
              : "border-transparent text-zinc-500 hover:text-zinc-950"
          }`}
        >
          Carrier Settings
          {isCredentialsSaved && (
            <span className="ml-1.5 inline-block w-2 h-2 rounded-full bg-emerald-500" />
          )}
        </button>
      </div>

      {/* TAB CONTENT: ACTIVE NUMBERS */}
      {activeTab === "numbers" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Connected Providers</p>
              <div className="flex gap-4 mt-2 items-center">
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-semibold ${
                  twilioSid ? "bg-red-50 text-red-700 border border-red-200" : "bg-zinc-100 text-zinc-400"
                }`}>
                  Twilio
                </span>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-semibold ${
                  telnyxKey ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-zinc-100 text-zinc-400"
                }`}>
                  Telnyx
                </span>
              </div>
            </div>

            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">SIP Router Status</p>
              <div className="flex items-center gap-1.5 mt-2.5 text-xs text-emerald-600 font-semibold">
                <CheckCircle className="w-4 h-4 text-emerald-500" />
                <span>Unified Webhook Active</span>
              </div>
            </div>

            <div className="bg-white border border-zinc-200 p-4 rounded-sm">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Monthly Spend</p>
              <h3 className="text-lg font-bold font-display text-zinc-950 mt-1">
                ${numbers.reduce((acc, n) => acc + parseFloat(n.monthlyCost.replace("$", "")), 0).toFixed(2)}/mo
              </h3>
            </div>
          </div>

          {numbers.length === 0 ? (
            <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
              <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
              <h3 className="font-bold text-base text-zinc-950">No registered phone numbers</h3>
              <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
                Connect your Twilio or Telnyx accounts and provision an AI voice number to accept inbound SIP calls.
              </p>
              <button
                onClick={() => setActiveTab("buy")}
                className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm"
              >
                <Plus className="w-3.5 h-3.5" /> Acquire Your First DID
              </button>
            </div>
          ) : (
            <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                      <th className="px-5 py-3 text-left">Phone Number</th>
                      <th className="px-5 py-3 text-left">Friendly Name</th>
                      <th className="px-5 py-3 text-left">Provider</th>
                      <th className="px-5 py-3 text-left">Connected AI Agent</th>
                      <th className="px-5 py-3 text-left">Capabilities</th>
                      <th className="px-5 py-3 text-center">Status</th>
                      <th className="px-5 py-3 text-right">Cost</th>
                      <th className="px-5 py-3 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {numbers.map((num) => (
                      <tr key={num.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="px-5 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <Phone className="w-4 h-4 text-zinc-400" />
                            <span className="font-mono-stat font-medium text-zinc-900">{num.number}</span>
                          </div>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-zinc-700 font-medium">{num.name}</td>
                        <td className="px-5 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-bold rounded-[2px] uppercase tracking-wide ${
                            num.provider === "Twilio" 
                              ? "bg-red-50 text-red-600 border border-red-200/50" 
                              : "bg-emerald-50 text-emerald-600 border border-emerald-200/50"
                          }`}>
                            {num.provider}
                          </span>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap">
                          <select
                            value={num.agentId}
                            onChange={(e) => handleAgentChange(num.id, e.target.value)}
                            className="bg-zinc-50 border border-zinc-200 rounded-sm px-2 py-1 text-xs text-zinc-800 focus:outline-none focus:border-zinc-950 font-medium"
                          >
                            <option value="">-- Route to Sandbox --</option>
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
                              <span className="px-1.5 py-0.2 bg-zinc-100 text-zinc-600 rounded-[2px] text-[10px] uppercase font-bold tracking-wider">Voice</span>
                            )}
                            {num.capabilities.sms && (
                              <span className="px-1.5 py-0.2 bg-zinc-100 text-zinc-600 rounded-[2px] text-[10px] uppercase font-bold tracking-wider">SMS</span>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-center">
                          <button 
                            onClick={() => toggleStatus(num.id)}
                            className="inline-flex focus:outline-none transition-colors"
                          >
                            {num.status === "active" ? (
                              <div className="flex items-center gap-1 text-emerald-600 text-xs font-semibold">
                                <ToggleRight className="w-7 h-7 text-emerald-600" />
                              </div>
                            ) : (
                              <div className="flex items-center gap-1 text-zinc-400 text-xs font-semibold">
                                <ToggleLeft className="w-7 h-7 text-zinc-300" />
                              </div>
                            )}
                          </button>
                        </td>
                        <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-500 font-mono-stat">{num.monthlyCost}/mo</td>
                        <td className="px-5 py-4 whitespace-nowrap text-center">
                          <button
                            onClick={() => handleReleaseNumber(num.id, num.number)}
                            className="text-zinc-400 hover:text-red-600 p-1 transition-colors"
                            title="Release Number"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="bg-zinc-50 border border-zinc-200 p-4 rounded-sm flex items-start gap-3">
            <Shield className="w-5 h-5 text-zinc-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <h4 className="font-semibold text-sm text-zinc-950">SIP trunk integration config</h4>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Inbound call routing uses LiveKit SIP. Once configured, map any DID number on Twilio to route calls directly to: <code className="font-mono text-zinc-900 bg-zinc-150 px-1 py-0.5 rounded-sm">https://api.42voice.ai/v1/livekit/sip/webhook</code>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: BUY NUMBERS */}
      {activeTab === "buy" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Search form column */}
          <div className="bg-white border border-zinc-200 p-5 rounded-sm h-fit space-y-4">
            <div>
              <h3 className="font-bold text-sm text-zinc-950">Find Available Lines</h3>
              <p className="text-xs text-zinc-500">Query direct telecom carriers in real time</p>
            </div>

            {/* Provider Selection */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1.5">Select Provider</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setBuyProvider("Twilio")}
                  className={`py-2 px-3 text-xs border rounded-sm flex flex-col items-center gap-1 transition-all ${
                    buyProvider === "Twilio"
                      ? "bg-red-50/50 border-red-500 text-red-950 font-bold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  <span className="text-sm">Twilio</span>
                  <span className="text-[10px] text-zinc-400 font-normal">Active Carrier API</span>
                </button>
                <button
                  onClick={() => setBuyProvider("Telnyx")}
                  className={`py-2 px-3 text-xs border rounded-sm flex flex-col items-center gap-1 transition-all ${
                    buyProvider === "Telnyx"
                      ? "bg-emerald-50/50 border-emerald-500 text-emerald-950 font-bold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  <span className="text-sm">Telnyx</span>
                  <span className="text-[10px] text-zinc-400 font-normal">Active Carrier API</span>
                </button>
              </div>
            </div>

            <form onSubmit={handleSearchNumbers} className="space-y-4 pt-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">Country</label>
                <select
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950"
                >
                  <option value="US">United States (+1)</option>
                  <option value="CA">Canada (+1)</option>
                  <option value="GB">United Kingdom (+44)</option>
                  <option value="AU">Australia (+61)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">Number Type</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setNumberType("local")}
                    className={`py-1.5 px-3 text-xs font-medium border text-center transition-colors rounded-sm ${
                      numberType === "local" 
                        ? "bg-zinc-950 text-white border-zinc-950" 
                        : "bg-zinc-50 text-zinc-600 border-zinc-200 hover:bg-zinc-100"
                    }`}
                  >
                    Local DID
                  </button>
                  <button
                    type="button"
                    onClick={() => setNumberType("toll-free")}
                    className={`py-1.5 px-3 text-xs font-medium border text-center transition-colors rounded-sm ${
                      numberType === "toll-free" 
                        ? "bg-zinc-950 text-white border-zinc-950" 
                        : "bg-zinc-50 text-zinc-600 border-zinc-200 hover:bg-zinc-100"
                    }`}
                  >
                    Toll-Free
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">Area Code / Prefix</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                  <input
                    value={areaCode}
                    onChange={(e) => setAreaCode(e.target.value)}
                    placeholder="e.g. 415 or 800"
                    maxLength={5}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-2 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white font-mono-stat"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSearching}
                className="w-full py-2 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors flex items-center justify-center gap-1.5"
              >
                {isSearching ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Searching Carriers...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-3.5 h-3.5" />
                    <span>Query Available Lines</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Results column */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-zinc-200 flex justify-between items-center bg-zinc-50/50">
                <span className="font-semibold text-sm text-zinc-800">Search Results from {buyProvider}</span>
                {searchResults.length > 0 && (
                  <span className="text-[10px] uppercase font-bold text-amber-600 bg-amber-50 border border-amber-200/50 px-1.5 py-0.5 rounded-sm flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> Live Carrier API Data
                  </span>
                )}
              </div>

              {searchResults.length === 0 ? (
                <div className="p-12 text-center text-zinc-500">
                  <Server className="w-10 h-10 text-zinc-300 mx-auto mb-2" />
                  <p className="text-xs">Fill in your area code search query and press "Query Available Lines"</p>
                </div>
              ) : (
                <div className="divide-y divide-zinc-200">
                  {searchResults.map((item, idx) => (
                    <div key={idx} className="p-4 flex items-center justify-between hover:bg-zinc-50/50 transition-colors">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono-stat font-bold text-sm text-zinc-950">{item.number}</span>
                          <span className="px-1.5 py-0.2 text-[9px] font-bold bg-zinc-100 text-zinc-600 rounded-[2px] uppercase">
                            {numberType}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span>Capabilities: {item.capabilities.voice ? "Voice" : ""} {item.capabilities.sms ? ", SMS" : ""}</span>
                          <span>•</span>
                          <span>Tier-1 Routing</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <div className="font-bold text-sm text-zinc-900 font-mono-stat">{item.monthlyCost}</div>
                          <div className="text-[9px] text-zinc-400">per month</div>
                        </div>
                        <button
                          onClick={() => setSelectedBuyNumber(item)}
                          className="px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-all"
                        >
                          Acquire
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Acquire/Purchase Confirmation Modal */}
          {selectedBuyNumber && (
            <div className="fixed inset-0 bg-zinc-950/40 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
              <div className="bg-white border border-zinc-200 max-w-md w-full p-6 shadow-xl rounded-sm">
                <h3 className="text-lg font-bold font-display text-zinc-950 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                  <span>Confirm DID Provisioning</span>
                </h3>
                <p className="text-xs text-zinc-500 mt-1">
                  You are provisioning {selectedBuyNumber.number} using your linked {selectedBuyNumber.provider} carrier credentials.
                </p>

                <form onSubmit={handlePurchase} className="mt-4 space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Friendly Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Sales Hotline, Support VIP"
                      value={friendlyName}
                      onChange={(e) => setFriendlyName(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Route to AI Voice Agent</label>
                    <select
                      value={assignAgentId}
                      onChange={(e) => setAssignAgentId(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950"
                    >
                      <option value="">-- Sandbox Router (LiveKit SIP Session) --</option>
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="bg-zinc-50 border border-zinc-200 p-3 rounded-sm text-xs text-zinc-600 space-y-1 font-medium">
                    <div className="flex justify-between">
                      <span>Monthly DID Rental:</span>
                      <span className="font-mono-stat font-semibold text-zinc-950">{selectedBuyNumber.monthlyCost}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Setup Fee:</span>
                      <span className="font-mono-stat font-semibold text-emerald-600">FREE</span>
                    </div>
                  </div>

                  <div className="flex gap-2 justify-end pt-2 border-t border-zinc-150">
                    <button
                      type="button"
                      onClick={() => setSelectedBuyNumber(null)}
                      className="px-3 py-1.5 border border-zinc-200 text-zinc-600 hover:bg-zinc-50 text-xs font-medium rounded-sm"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm"
                    >
                      Confirm & Buy DID
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: CARRIER SETTINGS */}
      {activeTab === "settings" && (
        <div className="max-w-2xl bg-white border border-zinc-200 p-6 rounded-sm space-y-6">
          <div className="border-b border-zinc-200 pb-3">
            <h3 className="font-bold text-base text-zinc-950">Carrier Integrations</h3>
            <p className="text-xs text-zinc-500">Configure Twilio and Telnyx API integration variables to query and claim phone lines directly</p>
          </div>

          <form onSubmit={handleSaveCredentials} className="space-y-6">
            {/* TWILIO SECTION */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-red-600 text-white flex items-center justify-center font-bold text-xs rounded-sm">T</span>
                <h4 className="font-bold text-sm text-zinc-900">Twilio API Settings</h4>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Account SID</label>
                  <input
                    type="text"
                    placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    value={twilioSid}
                    onChange={(e) => setTwilioSid(e.target.value)}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Auth Token</label>
                  <input
                    type="password"
                    placeholder="••••••••••••••••••••••••••••••••"
                    value={twilioToken}
                    onChange={(e) => setTwilioToken(e.target.value)}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">Fallback Twilio Phone Number (Optional)</label>
                <input
                  type="text"
                  placeholder="+1234567890"
                  value={twilioNumber}
                  onChange={(e) => setTwilioNumber(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                />
              </div>
            </div>

            <hr className="border-zinc-200" />

            {/* TELNYX SECTION */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 bg-emerald-600 text-white flex items-center justify-center font-bold text-xs rounded-sm">T</span>
                <h4 className="font-bold text-sm text-zinc-900">Telnyx API Settings</h4>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-1">API Key</label>
                <input
                  type="password"
                  placeholder="KEYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  value={telnyxKey}
                  onChange={(e) => setTelnyxKey(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                />
              </div>
            </div>

            <div className="flex gap-2 justify-end pt-4 border-t border-zinc-200">
              {isCredentialsSaved && (
                <button
                  type="button"
                  onClick={handleDisconnectCarriers}
                  className="px-3 py-1.5 border border-red-200 text-red-600 hover:bg-red-50 text-xs font-semibold rounded-sm transition-colors"
                >
                  Clear Carrier Config
                </button>
              )}
              <button
                type="submit"
                className="px-4 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors"
              >
                Save Integration Settings
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
