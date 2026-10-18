// The execution timeline: one row per event, in sequence order.
//
//   seq  operation (indented by depth)   | time track with a bar per event
//
// Bars are positioned with the recorded timestamp and sized with the
// measured duration. During replay an amber playhead marks the current
// event and events not reached yet are dimmed.

import { axisTicks, computeLayout } from "../../lib/timeline";
import { formatDuration, formatTick } from "../../lib/format";
import type { TraceRow } from "../../lib/tree";
import type { TraceEvent } from "../../types/api";

interface Props {
  rows: TraceRow[];
  /** all events of the run, used for the time scale (filters do not change it) */
  allEvents: TraceEvent[];
  selectedId: string | null;
  onSelect: (event: TraceEvent) => void;
  /** sequence of the replay cursor, or null when not replaying */
  cursorSequence: number | null;
}

const COLUMNS = "minmax(14rem, 34%) 1fr 4.5rem"; // label | track | duration

function barColor(event: TraceEvent): string {
  if (event.event_type === "exception") return "bg-fault";
  if (event.status === "error") return "bg-fault/80";
  if (event.event_type === "span") return "bg-ok";
  return "bg-muted";
}

function TypeGlyph({ event }: { event: TraceEvent }) {
  if (event.event_type === "exception") {
    return (
      <span aria-label="exception" className="font-bold text-fault">
        !
      </span>
    );
  }
  if (event.event_type === "run.started" || event.event_type === "run.finished") {
    return <span aria-hidden className="text-muted">{event.event_type === "run.started" ? "▸" : "■"}</span>;
  }
  return <span aria-hidden className={event.status === "error" ? "text-fault" : "text-ok"}>●</span>;
}

export function TraceTimeline({ rows, allEvents, selectedId, onSelect, cursorSequence }: Props) {
  const layout = computeLayout(allEvents);
  const ticks = axisTicks(layout.totalMs);
  const cursorEvent = cursorSequence === null ? null : allEvents.find((e) => e.sequence === cursorSequence);
  const cursorBar = cursorEvent ? layout.bars.get(cursorEvent.event_id) : undefined;

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <div className="min-w-[44rem]">
        {/* Time axis */}
        <div className="grid border-b border-line bg-sunken text-xs text-muted" style={{ gridTemplateColumns: COLUMNS }}>
          <div className="px-3 py-1.5 font-medium">Operation</div>
          <div className="relative mx-2 h-7">
            {ticks.map((t) => (
              <span
                key={t}
                className="absolute top-1.5 -translate-x-1/2 font-mono whitespace-nowrap tabular-nums first:translate-x-0"
                style={{ left: `${(t / layout.totalMs) * 100}%` }}
              >
                {formatTick(t)}
              </span>
            ))}
          </div>
          <div className="px-2 py-1.5 text-right font-medium">Duration</div>
        </div>

        <ol aria-label="Execution events" className="relative">
          {rows.map(({ event, depth, orphan }) => {
            const bar = layout.bars.get(event.event_id) ?? { start: 0, width: 0 };
            const selected = event.event_id === selectedId;
            const isCursor = cursorSequence === event.sequence;
            const notReached = cursorSequence !== null && event.sequence > cursorSequence;
            const instant = event.duration_ms === null;

            return (
              <li key={event.event_id}>
                <button
                  type="button"
                  onClick={() => onSelect(event)}
                  aria-current={isCursor ? "step" : undefined}
                  aria-pressed={selected}
                  data-testid={`row-${event.sequence}`}
                  className={`grid w-full items-center border-b border-line/60 text-left text-sm transition-opacity ${
                    selected ? "bg-cursor-soft" : "hover:bg-sunken"
                  } ${notReached ? "opacity-30" : ""}`}
                  style={{ gridTemplateColumns: COLUMNS }}
                >
                  <span className="flex min-w-0 items-center gap-2 py-1.5 pr-2 pl-3">
                    <span className="w-6 shrink-0 text-right font-mono text-xs tabular-nums text-muted">{event.sequence}</span>
                    <span className="flex min-w-0 items-center gap-1.5" style={{ paddingLeft: `${depth * 0.9}rem` }}>
                      <TypeGlyph event={event} />
                      <span className={`truncate font-mono text-[13px] ${event.event_type === "exception" ? "text-fault" : ""}`}>
                        {event.event_type === "exception" ? event.error?.type ?? "exception" : event.operation_name}
                      </span>
                      {orphan && <span className="shrink-0 rounded bg-warn-soft px-1 text-[11px] text-warn">parent missing</span>}
                    </span>
                  </span>
                  <span className="relative mx-2 h-7">
                    {ticks.map((t) => (
                      <span key={t} aria-hidden className="absolute inset-y-0 w-px bg-line/60" style={{ left: `${(t / layout.totalMs) * 100}%` }} />
                    ))}
                    {instant ? (
                      <span
                        aria-hidden
                        className={`absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rotate-45 ${barColor(event)}`}
                        style={{ left: `${bar.start}%` }}
                      />
                    ) : (
                      <span
                        aria-hidden
                        className={`absolute top-1/2 h-3 -translate-y-1/2 rounded-sm ${barColor(event)} ${isCursor ? "ring-2 ring-cursor ring-offset-1 ring-offset-panel" : ""}`}
                        style={{ left: `${bar.start}%`, width: `max(${bar.width}%, 2px)` }}
                      />
                    )}
                  </span>
                  <span className="px-2 text-right font-mono text-[11px] tabular-nums text-muted">
                    {instant ? "" : formatDuration(event.duration_ms)}
                  </span>
                </button>
              </li>
            );
          })}

          {/* Replay playhead */}
          {cursorBar && (
            <div aria-hidden className="pointer-events-none absolute inset-0 grid" style={{ gridTemplateColumns: COLUMNS }}>
              <div />
              <div className="relative mx-2">
                <div className="absolute inset-y-0 w-0.5 bg-cursor transition-[left] duration-150" style={{ left: `${cursorBar.start}%` }} />
              </div>
              <div />
            </div>
          )}
        </ol>
      </div>
    </div>
  );
}
