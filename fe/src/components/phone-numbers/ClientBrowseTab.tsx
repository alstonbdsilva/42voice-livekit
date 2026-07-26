import React, { useState } from "react";
import { Search, Server, Check, CheckCircle, HelpCircle } from "lucide-react";
import AppModal from "@/components/AppModal";

interface ClientBrowseTabProps {
  availableNumbers: any[];
  agents: any[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  onPurchase: (id: string, friendlyName: string, agentId: string) => Promise<void>;
}

export function ClientBrowseTab({
  availableNumbers,
  agents,
  searchQuery,
  setSearchQuery,
  onPurchase
}: ClientBrowseTabProps) {
  const [selectedNumber, setSelectedNumber] = useState<any | null>(null);
  const [friendlyName, setFriendlyName] = useState("");
  const [agentId, setAgentId] = useState("");
  const [loading, setLoading] = useState(false);

  const handleOpenPurchase = (num: any) => {
    setSelectedNumber(num);
    setFriendlyName(num.name || "");
    setAgentId("");
  };

  const handleConfirmPurchase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedNumber) return;

    setLoading(true);
    onPurchase(selectedNumber.id, friendlyName.trim(), agentId)
      .then(() => {
        setSelectedNumber(null);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
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

      {availableNumbers.length === 0 ? (
        <div className="border border-zinc-200 bg-white p-12 text-center rounded-sm">
          <Server className="w-10 h-10 text-zinc-350 mx-auto mb-2" />
          <p className="text-xs text-zinc-500 font-medium">All numbers sold or none are currently registered by superadmin.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {availableNumbers.map((item) => (
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
                  {item.capabilities?.voice && (
                    <span className="px-1.5 py-0.2 bg-zinc-50 border border-zinc-200 text-zinc-600 rounded-sm text-[9px] uppercase font-bold tracking-wider">Voice</span>
                  )}
                  {item.capabilities?.sms && (
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
                  onClick={() => handleOpenPurchase(item)}
                  className="px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-all"
                >
                  Buy Line
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* PURCHASE CONFIRMATION OVERLAY MODAL */}
      <AppModal
        open={!!selectedNumber}
        onClose={() => setSelectedNumber(null)}
        title="Purchase DID Line"
        description={`Confirm acquisition of number ${selectedNumber?.number}`}
        maxWidth="sm:max-w-[420px]"
        confirmLabel={loading ? "Purchasing..." : "Confirm Purchase"}
        onConfirm={() => {
          const btn = document.getElementById("submit-purchase-btn");
          if (btn) btn.click();
        }}
        loading={loading}
        showFooter={false}
      >
        {selectedNumber && (
          <form onSubmit={handleConfirmPurchase} className="space-y-4 text-xs">
            <p className="text-zinc-500 leading-relaxed">
              You are purchasing the phone number <strong className="font-mono text-zinc-900">{selectedNumber.number}</strong>. This line will route incoming SIP trunk calls to your 42Voice dashboard.
            </p>
            
            {/* Friendly Name */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600 mb-1">Friendly Name / Label</label>
              <input
                type="text"
                required
                value={friendlyName}
                onChange={(e) => setFriendlyName(e.target.value)}
                className="w-full bg-zinc-50 border border-zinc-200 rounded-sm px-2.5 py-1.5 focus:outline-none focus:border-zinc-950 text-xs"
                placeholder="e.g. Main Support Line"
              />
            </div>

            {/* AI Agent Association */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-600">Connect AI Agent (Optional)</label>
                <span className="text-[9px] text-zinc-400 flex items-center gap-0.5">
                  <HelpCircle className="w-3 h-3" /> Can route later
                </span>
              </div>
              <select
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                className={`w-full border rounded-sm px-2 py-1.5 text-xs focus:outline-none focus:border-zinc-950 font-medium ${
                  agentId 
                    ? "bg-zinc-50 border-zinc-200 text-zinc-800" 
                    : "bg-red-50 border-red-300 text-red-600"
                }`}
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
            <div className="bg-zinc-50 border border-zinc-150 p-3 rounded-sm space-y-1.5 font-mono text-[11px] text-zinc-650">
              <div className="flex justify-between">
                <span>Monthly Recurring:</span>
                <span className="font-bold text-zinc-900">{selectedNumber.monthlyCost}</span>
              </div>
              <div className="flex justify-between">
                <span>One-Time Setup:</span>
                <span className="font-bold text-zinc-900">{selectedNumber.setupCost}</span>
              </div>
            </div>

            {/* Form actions */}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedNumber(null)}
                className="px-3 py-1.5 border border-zinc-200 hover:bg-zinc-50 text-zinc-700 text-xs font-semibold rounded-sm bg-white"
              >
                Cancel
              </button>
              <button
                id="submit-purchase-btn"
                type="submit"
                className="px-3 py-1.5 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm shadow-xs"
              >
                Confirm Purchase
              </button>
            </div>
          </form>
        )}
      </AppModal>
    </div>
  );
}

export default ClientBrowseTab;
