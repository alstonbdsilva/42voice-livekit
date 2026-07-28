import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { 
  ArrowLeft, Phone, Info, Shield, Check, Server,
  Lock, Settings, HelpCircle, ToggleLeft, ToggleRight, Sparkles,
  Users, Globe, DollarSign, Search, PlusCircle, RefreshCw, AlertCircle
} from "lucide-react";
import ClientService from "@/services/client.service";
import ResellerService from "@/services/reseller.service";
import TwilioService from "@/services/twilio.service";
import PhoneNumberService from "@/services/phone-number.service";
import { Client, Reseller } from "@/types";

interface SIPConfig {
  domain: string;
  authUsername: string;
  password?: string;
  proxy: string;
  outboundProxy: string;
  useOutboundProxy: boolean;
  registerExpires: number;
  natKeepAlive: number;
  dtmfMode: "RFC2833" | "inband";
  preferredCodec: "G.711a" | "G.711u" | "G.722" | "G.729a" | "GSM";
  secondaryCodec: "G.711a" | "G.711u" | "G.722" | "G.729a" | "GSM";
  t38Support: boolean;
  echoCancellation: boolean;
  silenceSuppression: boolean;
}

export default function AddPhoneNumber() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState<"Twilio" | "CITL">("CITL");
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [monthlyCost, setMonthlyCost] = useState("");
  const [setupCost, setSetupCost] = useState("");
  const [voiceCapable, setVoiceCapable] = useState(true);
  const [smsCapable, setSmsCapable] = useState(true);
  const [isActivating, setIsActivating] = useState(false);

  // Allocation states
  const [allocation, setAllocation] = useState<"pool" | "me" | "client" | "reseller">("pool");
  const [assignedId, setAssignedId] = useState("");
  const [clients, setClients] = useState<Client[]>([]);
  const [resellers, setResellers] = useState<Reseller[]>([]);



  // SIP configs
  const [sipConfig, setSipConfig] = useState<SIPConfig>({
    domain: "",
    authUsername: "",
    password: "",
    proxy: "",
    outboundProxy: "",
    useOutboundProxy: true,
    registerExpires: 600,
    natKeepAlive: 60,
    dtmfMode: "RFC2833",
    preferredCodec: "G.711a",
    secondaryCodec: "G.711u",
    t38Support: true,
    echoCancellation: true,
    silenceSuppression: false
  });

  // Pre-populate if query parameters are present
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const numParam = params.get("number");
    const providerParam = params.get("provider");
    const nameParam = params.get("name");
    if (numParam) setNumber(numParam);
    if (providerParam === "Twilio" || providerParam === "CITL") setProvider(providerParam);
    if (nameParam) setName(nameParam);

    // Fetch clients & resellers
    ClientService.getAll()
      .then(setClients)
      .catch(() => {});
    ResellerService.getAll()
      .then(setResellers)
      .catch(() => {});
  }, []);

  // Pre-populate fields based on provider choice according to official guidelines
  useEffect(() => {
    if (provider === "CITL") {
      setSipConfig(prev => ({
        ...prev,
        domain: prev.domain || "",
        authUsername: prev.authUsername || "",
        password: prev.password || "",
        proxy: prev.proxy || "",
        outboundProxy: prev.outboundProxy || "",
        useOutboundProxy: true,
        registerExpires: 600,
        natKeepAlive: 60,
        dtmfMode: "RFC2833",
        preferredCodec: "G.711a", // G.711a (alaw) preferred for CITL/2talk
        secondaryCodec: "G.711u", // G.711u (ulaw) secondary
        t38Support: true,
        echoCancellation: true,
        silenceSuppression: false
      }));
    } else {
      // Twilio Elastic SIP Trunking / SIP Domain Defaults
      setSipConfig(prev => ({
        ...prev,
        domain: prev.domain || "",
        authUsername: prev.authUsername || "",
        password: prev.password || "",
        proxy: prev.proxy || "",
        outboundProxy: prev.outboundProxy || "",
        useOutboundProxy: false, // Twilio registration doesn't require outbound proxy
        registerExpires: 3600, // Twilio recommends 3600 seconds (1 hour)
        natKeepAlive: 30, // Keep-alive standard for Twilio is 30s
        dtmfMode: "RFC2833", // Twilio standard DTMF mode
        preferredCodec: "G.711u", // G.711u (ulaw) preferred for Twilio/US carriers
        secondaryCodec: "G.711a", // G.711a (alaw) secondary
        t38Support: false, // Twilio doesn't support T.38 on standard SIP trunks
        echoCancellation: true,
        silenceSuppression: false
      }));
    }
  }, [provider]);

  // Keep authorization username in sync with number unless manually edited
  useEffect(() => {
    if (!sipConfig.authUsername || sipConfig.authUsername === number) {
      setSipConfig(prev => ({
        ...prev,
        authUsername: number
      }));
    }
  }, [number]);

  const handleSipChange = (key: keyof SIPConfig, value: any) => {
    setSipConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };



  const handleRegister = (statusOverride?: "pending_sip" | "inactive") => {
    if (!number.trim()) {
      toast.error("Please enter a valid phone number.");
      return;
    }

    if ((allocation === "client" || allocation === "reseller") && !assignedId) {
      toast.error("Please select a specific Client or Reseller to assign this number.");
      return;
    }

    setIsActivating(true);

    // Call PhoneNumberService to register number on backend and provision LiveKit
    PhoneNumberService.register({
      number: number.trim(),
      name: name.trim() || `${provider} DID Line`,
      provider: provider,
      monthlyCost: parseFloat(monthlyCost) || 0,
      setupCost: parseFloat(setupCost) || 0,
      capabilities: { voice: voiceCapable, sms: smsCapable },
      sipConfig: sipConfig,
      allocation: allocation,
      assignedId: assignedId || undefined,
      draft: !!statusOverride
    })
      .then((res) => {
        setIsActivating(false);
        const warning = res?.data?.warning || res?.warning;
        if (warning) {
          toast.warning(`Registered but LiveKit warning: ${warning}`);
        } else {
          toast.success(`DID ${number} registered and provisioned successfully!`);
        }
        navigate("/phone-numbers");
      })
      .catch((err) => {
        setIsActivating(false);
        const errMsg = err?.response?.data?.message || err?.message || "Failed to register number.";
        toast.error(`Registration failed: ${errMsg}`);
      });
  };

  return (
    <div className="space-y-6 w-full" data-testid="add-phone-number-page">
      <div className="flex items-center justify-between border-b border-zinc-200 pb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/phone-numbers")}
            className="p-1.5 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 rounded-sm transition-colors bg-white shadow-xs"
            title="Back to Phone Numbers"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-zinc-950 font-display">Register & Provision DID</h1>
            <p className="text-xs text-zinc-500 font-medium">Add numbers, declare customer pricing, configure availability and connect SIP routing</p>
          </div>
        </div>
      </div>



      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">
        
        {/* Left Column: Number Details */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white border border-zinc-200 p-5 rounded-sm space-y-4 shadow-xs">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 border-b border-zinc-100 pb-2">Line Settings</h3>

            {/* Provider Selection */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-2">Provider Carrier</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setProvider("CITL")}
                  className={`py-2.5 px-3 text-xs border rounded-sm flex flex-col items-center gap-1 transition-all ${
                    provider === "CITL"
                      ? "bg-zinc-950 border-zinc-950 text-white font-bold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  <span className="text-xs font-semibold">CITL Carrier</span>
                  <span className={`text-[9px] ${provider === "CITL" ? "text-zinc-300" : "text-zinc-400"}`}>c-tel.co.nz (2talk)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setProvider("Twilio")}
                  className={`py-2.5 px-3 text-xs border rounded-sm flex flex-col items-center gap-1 transition-all ${
                    provider === "Twilio"
                      ? "bg-red-600 border-red-700 text-white font-bold"
                      : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                  }`}
                >
                  <span className="text-xs font-semibold">Twilio Cloud</span>
                  <span className={`text-[9px] ${provider === "Twilio" ? "text-red-200" : "text-zinc-400"}`}>twilio.com SIP</span>
                </button>
              </div>
            </div>

            {/* Phone Number Input */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Phone Number (E.164 format)</label>
              <div className="relative">
                <Phone className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input
                  type="text"
                  required
                  placeholder={provider === "CITL" ? "e.g. +64 9 888 1234" : "e.g. +1 (855) 428-6423"}
                  value={number}
                  onChange={(e) => setNumber(e.target.value)}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white font-mono"
                />
              </div>
              {(() => {
                const cleanNum = number.replace(/[\s\-\(\)]/g, "");
                const match = cleanNum.match(/^\+(\d{1,3})0(\d+)/);
                if (match) {
                  const countryCode = match[1];
                  const suggested = `+${countryCode}${cleanNum.substring(countryCode.length + 2)}`;
                  return (
                    <div className="mt-1.5 p-2 bg-amber-50/80 border border-amber-200/60 rounded-sm flex items-start gap-2">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5 animate-bounce" />
                      <div className="text-[10px] text-amber-700 leading-normal">
                        <strong>Formatting Alert:</strong> E.164 standard formats omit the local trunk prefix <code>0</code>. Use <strong>{suggested}</strong> instead of <strong>{cleanNum}</strong> (the system will normalize this automatically).
                      </div>
                    </div>
                  );
                }
                return null;
              })()}
            </div>

            {/* Name Input */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Friendly Label / Name</label>
              <input
                type="text"
                placeholder="e.g. Main Support Trunk"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white"
              />
            </div>

            {/* Lease Allocation Selection */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1.5">DID Availability & Lease Allocation</label>
              <select
                value={allocation}
                onChange={(e) => {
                  setAllocation(e.target.value as any);
                  setAssignedId("");
                }}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-2 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white font-medium text-zinc-800"
              >
                <option value="pool">🌐 Publish to Public Pool (Available to Rent)</option>
                <option value="me">💼 Assign to Me (Superadmin Internal Use)</option>
                <option value="client">🏢 Pre-assign directly to a specific Client</option>
                <option value="reseller">🤝 Pre-assign directly to a Reseller Partner</option>
              </select>

              {/* Sub-selectors for Client/Reseller assignment */}
              {allocation === "client" && (
                <div className="mt-2.5 space-y-1">
                  <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider font-semibold">Select Client</span>
                  <select
                    value={assignedId}
                    onChange={(e) => setAssignedId(e.target.value)}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                  >
                    <option value="">-- Choose Client --</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {allocation === "reseller" && (
                <div className="mt-2.5 space-y-1">
                  <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider font-semibold">Select Reseller Partner</span>
                  <select
                    value={assignedId}
                    onChange={(e) => setAssignedId(e.target.value)}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                  >
                    <option value="">-- Choose Reseller --</option>
                    {resellers.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Pricing Section */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1.5">End-User Pricing (USD)</label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-zinc-400 font-medium">Monthly Rent</span>
                  <div className="relative mt-1">
                    <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={monthlyCost}
                      onChange={(e) => setMonthlyCost(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-6 pr-2 py-1 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white font-mono font-medium"
                    />
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-medium">Setup Fee</span>
                  <div className="relative mt-1">
                    <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={setupCost}
                      onChange={(e) => setSetupCost(e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-6 pr-2 py-1 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white font-mono font-medium"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Capabilities */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1.5">Capabilities</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-1.5 text-xs text-zinc-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={voiceCapable}
                    onChange={(e) => setVoiceCapable(e.target.checked)}
                    className="rounded-sm border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5"
                  />
                  <span>Voice Calling</span>
                </label>
                <label className="flex items-center gap-1.5 text-xs text-zinc-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={smsCapable}
                    onChange={(e) => setSmsCapable(e.target.checked)}
                    className="rounded-sm border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5"
                  />
                  <span>SMS Texts</span>
                </label>
              </div>
            </div>
          </div>

          <div className="bg-zinc-50 border border-zinc-200 p-4 rounded-sm space-y-2 shadow-xs">
            <div className="flex items-center gap-2 text-zinc-700 font-semibold text-xs">
              <Shield className="w-4 h-4 text-zinc-500" />
              <span>DID Activation Rules</span>
            </div>
            <p className="text-[11px] text-zinc-650 leading-relaxed">
              If SIP connection parameters are complete, click <strong>Register & Activate DID</strong>. If you are waiting on carrier details, you can save as draft to keep the line record offline.
            </p>
          </div>
        </div>

        {/* Right Column: SIP & LiveKit configuration parameters */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white border border-zinc-200 p-5 rounded-sm space-y-5 shadow-xs">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5">
              <h3 className="text-sm font-bold text-zinc-950 flex items-center gap-1.5">
                <Server className="w-4 h-4 text-zinc-500" />
                <span>Carrier Connection Details</span>
              </h3>
              <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                <Lock className="w-3 h-3" /> Production Grade Config
              </span>
            </div>

            {/* Provider Instructions Alert Box */}
            <div className="bg-blue-50/50 border border-blue-200 p-3.5 rounded-sm text-xs text-blue-950 flex gap-2.5">
              <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold mb-0.5 text-xs text-blue-950">Official Carrier Settings ({provider})</p>
                {provider === "CITL" ? (
                  <div className="text-blue-900 leading-relaxed text-[11px] space-y-1">
                    <p>CITL routing credentials are provided by 2talk. Pre-populated variables correspond to 2talk guidelines:</p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      <li>Domain / Realm, Proxy, Outbound Proxy defaults to <code>phone.c-tel.co.nz</code></li>
                      <li>Register Expiry set to <strong>600s</strong>; Keep-Alive to <strong>60s</strong></li>
                      <li>Preferred audio codec is <strong>G.711a (alaw)</strong></li>
                    </ul>
                  </div>
                ) : (
                  <div className="text-blue-900 leading-relaxed text-[11px] space-y-1">
                    <p>Twilio registers calls using Elastic SIP domains:</p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      <li>Domain / Realm should map to <code>&lt;your-domain&gt;.sip.twilio.com</code></li>
                      <li>Proxy registrar resolves directly to <code>sip.twilio.com</code></li>
                      <li>Register Expiry set to Twilio standard <strong>3600s (1 hour)</strong></li>
                      <li>Preferred audio codec is <strong>G.711u (ulaw)</strong></li>
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {provider === "Twilio" ? (
              <div className="space-y-4">
                <div className="bg-red-50/50 border border-red-200 p-3.5 rounded-sm text-xs text-red-950 flex gap-2.5">
                  <Info className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold mb-0.5 text-xs text-red-950">Twilio Account Authentication</p>
                    <p className="text-red-900 leading-relaxed text-[11px]">
                      Enter your Twilio API credentials to authorize outbound calling and automatic call routing configuration for this phone number.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Twilio Account SID */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Twilio Account SID</label>
                    <input
                      type="text"
                      placeholder="e.g. Your Twilio Account SID"
                      value={sipConfig.authUsername}
                      onChange={(e) => handleSipChange("authUsername", e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Twilio Auth Token */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Twilio Auth Token</label>
                    <input
                      type="password"
                      placeholder="••••••••••••••••••••••••••••••••"
                      value={sipConfig.password}
                      onChange={(e) => handleSipChange("password", e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Domain / Realm */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Domain / Realm / Registrar Domain</label>
                    <input
                      type="text"
                      placeholder="phone.c-tel.co.nz"
                      value={sipConfig.domain}
                      onChange={(e) => handleSipChange("domain", e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Proxy */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">SIP Proxy Host</label>
                    <input
                      type="text"
                      placeholder="phone.c-tel.co.nz"
                      value={sipConfig.proxy}
                      onChange={(e) => handleSipChange("proxy", e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Username */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">
                      SIP Auth Username / ID (Login ID)
                    </label>
                    <input
                      type="text"
                      placeholder={number ? number : "e.g. +6498881234"}
                      value={sipConfig.authUsername}
                      onChange={(e) => handleSipChange("authUsername", e.target.value)}
                      autoComplete="new-password"
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Password */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">SIP Auth Password</label>
                    <input
                      type="password"
                      placeholder="••••••••••••"
                      value={sipConfig.password}
                      onChange={(e) => handleSipChange("password", e.target.value)}
                      autoComplete="new-password"
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Outbound Proxy */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Outbound Proxy (Leave empty if none)</label>
                    <input
                      type="text"
                      placeholder="e.g. phone.c-tel.co.nz"
                      value={sipConfig.outboundProxy}
                      onChange={(e) => handleSipChange("outboundProxy", e.target.value)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* Outbound toggle */}
                  <div className="flex items-center justify-between border border-zinc-150 p-2 rounded-sm">
                    <div>
                      <span className="block text-xs font-semibold text-zinc-900">Use Outbound Proxy</span>
                      <span className="text-[10px] text-zinc-400 font-medium font-semibold">CITL: Yes</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSipChange("useOutboundProxy", !sipConfig.useOutboundProxy)}
                      className="text-zinc-650 focus:outline-none transition-colors"
                    >
                      {sipConfig.useOutboundProxy ? (
                        <ToggleRight className="w-8 h-8 text-zinc-950" />
                      ) : (
                        <ToggleLeft className="w-8 h-8 text-zinc-200" />
                      )}
                    </button>
                  </div>

                  {/* Registration Expiry */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Register Expires (Seconds)</label>
                    <input
                      type="number"
                      value={sipConfig.registerExpires}
                      onChange={(e) => handleSipChange("registerExpires", parseInt(e.target.value) || 0)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>

                  {/* NAT Keep alive */}
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">NAT Keep-Alive (Seconds)</label>
                    <input
                      type="number"
                      value={sipConfig.natKeepAlive}
                      onChange={(e) => handleSipChange("natKeepAlive", parseInt(e.target.value) || 0)}
                      className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
                    />
                  </div>
                </div>

                <hr className="border-zinc-200" />

                {/* Extra Audio/Device Settings */}
                <div className="space-y-4">
                  <h4 className="text-xs font-bold text-zinc-900 flex items-center gap-1">
                    <Settings className="w-3.5 h-3.5 text-zinc-500" />
                    <span>Media Signals & Codecs</span>
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* DTMF Mode */}
                    <div>
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">DTMF Signaling</label>
                      <select
                        value={sipConfig.dtmfMode}
                        onChange={(e) => handleSipChange("dtmfMode", e.target.value)}
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-1.5 text-xs focus:outline-none focus:border-zinc-950"
                      >
                        <option value="RFC2833">RFC2833 (AVT Out-of-band)</option>
                        <option value="inband">Inband (Recommended for Alarm/Fax)</option>
                      </select>
                    </div>

                    {/* Preferred Codec */}
                    <div>
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Preferred Codec</label>
                      <select
                        value={sipConfig.preferredCodec}
                        onChange={(e) => handleSipChange("preferredCodec", e.target.value)}
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium"
                      >
                        <option value="G.711a">G.711a (alaw) - CITL Standard</option>
                        <option value="G.711u">G.711u (ulaw)</option>
                        <option value="G.722">G.722 (HD Audio)</option>
                        <option value="G.729a">G.729a</option>
                        <option value="GSM">GSM</option>
                      </select>
                    </div>

                    {/* Secondary Codec */}
                    <div>
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">Secondary Codec</label>
                      <select
                        value={sipConfig.secondaryCodec}
                        onChange={(e) => handleSipChange("secondaryCodec", e.target.value)}
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-sm p-1.5 text-xs focus:outline-none focus:border-zinc-950"
                      >
                        <option value="G.711u">G.711u (ulaw)</option>
                        <option value="G.711a">G.711a (alaw)</option>
                        <option value="G.722">G.722 (HD Audio)</option>
                        <option value="G.729a">G.729a</option>
                        <option value="GSM">GSM</option>
                      </select>
                    </div>
                  </div>

                  {/* Toggles */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                    <label className="flex items-center gap-2 p-2.5 border border-zinc-150 bg-zinc-50/50 rounded-sm cursor-pointer hover:bg-zinc-50 transition-colors">
                      <input
                        type="checkbox"
                        checked={sipConfig.t38Support}
                        onChange={(e) => handleSipChange("t38Support", e.target.checked)}
                        className="rounded-sm border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5"
                      />
                      <div>
                        <span className="block text-xs font-semibold text-zinc-800">T.38 Fax Support</span>
                        <span className="text-[9px] text-zinc-400">Re-route alarm & faxes</span>
                      </div>
                    </label>

                    <label className="flex items-center gap-2 p-2.5 border border-zinc-150 bg-zinc-50/50 rounded-sm cursor-pointer hover:bg-zinc-50 transition-colors">
                      <input
                        type="checkbox"
                        checked={sipConfig.echoCancellation}
                        onChange={(e) => handleSipChange("echoCancellation", e.target.checked)}
                        className="rounded-sm border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5"
                      />
                      <div>
                        <span className="block text-xs font-semibold text-zinc-800">Echo Cancellation</span>
                        <span className="text-[9px] text-zinc-400">Reduce feedback audio</span>
                      </div>
                    </label>

                    <label className="flex items-center gap-2 p-2.5 border border-zinc-150 bg-zinc-50/50 rounded-sm cursor-pointer hover:bg-zinc-50 transition-colors">
                      <input
                        type="checkbox"
                        checked={sipConfig.silenceSuppression}
                        onChange={(e) => handleSipChange("silenceSuppression", e.target.checked)}
                        className="rounded-sm border-zinc-300 text-zinc-900 focus:ring-zinc-900 w-3.5 h-3.5"
                      />
                      <div>
                        <span className="block text-xs font-semibold text-zinc-800">Silence Suppression</span>
                        <span className="text-[9px] text-zinc-400">Disable VAD packets</span>
                      </div>
                    </label>
                  </div>
                </div>
              </>
            )}

            {/* Actions Bar */}
            <div className="flex gap-2 justify-end pt-4 border-t border-zinc-200">
              <button
                type="button"
                onClick={() => navigate("/phone-numbers")}
                className="px-3.5 py-1.5 border border-zinc-200 text-zinc-600 hover:bg-zinc-50 text-xs font-semibold rounded-sm transition-colors bg-white shadow-xs"
              >
                Cancel
              </button>
              
              <button
                type="button"
                onClick={() => handleRegister("pending_sip")}
                className="px-3.5 py-1.5 border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 text-xs font-semibold rounded-sm transition-colors flex items-center gap-1.5 shadow-xs"
              >
                Save as Draft
              </button>

              <button
                type="button"
                disabled={isActivating}
                onClick={() => handleRegister()}
                className="px-4 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors flex items-center gap-1.5 shadow-sm"
              >
                {isActivating ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Activating DID...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Register & Activate DID</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
