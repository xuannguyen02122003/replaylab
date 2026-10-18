import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, getRun, listAllEvents } from "../api/client";
import { DEFAULT_FILTERS, EventFilters, isFiltered, type FilterState } from "../components/EventFilters";
import { EventInspector } from "../components/EventInspector/EventInspector";
import { IssuesBanner } from "../components/IssuesBanner";
import { ReplayControls } from "../components/ReplayControls/ReplayControls";
import { CompletenessBadge, StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/StateViews";
import { TraceTimeline } from "../components/TraceTimeline/TraceTimeline";
import { useAsync } from "../hooks/useAsync";
import { useReplay } from "../hooks/useReplay";
import { formatDateTime, formatDuration } from "../lib/format";
import { buildRows } from "../lib/tree";
import type { Run, TraceEvent } from "../types/api";

function RunTrace({ run, events }: { run: Run; events: TraceEvent[] }) {
  const rows = useMemo(() => buildRows(events), [events]);
  const ordered = useMemo(() => rows.map((r) => r.event), [rows]);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [speed, setSpeed] = useState(1);
  const [replay, dispatch] = useReplay(ordered.length, speed);

  // While replaying, the inspector follows the replay cursor.
  const cursorEvent = replay.index === null ? null : ordered[replay.index];
  const shownId = cursorEvent?.event_id ?? selectedId;
  const shown = ordered.find((e) => e.event_id === shownId) ?? null;

  const search = filters.search.trim().toLowerCase();
  const visible = rows.filter(
    ({ event }) =>
      filters.types.includes(event.event_type) &&
      (!filters.errorsOnly || event.status === "error") &&
      (search === "" ||
        event.operation_name.toLowerCase().includes(search) ||
        (event.error?.type.toLowerCase().includes(search) ?? false)),
  );

  const select = (event: TraceEvent) => {
    setSelectedId(event.event_id);
    if (replay.index !== null) dispatch({ type: "seek", index: ordered.indexOf(event) });
  };

  return (
    <>
      <ReplayControls state={replay} dispatch={dispatch} speed={speed} onSpeedChange={setSpeed} />
      <div className="mt-4 grid items-start gap-4 lg:grid-cols-[1fr_24rem]">
        <section aria-label="Timeline" className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <EventFilters value={filters} onChange={setFilters} />
            <span className="text-xs text-muted">
              Showing {visible.length} of {rows.length} events
            </span>
          </div>
          {visible.length === 0 ? (
            <div className="rounded-lg border border-line bg-panel">
              <EmptyState title="No events match these filters.">
                <button type="button" onClick={() => setFilters(DEFAULT_FILTERS)} className="underline">
                  Clear filters
                </button>
              </EmptyState>
            </div>
          ) : (
            <TraceTimeline
              rows={visible}
              allEvents={ordered}
              selectedId={shownId}
              onSelect={select}
              cursorSequence={cursorEvent?.sequence ?? null}
            />
          )}
          {isFiltered(filters) && replay.index !== null && (
            <p className="mt-2 text-xs text-muted">Replay steps through all events, including ones hidden by filters.</p>
          )}
        </section>
        <div className="lg:sticky lg:top-4">
          <EventInspector event={shown} events={ordered} onSelect={select} />
        </div>
      </div>
      <p className="mt-6 font-mono text-xs text-muted">run {run.id}</p>
    </>
  );
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const data = useAsync(async () => {
    const [run, events] = await Promise.all([getRun(runId), listAllEvents(runId)]);
    return { run, events };
  }, [runId]);

  if (data.status === "loading") return <LoadingState label="Loading trace" />;
  if (data.status === "error") {
    if (data.error instanceof ApiError && data.error.status === 404) {
      return (
        <EmptyState title="Run not found.">
          It may have been recorded on another server. <Link to="/" className="underline">Back to all runs</Link>
        </EmptyState>
      );
    }
    return <ErrorState error={data.error} onRetry={data.reload} />;
  }

  const { run, events } = data.data;
  return (
    <div>
      <Link to="/" className="text-sm text-muted hover:text-ink">
        All runs
      </Link>
      <div className="mt-1 mb-4 flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="font-mono text-2xl font-medium tracking-tight">{run.name}</h1>
        <StatusBadge status={run.status} />
        <CompletenessBadge completeness={run.completeness} />
        <span className="text-sm text-muted">
          {run.event_count} events
          {run.duration_ms !== null ? ` in ${formatDuration(run.duration_ms)}` : ", total duration unknown"}, recorded{" "}
          {formatDateTime(run.received_at)}
        </span>
      </div>
      {run.completeness === "incomplete" && (
        <div className="mb-4">
          <IssuesBanner issues={run.issues} />
        </div>
      )}
      {events.length === 0 ? <EmptyState title="This run has no events." /> : <RunTrace run={run} events={events} />}
    </div>
  );
}
