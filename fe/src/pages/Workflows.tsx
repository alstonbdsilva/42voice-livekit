import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  GitBranch,
  Plus,
  Search,
  Lock,
  Edit,
  ArrowRight,
  Sparkles,
  Calendar,
  Layers,
  MoreVertical,
  X,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { WorkflowSummary } from "@/types/workflow";
import { WorkflowService } from "@/services/workflow.service";

export default function Workflows() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Create Workflow modal state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchWorkflows = async () => {
    setIsLoading(true);
    try {
      const data = await WorkflowService.listWorkflows();
      setWorkflows(data);
    } catch (err: any) {
      toast.error(err?.response?.data?.message || "Failed to load workflows.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleCreateWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    setIsSubmitting(true);
    try {
      const created = await WorkflowService.createWorkflow({
        name: newName.trim(),
        description: newDescription.trim() || undefined,
      });
      toast.success("Workflow created successfully.");
      setIsCreateOpen(false);
      setNewName("");
      setNewDescription("");
      // Navigate straight into the builder for the newly created workflow
      navigate(`/workflows/${created.id}/builder`);
    } catch (err: any) {
      toast.error(err?.response?.data?.message || "Failed to create workflow.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredWorkflows = workflows.filter((w) =>
    (w.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (w.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-display text-zinc-900 flex items-center gap-2.5">
            <GitBranch className="w-6 h-6 text-indigo-600" />
            Voice Workflows
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Build multi-step, deterministic, and LLM-steered voice workflows for your AI agents.
          </p>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors shrink-0"
        >
          <Plus className="w-4 h-4" />
          Create Workflow
        </button>
      </div>

      {/* Search and Filters Bar */}
      <div className="flex items-center gap-3 bg-white p-2 rounded-xl border border-zinc-200 shadow-xs">
        <Search className="w-4 h-4 text-zinc-400 ml-2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search workflows by name or description..."
          className="flex-1 text-xs bg-transparent focus:outline-none text-zinc-800 placeholder:text-zinc-400"
        />
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="py-16 text-center text-xs text-zinc-400">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          Loading workflows...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && filteredWorkflows.length === 0 && (
        <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-zinc-200">
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3">
            <GitBranch className="w-6 h-6 stroke-1.5" />
          </div>
          <h3 className="text-sm font-bold text-zinc-900">No workflows found</h3>
          <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
            {searchQuery
              ? "No workflows match your search criteria."
              : "Get started by creating your first visual voice workflow."}
          </p>
          {!searchQuery && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-medium rounded-lg transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Workflow
            </button>
          )}
        </div>
      )}

      {/* Workflow Cards Grid */}
      {!isLoading && filteredWorkflows.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredWorkflows.map((wf) => {
            const hasPublished = wf.latestPublishedVersionNumber !== null && wf.latestPublishedVersionNumber !== undefined;
            const updatedDate = wf.updatedAt
              ? new Date(wf.updatedAt).toLocaleDateString()
              : wf.createdAt
              ? new Date(wf.createdAt).toLocaleDateString()
              : "Recently";

            return (
              <div
                key={wf.id}
                className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0">
                      <Layers className="w-4 h-4" />
                    </div>

                    <div className="flex items-center gap-1.5">
                      {hasPublished ? (
                        <span className="flex items-center gap-1 text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                          <Lock className="w-2.5 h-2.5" />
                          PUBLISHED V{wf.latestPublishedVersionNumber}
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full">
                          DRAFT ONLY
                        </span>
                      )}
                    </div>
                  </div>

                  <h3 className="text-sm font-bold text-zinc-900 group-hover:text-indigo-600 transition-colors">
                    {wf.name}
                  </h3>

                  <p className="text-xs text-zinc-500 mt-1.5 line-clamp-2 min-h-[32px]">
                    {wf.description || "No description provided."}
                  </p>
                </div>

                <div className="mt-5 pt-4 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-400">
                  <div className="flex items-center gap-1 text-[11px]">
                    <Calendar className="w-3 h-3" />
                    {updatedDate}
                  </div>

                  <Link
                    to={`/workflows/${wf.id}/builder`}
                    className="flex items-center gap-1 text-xs font-semibold text-zinc-900 group-hover:text-indigo-600 transition-colors"
                  >
                    Open Builder
                    <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Workflow Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-zinc-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <Plus className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-zinc-900">Create Voice Workflow</h3>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateWorkflow} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Workflow Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Inbound Customer Support Flow"
                  className="w-full text-xs p-2.5 rounded-lg border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">Description (Optional)</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  rows={3}
                  placeholder="Briefly describe the purpose of this workflow..."
                  className="w-full text-xs p-2.5 rounded-lg border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-3.5 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !newName.trim()}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
                >
                  {isSubmitting ? "Creating..." : "Create & Launch Builder"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
