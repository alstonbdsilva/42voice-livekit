import React, { useState } from "react";
import { UploadCloud, X, AlertCircle } from "lucide-react";

interface PublishDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmPublish: (description: string) => Promise<void>;
  isPublishing: boolean;
}

export const PublishDialog: React.FC<PublishDialogProps> = ({
  isOpen,
  onClose,
  onConfirmPublish,
  isPublishing,
}) => {
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handlePublish = async () => {
    setError(null);
    try {
      await onConfirmPublish(description.trim());
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.message || err?.message || "Failed to publish workflow version.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-xl border border-zinc-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-zinc-900">Publish Workflow Version</h3>
              <p className="text-xs text-zinc-500">Create an immutable, production-ready snapshot</p>
            </div>
          </div>
          <button
            disabled={isPublishing}
            onClick={onClose}
            className="p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">
          <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 text-xs text-zinc-600 leading-relaxed">
            Publishing stamps an immutable version (e.g. <code>V1</code>, <code>V2</code>) with all nodes, transitions, and prompts frozen in time. Voice agents can then be pinned to this version.
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">
              Release Notes / Description (Optional)
            </label>
            <textarea
              disabled={isPublishing}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="e.g. Added billing inquiry branch and updated appointment confirmation instructions"
              className="w-full text-xs p-2 rounded-md border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
            />
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-100 rounded-lg text-xs text-rose-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-100 flex items-center justify-end gap-2">
          <button
            disabled={isPublishing}
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={isPublishing}
            onClick={handlePublish}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg shadow-xs transition-colors"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>{isPublishing ? "Publishing..." : "Publish Version"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default PublishDialog;
