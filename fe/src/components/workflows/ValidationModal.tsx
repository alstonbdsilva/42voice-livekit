import React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, X } from "lucide-react";
import { ValidationResponse, ValidationErrorItem } from "@/types/workflow";

interface ValidationModalProps {
  isOpen: boolean;
  onClose: () => void;
  validationResult: ValidationResponse | null;
  onFocusNode?: (nodeId: string) => void;
}

export const ValidationModal: React.FC<ValidationModalProps> = ({
  isOpen,
  onClose,
  validationResult,
  onFocusNode,
}) => {
  if (!isOpen || !validationResult) return null;

  const { valid, errors, warnings, node_count, edge_count } = validationResult;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-xl border border-zinc-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {valid ? (
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
                <AlertCircle className="w-5 h-5" />
              </div>
            )}
            <div>
              <h3 className="text-sm font-bold text-zinc-900">
                {valid ? "Workflow is Valid & Ready" : "Validation Errors Found"}
              </h3>
              <p className="text-xs text-zinc-500">
                Analyzed {node_count} nodes and {edge_count} transitions
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
          {valid && errors.length === 0 && warnings.length === 0 && (
            <div className="p-4 bg-emerald-50/60 rounded-xl border border-emerald-100 text-center text-xs text-emerald-900">
              🎉 All graph validation checks passed! Graph connectivity, condition branches, tool registrations, and start node semantics are verified.
            </div>
          )}

          {errors.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-bold text-rose-700 uppercase tracking-wider flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5" />
                Errors ({errors.length}) - Must be resolved before publishing
              </div>
              {errors.map((err, i) => (
                <div
                  key={`err-${i}`}
                  className="p-3 bg-rose-50 rounded-lg border border-rose-100 text-xs flex items-start justify-between gap-2"
                >
                  <div className="space-y-1">
                    <p className="font-medium text-rose-950">{err.message}</p>
                    {err.node_id && (
                      <span className="inline-block font-mono text-[10px] bg-rose-100/80 text-rose-800 px-1.5 py-0.5 rounded">
                        Node: {err.node_id}
                      </span>
                    )}
                  </div>
                  {err.node_id && onFocusNode && (
                    <button
                      onClick={() => {
                        onFocusNode(err.node_id!);
                        onClose();
                      }}
                      className="shrink-0 text-[11px] font-semibold text-rose-700 hover:text-rose-900 underline"
                    >
                      Locate Node
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {warnings.length > 0 && (
            <div className="space-y-2 pt-2">
              <div className="text-xs font-bold text-amber-700 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Warnings ({warnings.length})
              </div>
              {warnings.map((warn, i) => (
                <div
                  key={`warn-${i}`}
                  className="p-3 bg-amber-50 rounded-lg border border-amber-100 text-xs flex items-start justify-between gap-2"
                >
                  <div className="space-y-1">
                    <p className="font-medium text-amber-950">{warn.message}</p>
                    {warn.node_id && (
                      <span className="inline-block font-mono text-[10px] bg-amber-100/80 text-amber-800 px-1.5 py-0.5 rounded">
                        Node: {warn.node_id}
                      </span>
                    )}
                  </div>
                  {warn.node_id && onFocusNode && (
                    <button
                      onClick={() => {
                        onFocusNode(warn.node_id!);
                        onClose();
                      }}
                      className="shrink-0 text-[11px] font-semibold text-amber-700 hover:text-amber-900 underline"
                    >
                      Locate Node
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-medium rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ValidationModal;
