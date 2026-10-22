// Small shared presentational components used by more than one view.
// Only real repeated patterns live here (per docs/CODING_STANDARDS.md).

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h2>{title}</h2>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="empty-state" role="status">
      <p className="empty-state__message">{message}</p>
      {hint && <p className="empty-state__hint">{hint}</p>}
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="loading-block" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Pagination({
  page,
  total,
  totalPages,
  onPage,
}: {
  page: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        Previous
      </button>
      <span className="pagination__label">
        Page {page} of {totalPages} · {total} total
      </span>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
      >
        Next
      </button>
    </div>
  );
}

// Modal confirmation shown before a consequential action (delete/archive).
// Focus starts inside the dialog; Escape and backdrop click cancel while the
// action is not in flight; the confirm button can be held disabled (e.g.
// while a required count is still loading) so confirmations cannot fire
// without the information the dialog promised to show.
export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = false,
  busy = false,
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape" && !busy) {
      event.stopPropagation();
      onCancel();
    }
  };

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={() => {
        if (!busy) onCancel();
      }}
    >
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={dialogRef}
        onKeyDown={handleKeyDown}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h3 id={titleId}>{title}</h3>
        <div className="dialog__body">{children}</div>
        <div className="dialog__actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={busy}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={destructive ? "btn btn-danger" : "btn btn-primary"}
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
