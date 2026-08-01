import React from "react";
import { Server, RefreshCw, AlertCircle, Phone, Shield, Trash2 } from "lucide-react";
import { toast } from "sonner";
import PhoneNumberService from "@/services/phone-number.service";

interface LiveKitMonitorTabProps {
  livekitStatus: any;
  isLivekitLoading: boolean;
  fetchLivekitStatus: () => void;
}

export function LiveKitMonitorTab({ livekitStatus, isLivekitLoading, fetchLivekitStatus }: LiveKitMonitorTabProps) {
  const handleDeleteTrunk = async (trunkId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete LiveKit SIP Trunk "${name}" (${trunkId}) from the LiveKit server?`)) {
      return;
    }
    try {
      await PhoneNumberService.deleteLiveKitTrunk(trunkId);
      toast.success(`SIP Trunk ${name} deleted successfully from LiveKit.`);
      fetchLivekitStatus();
    } catch (err: any) {
      toast.error(`Failed to delete trunk: ${err?.response?.data?.message || err?.message}`);
    }
  };

  const handleDeleteRule = async (ruleId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete LiveKit Dispatch Rule "${name}" (${ruleId}) from the LiveKit server?`)) {
      return;
    }
    try {
      await PhoneNumberService.deleteLiveKitDispatchRule(ruleId);
      toast.success(`Dispatch Rule ${name} deleted successfully from LiveKit.`);
      fetchLivekitStatus();
    } catch (err: any) {
      toast.error(`Failed to delete dispatch rule: ${err?.response?.data?.message || err?.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* LiveKit Connection Summary */}
      <div className="bg-white border border-zinc-200 p-5 rounded-sm shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-full shrink-0 ${
            livekitStatus?.connected 
              ? (livekitStatus.mode === "live" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600")
              : "bg-red-50 text-red-600"
          }`}>
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-bold text-sm text-zinc-950">LiveKit Server Instance</h4>
              <span className={`inline-block px-1.5 py-0.5 rounded-sm text-[8px] font-bold uppercase tracking-wider ${
                livekitStatus?.connected 
                  ? (livekitStatus.mode === "live" ? "bg-emerald-100 text-emerald-800 border border-emerald-250" : "bg-blue-100 text-blue-800 border border-blue-250")
                  : "bg-red-100 text-red-800 border border-red-250"
              }`}>
                {livekitStatus?.connected 
                  ? (livekitStatus.mode === "live" ? "Live Connected" : "Simulated/Mock")
                  : "Disconnected"}
              </span>
            </div>
            <p className="text-[10px] text-zinc-500 font-medium mt-0.5">
              Direct connection monitoring to verify the active LiveKit SIP registration pool and dispatch rules.
            </p>
          </div>
        </div>
        <button
          onClick={fetchLivekitStatus}
          disabled={isLivekitLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-200 hover:bg-zinc-50 text-zinc-700 text-xs font-semibold rounded-sm transition-all bg-white shadow-xs disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLivekitLoading ? "animate-spin" : ""}`} />
          <span>{isLivekitLoading ? "Syncing..." : "Sync Live Status"}</span>
        </button>
      </div>

      {livekitStatus?.error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-850 rounded-sm text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div>
            <strong className="font-bold">LiveKit Error:</strong> {livekitStatus.error}
          </div>
        </div>
      )}

      {/* Grid for Trunks & Rules */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* TRUNKS SECTION */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 border-b border-zinc-100 pb-2 flex items-center justify-between">
            <span>Active SIP Trunks ({livekitStatus?.trunks?.length || 0})</span>
            <span className="text-[10px] text-zinc-400 font-medium normal-case font-normal">Registered in LiveKit</span>
          </h3>

          {isLivekitLoading ? (
            <div className="py-12 text-center text-xs text-zinc-500 font-medium bg-white border border-zinc-200 rounded-sm">Syncing trunks...</div>
          ) : !livekitStatus?.trunks || livekitStatus.trunks.length === 0 ? (
            <div className="border border-dashed border-zinc-200 bg-white p-8 text-center rounded-sm">
              <Phone className="w-8 h-8 text-zinc-300 mx-auto mb-2" />
              <h4 className="font-bold text-xs text-zinc-900">No active trunks</h4>
              <p className="text-[10px] text-zinc-400 mt-0.5">There are no trunks provisioned on LiveKit server.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {livekitStatus.trunks.map((trunk: any) => {
                const badNumbers = trunk.numbers.filter((num: string) => {
                  const clean = num.replace(/[\s\-\(\)]/g, "");
                  return clean.match(/^\+(\d{1,3})0\d+/);
                });
                return (
                  <div key={trunk.id} className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-3">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h4 className="font-bold text-xs text-zinc-900 leading-tight">{trunk.name}</h4>
                        <span className="font-mono text-[9px] text-zinc-400 select-all">{trunk.id}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block px-1.5 py-0.5 bg-zinc-100 text-zinc-650 border border-zinc-200 rounded-sm text-[8px] font-bold uppercase tracking-wider">
                          Trunk info
                        </span>
                        <button
                          onClick={() => handleDeleteTrunk(trunk.id, trunk.name)}
                          className="p-1 text-zinc-400 hover:text-red-600 transition-colors"
                          title="Delete Trunk from LiveKit"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-400">DID Numbers:</span>
                      {trunk.numbers.map((num: string, i: number) => (
                        <code key={i} className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-800 rounded-sm text-[10px] font-mono font-medium">
                          {num}
                        </code>
                      ))}
                    </div>
                    {badNumbers.length > 0 && (
                      <div className="p-2.5 bg-amber-50 border border-amber-200 text-amber-850 rounded-sm text-[10px] flex items-start gap-1.5 leading-normal">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5 animate-bounce" />
                        <div>
                          <strong>Formatting Warning:</strong> These numbers contain a local dialing prefix <code>0</code> (e.g. <code>+640...</code>). LiveKit SIP matching will fail because Twilio routes calls without the local zero. Re-register the number in E.164 format (e.g., <code>+649...</code>) to restore service.
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* DISPATCH RULES SECTION */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-900 border-b border-zinc-100 pb-2 flex items-center justify-between">
            <span>Active Dispatch Rules ({livekitStatus?.dispatch_rules?.length || 0})</span>
            <span className="text-[10px] text-zinc-400 font-medium normal-case font-normal">SIP to Room Mappings</span>
          </h3>

          {isLivekitLoading ? (
            <div className="py-12 text-center text-xs text-zinc-500 font-medium bg-white border border-zinc-200 rounded-sm">Syncing dispatch rules...</div>
          ) : !livekitStatus?.dispatch_rules || livekitStatus.dispatch_rules.length === 0 ? (
            <div className="border border-dashed border-zinc-200 bg-white p-8 text-center rounded-sm">
              <Shield className="w-8 h-8 text-zinc-300 mx-auto mb-2" />
              <h4 className="font-bold text-xs text-zinc-900">No active dispatch rules</h4>
              <p className="text-[10px] text-zinc-400 mt-0.5">There are no dispatch rules defined on LiveKit server.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {livekitStatus.dispatch_rules.map((rule: any) => (
                <div key={rule.id} className="bg-white border border-zinc-200 p-4 rounded-sm shadow-xs space-y-2">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h4 className="font-bold text-xs text-zinc-900 leading-tight">{rule.name}</h4>
                      <span className="font-mono text-[9px] text-zinc-400 select-all">{rule.id}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-block px-1.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-250 rounded-sm text-[8px] font-bold uppercase tracking-wider">
                        Dispatch rule
                      </span>
                      <button
                        onClick={() => handleDeleteRule(rule.id, rule.name)}
                        className="p-1 text-zinc-400 hover:text-red-600 transition-colors"
                        title="Delete Dispatch Rule from LiveKit"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1 text-[10px] text-zinc-650">
                    <div>
                      <span className="font-bold uppercase tracking-wider text-zinc-400 mr-1.5">Target Trunks:</span>
                      {rule.trunk_ids && rule.trunk_ids.length > 0 ? (
                        rule.trunk_ids.map((tid: string, idx: number) => (
                          <code key={idx} className="font-mono bg-zinc-50 border border-zinc-150 rounded-sm px-1 py-0.5 mr-1 text-[9px]">
                            {tid}
                          </code>
                        ))
                      ) : (
                        <span className="text-red-500 italic">No trunks associated</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default LiveKitMonitorTab;
