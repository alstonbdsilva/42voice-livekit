import React from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Save,
  CheckCircle2,
  UploadCloud,
  History,
  LayoutGrid,
  ShieldCheck,
  AlertCircle,
  Lock,
} from "lucide-react";
import { WorkflowDraft, WorkflowVersion } from "@/types/workflow";

interface WorkflowToolbarProps {
  workflowName: string;
  isDirty: boolean;
  isSaving: boolean;
  isValidating: boolean;
  isPublishing: boolean;
  activeVersionNumber: number | null;
  isReadOnly: boolean;
  onSaveDraft: () => void;
  onValidate: () => void;
  onPublishClick: () => void;
  onAutoLayout: () => void;
  onOpenVersionHistory: () => void;
}

export const WorkflowToolbar: React.FC<WorkflowToolbarProps> = ({
  workflowName,
  isDirty,
  isSaving,
  isValidating,
  isPublishing,
  activeVersionNumber,
  isReadOnly,
  onSaveDraft,
  onValidate,
  onPublishClick,
  onAutoLayout,
  onOpenVersionHistory,
}) => {
  return (
    <header className="h-14 bg-white border-b border-zinc-200 flex items-center justify-between px-4 z-20 select-none">
      {/* Left: Navigation and Workflow Title */}
      <div className="flex items-center gap-3">
        <Link
          to="/workflows"
          className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 transition-colors"
          title="Back to Workflows"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>

        <div className="h-5 w-px bg-zinc-200" />

        <div className="flex items-center gap-2.5">
          <h1 className="text-sm font-bold text-zinc-900 truncate max-w-[280px]">
            {workflowName || "Untitled Workflow"}
          </h1>

          {isReadOnly ? (
            <span className="flex items-center gap-1 text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-full">
              <Lock className="w-3 h-3" />
              PUBLISHED V{activeVersionNumber} (READ-ONLY)
            </span>
          ) : (
            <span className="text-[11px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-200 px-2 py-0.5 rounded-full">
              DRAFT
            </span>
          )}

          {/* Dirty status indicator */}
          {!isReadOnly && (
            <div className="flex items-center gap-1.5 text-xs">
              {isDirty ? (
                <span className="flex items-center gap-1 text-amber-600 font-medium">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  Unsaved changes
                </span>
              ) : (
                <span className="flex items-center gap-1 text-zinc-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  Saved
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        {/* Auto Layout */}
        <button
          onClick={onAutoLayout}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg border border-zinc-200 transition-colors"
          title="Auto-organize nodes neatly"
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          <span>Auto Layout</span>
        </button>

        {/* Version History */}
        <button
          onClick={onOpenVersionHistory}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg border border-zinc-200 transition-colors"
        >
          <History className="w-3.5 h-3.5" />
          <span>Versions</span>
        </button>

        <div className="h-5 w-px bg-zinc-200 mx-1" />

        {/* Validate Graph */}
        <button
          onClick={onValidate}
          disabled={isValidating}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 rounded-lg border border-zinc-200 transition-colors disabled:opacity-50"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
          <span>{isValidating ? "Validating..." : "Validate"}</span>
        </button>

        {!isReadOnly && (
          <>
            {/* Save Draft */}
            <button
              onClick={onSaveDraft}
              disabled={isSaving || !isDirty}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-900 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isSaving ? "Saving..." : "Save Draft"}</span>
            </button>

            {/* Publish Version */}
            <button
              onClick={onPublishClick}
              disabled={isPublishing || isSaving}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>{isPublishing ? "Publishing..." : "Publish"}</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
};

export default WorkflowToolbar;
