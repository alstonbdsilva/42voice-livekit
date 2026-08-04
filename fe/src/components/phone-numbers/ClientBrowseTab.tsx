import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Search, Server, Globe, Loader2, HelpCircle } from "lucide-react";
import { toast } from "sonner";
import AppModal from "@/components/AppModal";
import PhoneNumberService from "@/services/phone-number.service";

interface ClientBrowseTabProps {
  availableNumbers: any[];
  agents: any[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  onPurchase: (id: string, friendlyName: string, agentId: string) => Promise<void>;
}

// Supported Countries List
const COUNTRIES = [
  { code: "US", name: "United States", flag: "🇺🇸", prefix: "+1" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧", prefix: "+44" },
  { code: "CA", name: "Canada", flag: "🇨🇦", prefix: "+1" },
  { code: "AU", name: "Australia", flag: "🇦🇺", prefix: "+61" },
  { code: "IN", name: "India", flag: "🇮🇳", prefix: "+91" },
  { code: "DE", name: "Germany", flag: "🇩🇪", prefix: "+49" },
  { code: "FR", name: "France", flag: "🇫🇷", prefix: "+33" },
  { code: "ES", name: "Spain", flag: "🇪🇸", prefix: "+34" },
  { code: "MX", name: "Mexico", flag: "🇲🇽", prefix: "+52" },
  { code: "BR", name: "Brazil", flag: "🇧🇷", prefix: "+55" },
];

export function ClientBrowseTab({
  availableNumbers,
  agents,
  searchQuery,
  setSearchQuery,
  onPurchase
}: ClientBrowseTabProps) {
  // Search Parameters
  const [selectedCountry, setSelectedCountry] = useState<string>("US");
  const [areaCode, setAreaCode] = useState<string>("");
  const [numberType, setNumberType] = useState<"Local" | "TollFree">("Local");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [smsEnabled, setSmsEnabled] = useState(true);

  // Backend Live Results State
  const [backendResults, setBackendResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Purchase Modal state
  const [selectedNumber, setSelectedNumber] = useState<any | null>(null);
  const [friendlyName, setFriendlyName] = useState("");
  const [agentId, setAgentId] = useState("");
  const [purchasing, setPurchasing] = useState(false);

  // Backend API Call function
  const fetchAvailableNumbers = useCallback(async () => {
    setIsSearching(true);
    try {
      const res = await PhoneNumberService.getAvailable(selectedCountry, numberType, areaCode.trim() || undefined);
      if (Array.isArray(res) && res.length > 0) {
        setBackendResults(res);
      } else {
        setBackendResults([]);
      }
    } catch (err) {
      console.error("Failed to fetch available numbers from backend API", err);
      setBackendResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [selectedCountry, numberType, areaCode]);

  // Fetch when filters change
  useEffect(() => {
    fetchAvailableNumbers();
  }, [fetchAvailableNumbers]);

  // Dynamic Numbers for Display (100% backend API results)
  const displayNumbers = useMemo(() => {
    const countryObj = COUNTRIES.find((c) => c.code === selectedCountry) || COUNTRIES[0];

    const sourceList = backendResults.length > 0 ? backendResults : availableNumbers;

    return sourceList
      .map((item: any, idx: number) => ({
        id: item.id || item.phone_number || `be-${idx}`,
        number: item.friendly_name || item.number || item.phone_number,
        country: item.country || selectedCountry,
        countryName: item.countryName || countryObj.name,
        flag: item.flag || countryObj.flag,
        location: item.location || (item.locality ? `${item.locality}, ${item.region || ""}`.trim() : (item.name || countryObj.name)),
        type: item.type || numberType,
        provider: item.provider || "Twilio",
        monthlyCost: item.monthlyCost || "$0.00",
        setupCost: item.setupCost || "$0.00",
        capabilities: item.capabilities || { voice: true, sms: true }
      }))
      .filter((item: any) => {
        const matchesCountry = !selectedCountry || item.country === selectedCountry;
        const matchesType = !numberType || item.type.toLowerCase() === numberType.toLowerCase();
        const matchesAreaCode = !areaCode.trim() || item.number?.includes(areaCode.trim());
        const matchesVoice = !voiceEnabled || item.capabilities?.voice;
        const matchesSms = !smsEnabled || item.capabilities?.sms;

        const q = searchQuery.toLowerCase();
        const matchesSearch = !q || item.number?.toLowerCase().includes(q) || item.location?.toLowerCase().includes(q);

        return matchesCountry && matchesType && matchesAreaCode && matchesVoice && matchesSms && matchesSearch;
      });
  }, [backendResults, availableNumbers, selectedCountry, numberType, areaCode, voiceEnabled, smsEnabled, searchQuery]);

  const handleOpenPurchase = (num: any) => {
    setSelectedNumber(num);
    setFriendlyName(num.location || num.name || num.number);
    setAgentId("");
  };

  const handleConfirmPurchase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedNumber) return;

    setPurchasing(true);
    onPurchase(selectedNumber.id, friendlyName.trim(), agentId)
      .then(() => {
        setSelectedNumber(null);
        toast.success(`Purchased number ${selectedNumber.number} successfully!`);
      })
      .catch((err) => {
        toast.error(err.message || "Purchase failed.");
      })
      .finally(() => {
        setPurchasing(false);
      });
  };

  return (
    <div className="space-y-6" data-testid="client-browse-tab">
      {/* SEARCH FILTERS TOOLBAR */}
      <div className="bg-white border border-zinc-200 p-4 rounded-sm space-y-4 shadow-xs">
        <div className="flex justify-between items-center border-b border-zinc-100 pb-3">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-zinc-700" />
            <h3 className="text-xs font-bold text-zinc-950 uppercase tracking-wider">
              Browse Available Telephony Lines
            </h3>
          </div>

          <button
            onClick={fetchAvailableNumbers}
            disabled={isSearching}
            className="flex items-center gap-2 px-4 py-1.5 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm transition-colors shadow-xs disabled:opacity-50"
            data-testid="search-twilio-btn"
          >
            {isSearching ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Searching Backend API...</span>
              </>
            ) : (
              <>
                <Search className="w-3.5 h-3.5" />
                <span>Search Available Lines</span>
              </>
            )}
          </button>
        </div>

        {/* Filter Controls Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {/* Country Selector */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              Select Country <span className="text-red-500">*</span>
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs font-semibold text-zinc-800 focus:outline-none focus:border-zinc-950"
              data-testid="country-select"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.name} ({c.prefix})
                </option>
              ))}
            </select>
          </div>

          {/* Area Code Filter */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              Area Code / Region
            </label>
            <input
              type="text"
              placeholder="e.g. 415, 212, 800..."
              value={areaCode}
              onChange={(e) => setAreaCode(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-mono"
              data-testid="area-code-input"
            />
          </div>

          {/* Number Type */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              Number Type
            </label>
            <select
              value={numberType}
              onChange={(e) => setNumberType(e.target.value as any)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs font-semibold text-zinc-800 focus:outline-none focus:border-zinc-950"
            >
              <option value="Local">Local Line</option>
              <option value="TollFree">Toll-Free Line</option>
            </select>
          </div>

          {/* Filter Keyword */}
          <div className="space-y-1">
            <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500">
              Filter Keyword
            </label>
            <input
              type="text"
              placeholder="Filter by city, number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 text-xs focus:outline-none focus:border-zinc-950"
            />
          </div>
        </div>

        {/* Capability Toggles */}
        <div className="flex items-center gap-4 pt-1 text-xs text-zinc-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Capabilities:</span>
          <label className="flex items-center gap-1.5 cursor-pointer font-medium">
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => setVoiceEnabled(e.target.checked)}
              className="rounded border-zinc-300 text-zinc-950 focus:ring-0"
            />
            <span>Voice Required</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer font-medium">
            <input
              type="checkbox"
              checked={smsEnabled}
              onChange={(e) => setSmsEnabled(e.target.checked)}
              className="rounded border-zinc-300 text-zinc-950 focus:ring-0"
            />
            <span>SMS Required</span>
          </label>
        </div>
      </div>

      {/* NUMBERS CARDS GRID */}
      {isSearching ? (
        <div className="border border-zinc-200 bg-white p-12 text-center rounded-sm space-y-3">
          <Loader2 className="w-8 h-8 text-zinc-800 animate-spin mx-auto" />
          <p className="text-xs font-semibold text-zinc-800">
            Fetching available telephony lines from backend API...
          </p>
        </div>
      ) : displayNumbers.length === 0 ? (
        <div className="border border-zinc-200 bg-white p-12 text-center rounded-sm space-y-2">
          <Server className="w-10 h-10 text-zinc-300 mx-auto" />
          <p className="text-xs font-semibold text-zinc-700">No phone numbers found matching your criteria.</p>
          <p className="text-[11px] text-zinc-400">Try changing the country selection or clearing the area code filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {displayNumbers.map((item: any, idx: number) => (
            <div
              key={item.id || idx}
              className="bg-white border border-zinc-200 p-4 rounded-sm flex flex-col justify-between hover:border-zinc-400 transition-all shadow-xs space-y-4"
              data-testid={`number-card-${item.id}`}
            >
              <div>
                {/* Header: Country Flag & Provider */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">{item.flag || "🌐"}</span>
                    <span className="text-[11px] font-bold text-zinc-800">{item.countryName || item.country}</span>
                    <span className="text-[9px] px-1 py-0.2 bg-zinc-100 text-zinc-600 rounded font-semibold uppercase">
                      {item.type}
                    </span>
                  </div>
                  <span className="inline-block px-1.5 py-0.5 text-[8px] font-bold rounded-sm uppercase tracking-wider bg-red-50 text-red-700 border border-red-200/50">
                    {item.provider || "Twilio"}
                  </span>
                </div>

                {/* Main Phone Number */}
                <h4 className="text-lg font-bold text-zinc-950 font-mono tracking-tight mt-2.5">
                  {item.number}
                </h4>
                <p className="text-[11px] text-zinc-500 font-medium">{item.location || item.name}</p>

                {/* Capability Badges */}
                <div className="flex items-center gap-1.5 mt-3">
                  {item.capabilities?.voice && (
                    <span className="px-1.5 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-sm text-[9px] uppercase font-bold tracking-wider">
                      Voice
                    </span>
                  )}
                  {item.capabilities?.sms && (
                    <span className="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-sm text-[9px] uppercase font-bold tracking-wider">
                      SMS
                    </span>
                  )}
                  {item.capabilities?.mms && (
                    <span className="px-1.5 py-0.5 bg-purple-50 border border-purple-200 text-purple-700 rounded-sm text-[9px] uppercase font-bold tracking-wider">
                      MMS
                    </span>
                  )}
                </div>
              </div>

              {/* Pricing & Purchase Action */}
              <div className="border-t border-zinc-100 pt-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-zinc-950 font-mono-stat">{item.monthlyCost}</div>
                  <div className="text-[9px] text-zinc-400 font-medium">per month</div>
                </div>

                <button
                  onClick={() => handleOpenPurchase(item)}
                  className="px-3.5 py-1.5 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm transition-all shadow-xs"
                >
                  Buy Line
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* PURCHASE OVERLAY MODAL */}
      <AppModal
        open={!!selectedNumber}
        onClose={() => setSelectedNumber(null)}
        title="Purchase Telephony Line"
        description={`Confirm acquisition of number ${selectedNumber?.number}`}
        maxWidth="sm:max-w-[440px]"
        showFooter={false}
      >
        {selectedNumber && (
          <form onSubmit={handleConfirmPurchase} className="space-y-4 text-xs">
            <div className="bg-zinc-50 border border-zinc-200 p-3 rounded-sm space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-base">{selectedNumber.flag}</span>
                <span className="font-bold text-zinc-900 text-sm font-mono">{selectedNumber.number}</span>
              </div>
              <p className="text-[11px] text-zinc-500">
                {selectedNumber.location} • {selectedNumber.countryName} ({selectedNumber.type})
              </p>
            </div>

            {/* Friendly Name */}
            <div className="space-y-1">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600">
                Friendly Name / Label <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={friendlyName}
                onChange={(e) => setFriendlyName(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 text-xs"
                placeholder="e.g. Sales Inbound Hotline"
              />
            </div>

            {/* AI Agent Association */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600">
                  Connect AI Agent (Optional)
                </label>
                <span className="text-[9px] text-zinc-400 flex items-center gap-0.5">
                  <HelpCircle className="w-3 h-3" /> Can route later
                </span>
              </div>
              <select
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                className="w-full border bg-zinc-50 border-zinc-200 rounded-sm px-2 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium text-zinc-800"
              >
                <option value="">-- Unassigned (No Agent) --</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Pricing Summary */}
            <div className="bg-zinc-50 border border-zinc-200 p-3 rounded-sm space-y-1.5 font-mono text-[11px] text-zinc-700">
              <div className="flex justify-between">
                <span>Monthly Recurring:</span>
                <span className="font-bold text-zinc-900">{selectedNumber.monthlyCost}</span>
              </div>
              <div className="flex justify-between">
                <span>One-Time Setup:</span>
                <span className="font-bold text-zinc-900">{selectedNumber.setupCost || "$0.00"}</span>
              </div>
            </div>

            {/* Form actions */}
            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
              <button
                type="button"
                onClick={() => setSelectedNumber(null)}
                className="px-3 py-1.5 border border-zinc-200 hover:bg-zinc-50 text-zinc-700 text-xs font-semibold rounded-sm bg-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={purchasing}
                className="px-3.5 py-1.5 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm shadow-xs"
              >
                {purchasing ? "Processing..." : "Confirm Purchase"}
              </button>
            </div>
          </form>
        )}
      </AppModal>
    </div>
  );
}

export default ClientBrowseTab;
