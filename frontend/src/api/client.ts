// All HTTP calls to the collector live here, so components never call fetch directly.

import type { Comparison, IngestResponse, Page, Run, Scenario, TraceEvent } from "../types/api";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

/** An error the UI can show: HTTP status plus the backend's error code and message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the ReplayLab collector. Check that the backend is running.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "http_error",
      error?.message ?? `Request failed with status ${response.status}.`,
      error?.details ?? null,
    );
  }
  return body as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export interface RunFilters {
  status?: string;
  completeness?: string;
  limit?: number;
  offset?: number;
}

export function listRuns(filters: RunFilters = {}): Promise<Page<Run>> {
  return request(`/api/runs${query({ ...filters })}`);
}

export function getRun(runId: string): Promise<Run> {
  return request(`/api/runs/${encodeURIComponent(runId)}`);
}

/** Loads every event of a run, page by page, ordered by sequence. */
export async function listAllEvents(runId: string): Promise<TraceEvent[]> {
  const pageSize = 1000;
  const events: TraceEvent[] = [];
  for (let offset = 0; ; offset += pageSize) {
    const page = await request<Page<TraceEvent>>(
      `/api/runs/${encodeURIComponent(runId)}/events${query({ limit: pageSize, offset })}`,
    );
    events.push(...page.items);
    if (page.items.length === 0 || events.length >= page.total) return events;
  }
}

export function listScenarios(): Promise<Scenario[]> {
  return request("/api/scenarios");
}

export function runScenario(name: string): Promise<IngestResponse> {
  return request(`/api/scenarios/${encodeURIComponent(name)}/runs`, { method: "POST" });
}

export function compareRuns(base: string, target: string): Promise<Comparison> {
  return request(`/api/compare${query({ base, target })}`);
}
