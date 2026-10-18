import type { Completeness, RunStatus } from "../types/api";

const STATUS_STYLE: Record<RunStatus, string> = {
  ok: "bg-ok-soft text-ok",
  error: "bg-fault-soft text-fault",
  unknown: "bg-sunken text-muted",
};

const STATUS_LABEL: Record<RunStatus, string> = { ok: "Succeeded", error: "Failed", unknown: "Unknown" };

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status]}`}>
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function CompletenessBadge({ completeness }: { completeness: Completeness }) {
  if (completeness === "complete") {
    return <span className="text-xs text-muted">Complete trace</span>;
  }
  return (
    <span className="inline-flex rounded-full border border-dashed border-warn bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn">
      Incomplete trace
    </span>
  );
}
