// Shows the result of comparing two runs, one row per matched or unmatched event.

import { formatDelta, formatDuration, formatValue } from "../../lib/format";
import type { DiffEntry, DiffKind } from "../../types/api";

const KIND: Record<DiffKind, { mark: string; label: string; className: string }> = {
  unchanged: { mark: "=", label: "Same", className: "text-muted" },
  changed: { mark: "~", label: "Changed", className: "text-warn" },
  added: { mark: "+", label: "Only in target", className: "text-ok" },
  missing: { mark: "−", label: "Only in base", className: "text-fault" },
};

function StatusCell({ entry }: { entry: DiffEntry }) {
  if (!entry.status_change) return <span className="text-muted">—</span>;
  return (
    <span className="font-mono text-xs">
      {entry.status_change.base} → <span className="font-semibold text-fault">{entry.status_change.target}</span>
    </span>
  );
}

function DurationCell({ entry }: { entry: DiffEntry }) {
  const d = entry.duration;
  if (!d) return <span className="text-muted">—</span>;
  return (
    <span className="font-mono text-xs tabular-nums">
      {formatDuration(d.base_ms)} → {formatDuration(d.target_ms)}{" "}
      <span className={d.significant ? "font-semibold text-warn" : "text-muted"}>
        ({formatDelta(d.delta_ms)}
        {d.delta_pct !== null && `, ${d.delta_pct > 0 ? "+" : ""}${d.delta_pct}%`})
      </span>
    </span>
  );
}

function ChangesCell({ entry }: { entry: DiffEntry }) {
  const items: string[] = entry.attribute_changes.map((c) => {
    if (c.change === "added") return `${c.key}: added ${formatValue(c.target)}`;
    if (c.change === "removed") return `${c.key}: removed (was ${formatValue(c.base)})`;
    return `${c.key}: ${formatValue(c.base)} → ${formatValue(c.target)}`;
  });
  if (entry.error_change) items.push(`error: ${entry.error_change.base ?? "none"} → ${entry.error_change.target ?? "none"}`);
  if (items.length === 0) return <span className="text-muted">—</span>;
  return (
    <ul className="space-y-0.5 font-mono text-xs">
      {items.map((item) => (
        <li key={item} className="break-all">
          {item}
        </li>
      ))}
    </ul>
  );
}

export function ComparisonTable({ entries }: { entries: DiffEntry[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <table className="w-full min-w-[48rem] text-sm">
        <thead className="bg-sunken text-left text-xs text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Result</th>
            <th scope="col" className="px-3 py-2 font-medium">Operation</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
            <th scope="col" className="px-3 py-2 font-medium">Duration (base → target)</th>
            <th scope="col" className="px-3 py-2 font-medium">Attribute and error changes</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const kind = KIND[entry.kind];
            return (
              <tr key={entry.key} data-kind={entry.kind} className="border-t border-line/60 align-top">
                <td className={`px-3 py-1.5 whitespace-nowrap ${kind.className}`}>
                  <span aria-hidden className="mr-1.5 inline-block w-3 text-center font-mono font-bold">
                    {kind.mark}
                  </span>
                  {kind.label}
                </td>
                <td className="px-3 py-1.5">
                  <span className="font-mono text-[13px]" style={{ paddingLeft: `${entry.depth * 0.9}rem` }}>
                    {entry.event_type === "exception" ? `exception in ${entry.operation_name}` : entry.operation_name}
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  <StatusCell entry={entry} />
                </td>
                <td className="px-3 py-1.5">
                  <DurationCell entry={entry} />
                </td>
                <td className="px-3 py-1.5">
                  <ChangesCell entry={entry} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
