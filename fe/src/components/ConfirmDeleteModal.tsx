import React from "react";
import AppModal from "@/components/AppModal";

// ---------------------------------------------------------------------------
// ConfirmDeleteModal
// A pre-wired destructive confirmation dialog built on top of AppModal.
// Use this for every DELETE action across the application.
//
// Usage:
//   <ConfirmDeleteModal
//     open={isDeleteOpen}
//     onClose={() => setIsDeleteOpen(false)}
//     onConfirm={handleDelete}
//     loading={busy}
//     entityName="Partner Corp"           // shown in bold
//     entityLabel="partner"               // e.g. "partner", "user", "client"
//     warningNote="Their login credentials will also be removed."  // optional
//   />
// ---------------------------------------------------------------------------

export interface ConfirmDeleteModalProps {
  /** Controls visibility. */
  open: boolean;
  /** Called when the modal should close. */
  onClose: () => void;
  /** Called when the user clicks "Delete". */
  onConfirm: () => void;
  /** Whether the confirm button shows a loading indicator. */
  loading?: boolean;
  /** The display name of the record being deleted, shown in bold. */
  entityName?: string;
  /** Friendly noun for what is being deleted – used in the message. Defaults to "record". */
  entityLabel?: string;
  /**
   * Optional extra warning shown below the main message.
   * Use this to highlight cascading effects (e.g. "Their linked user account will also be removed.").
   */
  warningNote?: string;
}

export function ConfirmDeleteModal({
  open,
  onClose,
  onConfirm,
  loading = false,
  entityName,
  entityLabel = "record",
  warningNote,
}: ConfirmDeleteModalProps) {
  return (
    <AppModal
      open={open}
      onClose={onClose}
      title={`Delete ${entityLabel.charAt(0).toUpperCase() + entityLabel.slice(1)}`}
      maxWidth="sm:max-w-[420px]"
      confirmLabel="Delete"
      confirmVariant="destructive"
      onConfirm={onConfirm}
      loading={loading}
      cancelLabel="Cancel"
    >
      <div className="space-y-2 py-1">
        <p className="text-sm text-zinc-600">
          Are you sure you want to delete{" "}
          {entityName ? <strong>{entityName}</strong> : <span>this {entityLabel}</span>}?{" "}
          This action <strong>cannot be undone</strong>.
        </p>
        {warningNote && (
          <p className="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-md px-3 py-2 leading-relaxed">
            ⚠ {warningNote}
          </p>
        )}
      </div>
    </AppModal>
  );
}

export default ConfirmDeleteModal;
