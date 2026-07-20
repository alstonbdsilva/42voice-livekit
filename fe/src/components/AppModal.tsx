import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// AppModal
// A thin, opinionated wrapper around the Radix Dialog primitives.
//
// Usage – General modal:
//   <AppModal open={open} onClose={() => setOpen(false)} title="Add User">
//     <form>...</form>
//   </AppModal>
//
// Usage – Confirm / destructive dialog:
//   <AppModal
//     open={open}
//     onClose={() => setOpen(false)}
//     title="Delete Record"
//     description="This action is permanent."
//     confirmLabel="Delete"
//     confirmVariant="destructive"
//     onConfirm={handleDelete}
//     loading={busy}
//   />
// ---------------------------------------------------------------------------

export interface AppModalProps {
  /** Controls visibility. Bind to a boolean state. */
  open: boolean;
  /** Called when the modal should close (X button, overlay click, cancel). */
  onClose: () => void;
  /** Modal heading shown in the DialogHeader. */
  title: string;
  /** Optional subtitle / description shown below the title. */
  description?: string;
  /** Max-width override passed straight to the inner DialogContent div. */
  maxWidth?: string;
  /** Modal body content – forms, info blocks, etc. */
  children?: React.ReactNode;

  // ── Footer / action props ─────────────────────────────────────────────────
  /** Label of the primary confirm button. Defaults to "Confirm". */
  confirmLabel?: string;
  /** Variant of the primary confirm button. Defaults to "default". */
  confirmVariant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  /** Callback for the primary confirm button. Required when showFooter is true. */
  onConfirm?: () => void;
  /** Whether the confirm button shows a loading spinner. */
  loading?: boolean;
  /** Label of the cancel button. Defaults to "Cancel". */
  cancelLabel?: string;
  /** Whether to render the built-in footer at all. When false you own the footer (inside children). */
  showFooter?: boolean;
}

export function AppModal({
  open,
  onClose,
  title,
  description,
  maxWidth = "sm:max-w-[450px]",
  children,
  confirmLabel = "Confirm",
  confirmVariant = "default",
  onConfirm,
  loading = false,
  cancelLabel = "Cancel",
  showFooter = true,
}: AppModalProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className={maxWidth}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        {/* ── Body ─────────────────────────────────────────────────────────── */}
        {children && <div className="py-2">{children}</div>}

        {/* ── Footer ───────────────────────────────────────────────────────── */}
        {showFooter && (
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={loading}
            >
              {cancelLabel}
            </Button>
            {onConfirm && (
              <Button
                type="button"
                variant={confirmVariant}
                onClick={onConfirm}
                disabled={loading}
              >
                {loading ? "Please wait…" : confirmLabel}
              </Button>
            )}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default AppModal;
