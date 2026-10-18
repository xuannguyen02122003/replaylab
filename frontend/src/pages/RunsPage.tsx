import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, listRuns, listScenarios, runScenario } from "../api/client";
import { CompletenessBadge, StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/StateViews";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, formatDuration } from "../lib/format";

const PAGE_SIZE = 20;

function ScenarioPanel() {
  const navigate = useNavigate();
  const scenarios = useAsync(listScenarios, []);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async (name: string) => {
    setRunning(name);
    setError(null);
    try {
      const result = await runScenario(name);
      navigate(`/runs/${result.run.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The scenario could not be run.");
      setRunning(null);
    }
  };

  return (
    <section aria-labelledby="scenarios-title" className="rounded-lg border border-line bg-panel">
      <div className="border-b border-line px-4 py-3">
        <h2 id="scenarios-title" className="font-semibold">Record a demo run</h2>
        <p className="mt-0.5 text-sm text-muted">Runs the instrumented order service once and stores the events it emits.</p>
      </div>
      {scenarios.status === "loading" && <LoadingState label="Loading scenarios" />}
      {scenarios.status === "error" && <ErrorState error={scenarios.error} onRetry={scenarios.reload} />}
      {scenarios.status === "success" && (
        <ul className="divide-y divide-line/60">
          {scenarios.data.map((s) => (
            <li key={s.name} className="flex items-start gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-[13px]">{s.name}</p>
                <p className="text-xs text-muted">{s.description}</p>
              </div>
              <button
                type="button"
                onClick={() => start(s.name)}
                disabled={running !== null}
                className="shrink-0 rounded-md bg-ink px-3 py-1 text-sm font-medium text-panel hover:opacity-90 disabled:opacity-40"
              >
                {running === s.name ? "Running" : "Run"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="border-t border-line px-4 py-2 text-sm text-fault">
          {error}
        </p>
      )}
    </section>
  );
}

export function RunsPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [completeness, setCompleteness] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const runs = useAsync(() => listRuns({ status, completeness, limit: PAGE_SIZE, offset }), [status, completeness, offset]);

  const toggle = (id: string) =>
    setSelected((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current.slice(-1), id]));

  const filtersActive = status !== "" || completeness !== "";

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <section aria-labelledby="runs-title" className="min-w-0">
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div className="mr-auto">
            <h1 id="runs-title" className="text-2xl font-bold tracking-tight">Recorded runs</h1>
            <p className="text-sm text-muted">Every run was captured from real execution of the demo app.</p>
          </div>
          <label className="text-sm">
            <span className="mr-1 text-muted">Result</span>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="rounded-md border border-line bg-panel px-2 py-1">
              <option value="">All</option>
              <option value="ok">Succeeded</option>
              <option value="error">Failed</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="mr-1 text-muted">Trace</span>
            <select value={completeness} onChange={(e) => { setCompleteness(e.target.value); setOffset(0); }} className="rounded-md border border-line bg-panel px-2 py-1">
              <option value="">All</option>
              <option value="complete">Complete</option>
              <option value="incomplete">Incomplete</option>
            </select>
          </label>
          <button
            type="button"
            disabled={selected.length !== 2}
            onClick={() => navigate(`/compare?base=${selected[0]}&target=${selected[1]}`)}
            className="rounded-md border border-ink px-3 py-1 text-sm font-medium disabled:border-line disabled:text-muted"
          >
            Compare selected ({selected.length}/2)
          </button>
        </div>

        <div className="rounded-lg border border-line bg-panel">
          {runs.status === "loading" && <LoadingState label="Loading runs" />}
          {runs.status === "error" && <ErrorState error={runs.error} onRetry={runs.reload} />}
          {runs.status === "success" && runs.data.items.length === 0 && (
            <EmptyState title={filtersActive ? "No runs match these filters." : "No runs recorded yet."}>
              {filtersActive ? "Change the filters to see other runs." : "Run a demo scenario to record your first trace."}
            </EmptyState>
          )}
          {runs.status === "success" && runs.data.items.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[40rem] text-sm">
                  <thead className="bg-sunken text-left text-xs text-muted">
                    <tr>
                      <th scope="col" className="w-10 px-3 py-2"><span className="sr-only">Select for comparison</span></th>
                      <th scope="col" className="px-3 py-2 font-medium">Scenario</th>
                      <th scope="col" className="px-3 py-2 font-medium">Result</th>
                      <th scope="col" className="px-3 py-2 font-medium">Trace</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Events</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Duration</th>
                      <th scope="col" className="px-3 py-2 font-medium">Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.data.items.map((run) => (
                      <tr key={run.id} className="border-t border-line/60 hover:bg-sunken">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            aria-label={`Select ${run.name} for comparison`}
                            checked={selected.includes(run.id)}
                            onChange={() => toggle(run.id)}
                            className="accent-ink"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <Link to={`/runs/${run.id}`} className="font-mono text-[13px] font-medium hover:underline">
                            {run.name}
                          </Link>
                          <span className="ml-2 font-mono text-xs text-muted">{run.id.slice(0, 8)}</span>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap"><StatusBadge status={run.status} /></td>
                        <td className="px-3 py-2 whitespace-nowrap"><CompletenessBadge completeness={run.completeness} /></td>
                        <td className="px-3 py-2 text-right font-mono text-xs whitespace-nowrap tabular-nums">
                          {run.event_count}
                          {run.error_count > 0 && <span className="ml-1 text-fault" title="exceptions recorded">({run.error_count} exc)</span>}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs whitespace-nowrap tabular-nums">{formatDuration(run.duration_ms)}</td>
                        <td className="px-3 py-2 text-xs whitespace-nowrap text-muted">{formatDateTime(run.received_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <nav aria-label="Pagination" className="flex items-center justify-between border-t border-line px-3 py-2 text-sm">
                <span className="text-muted">
                  {offset + 1}–{offset + runs.data.items.length} of {runs.data.total}
                </span>
                <span className="flex gap-2">
                  <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded-md border border-line px-2 py-0.5 disabled:opacity-40">
                    Previous
                  </button>
                  <button type="button" disabled={offset + PAGE_SIZE >= runs.data.total} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded-md border border-line px-2 py-0.5 disabled:opacity-40">
                    Next
                  </button>
                </span>
              </nav>
            </>
          )}
        </div>
      </section>
      <ScenarioPanel />
    </div>
  );
}
