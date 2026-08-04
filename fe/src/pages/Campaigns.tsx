import React, { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus,
  Search,
  Trash2,
  Bot,
  Megaphone,
  Eye
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { useCampaignStore, CampaignItem } from "@/store/campaignStore";

export default function Campaigns() {
  // Zustand store hooks
  const campaigns = useCampaignStore((state) => state.campaigns);
  const deleteCampaign = useCampaignStore((state) => state.deleteCampaign);

  // Search State
  const [searchQuery, setSearchQuery] = useState("");

  // Filtered Campaigns (Search only)
  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((c) => {
      return (
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.agent.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.callerId.includes(searchQuery)
      );
    });
  }, [campaigns, searchQuery]);

  return (
    <div className="space-y-6" data-testid="campaigns-page">
      {/* Header */}
      <PageHeader
        title="Campaigns"
        subtitle="Manage, schedule, and monitor automated AI outbound voice & multichannel outreach campaigns"
        actions={
          <div className="flex items-center gap-3">
            <Link
              to="/campaigns/new"
              className="flex items-center gap-2 px-4 py-2 bg-zinc-950 hover:bg-zinc-800 text-white text-xs font-semibold rounded-sm transition-colors shadow-sm"
              data-testid="create-campaign-btn"
            >
              <Plus className="w-4 h-4" />
              <span>Create Campaign</span>
            </Link>
          </div>
        }
      />

      {/* Search Toolbar */}
      <div className="bg-white border border-zinc-200 p-4 rounded-sm flex justify-between items-center gap-4">
        <div className="relative w-full max-w-md">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search campaigns by name, agent, caller ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-50 border border-zinc-200 rounded-sm pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:border-zinc-950 focus:bg-white"
          />
        </div>

        <div className="text-xs text-zinc-500 font-mono-stat">
          Total Campaigns: <strong className="text-zinc-900 font-semibold">{filteredCampaigns.length}</strong>
        </div>
      </div>

      {/* Campaigns Table */}
      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-zinc-50 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-200 font-bold">
                <th className="px-5 py-3 text-left">Campaign Name</th>
                <th className="px-5 py-3 text-left">Assigned Agent</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-center">Answer Rate</th>
                <th className="px-5 py-3 text-center">Conversion</th>
                <th className="px-5 py-3 text-left">Caller ID / Schedule</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-zinc-200">
              {filteredCampaigns.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-zinc-400 italic space-y-2">
                    <Megaphone className="w-8 h-8 text-zinc-300 mx-auto" />
                    <p className="text-sm font-semibold text-zinc-600">No campaigns found.</p>
                  </td>
                </tr>
              ) : (
                filteredCampaigns.map((camp) => {
                  const percent =
                    camp.totalLeads > 0
                      ? Math.round((camp.completedLeads / camp.totalLeads) * 100)
                      : 0;

                  return (
                    <tr key={camp.id} className="hover:bg-zinc-50/70 transition-colors">
                      {/* Name & Channel Tag */}
                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="space-y-1 max-w-xs">
                          <div className="flex items-center gap-2">
                            <Link
                              to={`/campaigns/${camp.id}`}
                              className="font-bold text-zinc-950 hover:text-indigo-600 transition-colors"
                            >
                              {camp.name}
                            </Link>
                            <span
                              className={`px-1.5 py-0.2 text-[9px] font-bold rounded uppercase tracking-wider ${camp.channel === "voice"
                                  ? "bg-indigo-50 text-indigo-700 border border-indigo-200/60"
                                  : camp.channel === "sms"
                                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                                    : "bg-purple-50 text-purple-700 border border-purple-200/60"
                                }`}
                            >
                              {camp.channel}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-500 truncate">{camp.description}</p>
                        </div>
                      </td>

                      {/* Agent */}
                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-zinc-900 text-white flex items-center justify-center text-[10px] font-bold">
                            <Bot className="w-3.5 h-3.5" />
                          </div>
                          <span className="text-xs font-semibold text-zinc-800">{camp.agent}</span>
                        </div>
                      </td>

                      {/* Status Badge */}
                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${camp.status === "active"
                                ? "bg-emerald-500 animate-pulse"
                                : camp.status === "paused"
                                  ? "bg-amber-500"
                                  : camp.status === "completed"
                                    ? "bg-blue-500"
                                    : camp.status === "scheduled"
                                      ? "bg-indigo-500"
                                      : "bg-zinc-400"
                              }`}
                          />
                          <span
                            className={`px-2 py-0.5 text-[9px] font-bold rounded-sm uppercase tracking-wide border ${camp.status === "active"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : camp.status === "paused"
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : camp.status === "completed"
                                    ? "bg-blue-50 text-blue-700 border-blue-200"
                                    : camp.status === "scheduled"
                                      ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                                      : "bg-zinc-100 text-zinc-600 border-zinc-200"
                              }`}
                          >
                            {camp.status}
                          </span>
                        </div>
                      </td>

                      {/* Answer Rate */}
                      <td className="px-5 py-4 whitespace-nowrap text-center">
                        <span className="font-mono-stat text-xs font-bold text-zinc-900">
                          {camp.answerRate > 0 ? `${camp.answerRate}%` : "—"}
                        </span>
                      </td>

                      {/* Conversion Rate */}
                      <td className="px-5 py-4 whitespace-nowrap text-center">
                        <span className="font-mono-stat text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-sm border border-emerald-200/50">
                          {camp.conversionRate > 0 ? `${camp.conversionRate}%` : "—"}
                        </span>
                      </td>

                      {/* Caller ID & Schedule */}
                      <td className="px-5 py-4 whitespace-nowrap text-xs text-zinc-600">
                        <div className="font-mono-stat font-medium text-zinc-800">{camp.callerId}</div>
                        <div className="text-[10px] text-zinc-400 truncate max-w-[140px]">{camp.schedule}</div>
                      </td>

                      {/* Action Menu */}
                      <td className="px-5 py-4 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            to={`/campaigns/${camp.id}`}
                            className="p-1.5 text-zinc-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-sm transition-colors"
                            title="View Campaign Details & Leads"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          <button
                            onClick={() => {
                              deleteCampaign(camp.id);
                              toast.success(`Deleted campaign '${camp.name}'`);
                            }}
                            className="p-1.5 text-zinc-400 hover:text-red-600 hover:bg-red-50 rounded-sm transition-colors"
                            title="Delete Campaign"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
