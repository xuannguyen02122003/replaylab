export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatDelta(ms: number): string {
  const sign = ms > 0 ? "+" : ms < 0 ? "−" : "±";
  return `${sign}${formatDuration(Math.abs(ms))}`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

/** Axis labels: "0 ms", "5 ms", "0.5 ms", "1.5 s". */
export function formatTick(ms: number): string {
  if (ms === 0) return "0 ms";
  if (ms >= 1000) return `${Number((ms / 1000).toFixed(2))} s`;
  return `${Number(ms.toFixed(3))} ms`;
}
