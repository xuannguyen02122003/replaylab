// Computes where each bar is drawn on the timeline, as percentages of the run.
//
// Position uses the wall-clock timestamp (when it started); width uses the
// measured duration. Order is NOT decided here: rows keep sequence order.

import type { TraceEvent } from "../types/api";

export interface BarLayout {
  /** left edge, 0–100 */
  start: number;
  /** width, 0–100. 0 for instant events (run.started, exception). */
  width: number;
}

export interface TimelineLayout {
  totalMs: number;
  bars: Map<string, BarLayout>;
}

export function computeLayout(events: TraceEvent[]): TimelineLayout {
  const bars = new Map<string, BarLayout>();
  if (events.length === 0) return { totalMs: 0, bars };

  const starts = events.map((e) => Date.parse(e.timestamp));
  const origin = Math.min(...starts);
  const end = Math.max(...events.map((e, i) => starts[i] - origin + (e.duration_ms ?? 0)));
  const totalMs = Math.max(end, 1);

  events.forEach((event, i) => {
    const start = Math.min(((starts[i] - origin) / totalMs) * 100, 100);
    const width = Math.min(((event.duration_ms ?? 0) / totalMs) * 100, 100 - start);
    bars.set(event.event_id, { start, width });
  });
  return { totalMs, bars };
}

/** Tick marks for the time axis, e.g. 0, 5, 10, 15 ms. */
export function axisTicks(totalMs: number, count = 4): number[] {
  if (totalMs <= 0) return [0];
  const raw = totalMs / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let t = 0; t <= totalMs + 1e-9; t += step) ticks.push(Number(t.toFixed(6)));
  return ticks;
}
