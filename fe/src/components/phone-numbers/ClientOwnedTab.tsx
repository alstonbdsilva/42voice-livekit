import React from "react";
import { Phone, Search, ToggleRight, ToggleLeft } from "lucide-react";

interface ClientOwnedTabProps {
  numbers: any[];
  agents: any[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  onAgentChange: (id: string, agentId: string) => void;
  onRelease: (id: string, numStr: string) => void;
  onToggleStatus: (id: string) => void;
  onBrowseRedirect: () => void;
}

export function ClientOwnedTab({
  numbers,
  agents,
  searchQuery,
  setSearchQuery,
  onAgentChange,
  onRelease,
  onToggleStatus,
  onBrowseRedirect
}: ClientOwnedTabProps) {
  return (
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

      {numbers.length === 0 ? (
        <div className="border border-dashed border-zinc-200 bg-white p-12 text-center rounded-sm">
          <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
          <h3 className="font-bold text-sm text-zinc-950">No purchased numbers</h3>
          <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto">
            You haven't purchased any voice numbers yet. Check out the available pool to get started.
          </p>
          <button
            onClick={onBrowseRedirect}
            className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white hover:bg-zinc-800 text-xs font-semibold rounded-sm transition-colors"
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
                      onChange={(e) => onAgentChange(num.id, e.target.value)}
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
                      onClick={() => onToggleStatus(num.id)}
                      className="inline-flex focus:outline-none transition-colors"
                    >
                      {num.status === "active" ? (
                        <ToggleRight className="w-7 h-7 text-emerald-600" />
                      ) : (
                        <ToggleLeft className="w-7 h-7 text-zinc-300" />
                      )}
                    </button>
                  </td>
                  <td className="px-5 py-4 whitespace-nowrap text-right text-zinc-900 font-mono font-medium text-xs">
                    {num.monthlyCost}/mo
                  </td>
                  <td className="px-5 py-4 whitespace-nowrap text-center text-xs">
                    <button
                      onClick={() => onRelease(num.id, num.number)}
                      className="px-2.5 py-1 text-zinc-500 hover:text-red-600 border border-zinc-200 hover:border-red-200 bg-white rounded-sm font-semibold transition-all hover:bg-red-50"
                    >
                      Release Line
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ClientOwnedTab;
