import type { ReactNode } from "react";

import { ApiError } from "../api/client";

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 px-4 py-10 text-muted">
      <span aria-hidden className="h-4 w-1 animate-pulse rounded bg-cursor" />
      {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-4 py-10">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const status = error instanceof ApiError && error.status > 0 ? `HTTP ${error.status}: ` : "";
  return (
    <div role="alert" className="m-4 rounded-lg border border-fault/40 bg-fault-soft px-4 py-3">
      <p className="font-semibold text-fault">Could not load data</p>
      <p className="mt-1 text-sm">
        {status}
        {error.message}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 rounded-md border border-line bg-panel px-3 py-1 text-sm font-medium hover:bg-sunken">
          Try again
        </button>
      )}
    </div>
  );
}
