// Turns the flat list of events into display rows with tree depth.

import type { TraceEvent } from "../types/api";

export interface TraceRow {
  event: TraceEvent;
  depth: number;
  /** true if the event has a parent_event_id that is not in this run */
  orphan: boolean;
}

/** Rows in sequence order. Depth = number of ancestors. */
export function buildRows(events: TraceEvent[]): TraceRow[] {
  const sorted = [...events].sort((a, b) => a.sequence - b.sequence);
  const depthById = new Map<string, number>();
  const known = new Set(sorted.map((e) => e.event_id));

  return sorted.map((event) => {
    const parent = event.parent_event_id;
    const orphan = parent !== null && !known.has(parent);
    // Parents always have a lower sequence, so their depth is already known.
    const depth = parent !== null && !orphan ? (depthById.get(parent) ?? 0) + 1 : 0;
    depthById.set(event.event_id, depth);
    return { event, depth, orphan };
  });
}

/** The exception event that explains why `span` failed (raised in it or below it). */
export function findCause(span: TraceEvent, events: TraceEvent[]): TraceEvent | null {
  const byId = new Map(events.map((e) => [e.event_id, e]));
  for (const candidate of events) {
    if (candidate.event_type !== "exception") continue;
    let cursor: string | null = candidate.parent_event_id;
    while (cursor !== null) {
      if (cursor === span.event_id) return candidate;
      cursor = byId.get(cursor)?.parent_event_id ?? null;
    }
  }
  return null;
}
