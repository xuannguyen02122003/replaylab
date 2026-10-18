import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { compareRuns, listRuns } from "../api/client";
import { ComparisonTable } from "../components/RunComparison/ComparisonTable";
import { EmptyState, ErrorState, LoadingState } from "../components/StateViews";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime } from "../lib/format";
import type { Comparison, Run } from "../types/api";

function RunSelect({ label, value, runs, onChange }: { label: string; value: string; runs: Run[]; onChange: (id: string) => void }) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-md border border-line bg-panel px-2 py-1.5 font-mono text-xs">
        <option value="">Choose a run</option>
        {runs.map((run) => (
          <option key={run.id} value={run.id}>
            {run.name} ({run.status}) {run.id.slice(0, 8)}, {formatDateTime(run.received_at)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Result({ base, target }: { base: string; target: string }) {
  const [hideUnchanged, setHideUnchanged] = useState(true);
  const result = useAsync(() => compareRuns(base, target), [base, target]);

  if (result.status === "loading") return <LoadingState label="Comparing runs" />;
  if (result.status === "error") return <ErrorState error={result.error} onRetry={result.reload} />;

  const comparison: Comparison = result.data;
  const entries = hideUnchanged ? comparison.entries.filter((e) => e.kind !== "unchanged") : comparison.entries;
  const c = comparison.counts;

  return (
    <section aria-label="Comparison result" className="mt-6">
      {comparison.warnings.map((w) => (
        <p key={w} role="note" className="mb-2 rounded-md border border-dashed border-warn bg-warn-soft px-3 py-2 text-sm text-warn">
          {w}
        </p>
      ))}
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <span><strong className="text-warn">{c.changed}</strong> changed</span>
        <span><strong className="text-ok">{c.added}</strong> only in target</span>
        <span><strong className="text-fault">{c.missing}</strong> only in base</span>
        <span><strong className="text-muted">{c.unchanged}</strong> same</span>
        <label className="ml-auto flex items-center gap-1.5">
          <input type="checkbox" checked={hideUnchanged} onChange={(e) => setHideUnchanged(e.target.checked)} className="accent-ink" />
          Hide unchanged events
        </label>
      </div>
      {entries.length === 0 ? (
        <div className="rounded-lg border border-line bg-panel">
          <EmptyState title="No differences found.">The two runs recorded the same operations with the same results.</EmptyState>
        </div>
      ) : (
        <ComparisonTable entries={entries} />
      )}
      <p className="mt-3 max-w-prose text-xs text-muted">
        Events are matched by their position in the call tree (parent operation, operation name and how many times it ran
        before), not by sequence number. Duration changes are highlighted only when they are at least 5 ms and 50%.
      </p>
    </section>
  );
}

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const base = params.get("base") ?? "";
  const target = params.get("target") ?? "";
  const runs = useAsync(() => listRuns({ limit: 100 }), []);

  const update = (next: { base?: string; target?: string }) => {
    const values = { base, target, ...next };
    const search = new URLSearchParams();
    if (values.base) search.set("base", values.base);
    if (values.target) search.set("target", values.target);
    setParams(search);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Compare two runs</h1>
      <p className="text-sm text-muted">Pick a reference run (base) and a run to check against it (target).</p>

      {runs.status === "loading" && <LoadingState label="Loading runs" />}
      {runs.status === "error" && <ErrorState error={runs.error} onRetry={runs.reload} />}
      {runs.status === "success" && runs.data.items.length < 2 && (
        <EmptyState title="You need at least two runs to compare.">
          <Link to="/" className="underline">Record demo runs</Link> first.
        </EmptyState>
      )}
      {runs.status === "success" && runs.data.items.length >= 2 && (
        <>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <RunSelect label="Base run" value={base} runs={runs.data.items} onChange={(id) => update({ base: id })} />
            <button
              type="button"
              onClick={() => update({ base: target, target: base })}
              disabled={!base && !target}
              className="rounded-md border border-line bg-panel px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Swap
            </button>
            <RunSelect label="Target run" value={target} runs={runs.data.items} onChange={(id) => update({ target: id })} />
          </div>
          {base && target ? <Result base={base} target={target} /> : <EmptyState title="Choose both runs to see the differences." />}
        </>
      )}
    </div>
  );
}
