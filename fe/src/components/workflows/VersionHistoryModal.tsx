import React, { useState, useEffect } from "react";
import { History, Check, Eye, RotateCcw, X, Lock, FileText } from "lucide-react";
import { WorkflowVersion } from "@/types/workflow";
import { WorkflowService } from "@/services/workflow.service";

interface VersionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: string;
  currentVersionNumber: number | null;
  onSelectVersion: (version: WorkflowVersion | null) => void;
  onRestoreVersionToDraft: (version: WorkflowVersion) => void;
}

export const VersionHistoryModal: React.FC<VersionHistoryModalProps> = ({
  isOpen,
  onClose,
  workflowId,
  currentVersionNumber,
  onSelectVersion,
  onRestoreVersionToDraft,
}) => {
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && workflowId) {
      loadVersions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, workflowId]);

  const loadVersions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await WorkflowService.listVersions(workflowId);
      // Sort newest first
      const sorted = [...data].sort((a, b) => b.version_number - a.version_number);
      setVersions(sorted);
    } catch (err: any) {
      setError(err?.response?.data?.message || "Failed to load workflow version history.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-xl border border-zinc-200 w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-zinc-900">Version History</h3>
              <p className="text-xs text-zinc-500">
                Published immutable snapshots and release notes
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto space-y-3">
          {/* Working Draft Item */}
          <div
            className={`p-3.5 rounded-xl border flex items-center justify-between transition-all ${
              currentVersionNumber === null
                ? "bg-indigo-50/40 border-indigo-300 ring-1 ring-indigo-200"
                : "bg-white border-zinc-200 hover:border-zinc-300"
            }`}
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-zinc-900">Working Draft</span>
                <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">
                  EDITABLE
                </span>
              </div>
              <p className="text-xs text-zinc-500">Currently active mutable workspace definition.</p>
            </div>

            <button
              onClick={() => {
                onSelectVersion(null);
                onClose();
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                currentVersionNumber === null
                  ? "bg-indigo-600 text-white cursor-default"
                  : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
            >
              {currentVersionNumber === null ? "Currently Editing" : "Switch to Draft"}
            </button>
          </div>

          <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 pt-2">
            Published Immutable Versions
          </div>

          {isLoading && (
            <div className="py-8 text-center text-xs text-zinc-400">Loading version history...</div>
          )}

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-100 text-rose-800 rounded-lg text-xs">
              {error}
            </div>
          )}

          {!isLoading && versions.length === 0 && (
            <div className="py-8 text-center text-xs text-zinc-400 italic">
              No published versions yet. Save your draft and click "Publish" to create Version 1.
            </div>
          )}

          {versions.map((ver) => {
            const isViewingThis = currentVersionNumber === ver.version_number;
            const nodeCount = Object.keys(ver.definition?.nodes || {}).length;
            const edgeCount = (ver.definition?.edges || []).length;
            const publishedDate = ver.published_at
              ? new Date(ver.published_at).toLocaleString()
              : ver.created_at
              ? new Date(ver.created_at).toLocaleString()
              : "Unknown date";

            return (
              <div
                key={ver.id}
                className={`p-3.5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all ${
                  isViewingThis
                    ? "bg-amber-50/50 border-amber-300 ring-1 ring-amber-200"
                    : "bg-white border-zinc-200 hover:border-zinc-300"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-zinc-900">Version {ver.version_number}</span>
                    <span className="flex items-center gap-1 text-[10px] font-semibold bg-zinc-100 text-zinc-700 px-1.5 py-0.5 rounded border border-zinc-200">
                      <Lock className="w-2.5 h-2.5" />
                      IMMUTABLE
                    </span>
                  </div>

                  <div className="text-[11px] text-zinc-500">
                    Published on {publishedDate} • {nodeCount} nodes, {edgeCount} transitions
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => {
                      onSelectVersion(ver);
                      onClose();
                    }}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      isViewingThis
                        ? "bg-amber-600 text-white cursor-default"
                        : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
                    }`}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>{isViewingThis ? "Viewing" : "Inspect"}</span>
                  </button>

                  <button
                    onClick={() => {
                      if (
                        window.confirm(
                          `Overwrite current draft with Version ${ver.version_number} definition? Any unsaved draft changes will be replaced.`
                        )
                      ) {
                        onRestoreVersionToDraft(ver);
                        onClose();
                      }
                    }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 transition-colors"
                    title="Copy this version into draft"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Restore to Draft</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 text-xs font-medium rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default VersionHistoryModal;
