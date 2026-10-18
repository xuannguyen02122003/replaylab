// Small hand-built events for frontend tests. Real runs are tested on the backend.

import type { Run, TraceEvent } from "../types/api";

const RUN_ID = "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d";

export function makeEvent(overrides: Partial<TraceEvent> & Pick<TraceEvent, "sequence">): TraceEvent {
  return {
    event_id: `evt-${overrides.sequence}`,
    run_id: RUN_ID,
    parent_event_id: null,
    schema_version: "1.0",
    event_type: "span",
    operation_name: `op_${overrides.sequence}`,
    timestamp: `2026-10-11T11:20:00.${String(overrides.sequence).padStart(3, "0")}Z`,
    duration_ms: 1,
    status: "ok",
    attributes: {},
    error: null,
    ...overrides,
  };
}

/** run.started, process_order > (validate_order, reserve_stock > exception), run.finished */
export const failedRunEvents: TraceEvent[] = [
  makeEvent({ sequence: 0, event_type: "run.started", operation_name: "scenario.order_out_of_stock", duration_ms: null }),
  makeEvent({ sequence: 1, event_id: "evt-1", operation_name: "process_order", status: "error", duration_ms: 15 }),
  makeEvent({ sequence: 2, parent_event_id: "evt-1", operation_name: "validate_order", attributes: { order_id: "ORD-1001" } }),
  makeEvent({
    sequence: 3,
    event_id: "evt-3",
    parent_event_id: "evt-1",
    operation_name: "inventory.reserve_stock",
    status: "error",
    duration_ms: 9,
    attributes: { sku: "SKU-123", card_token: "[REDACTED]" },
  }),
  makeEvent({
    sequence: 4,
    parent_event_id: "evt-3",
    event_type: "exception",
    operation_name: "inventory.reserve_stock",
    status: "error",
    duration_ms: null,
    timestamp: "2026-10-11T11:20:00.012Z",
    error: {
      type: "OutOfStockError",
      message: "Product SKU-123 has 0 units available",
      stack: [
        { file: "examples/order_service/inventory.py", line: 21, function: "reserve_stock" },
        { file: "examples/order_service/service.py", line: 42, function: "process_order" },
      ],
    },
  }),
  makeEvent({ sequence: 5, event_type: "run.finished", operation_name: "scenario.order_out_of_stock", status: "error", duration_ms: 17, timestamp: "2026-10-11T11:20:00.000Z" }),
];

export function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: RUN_ID,
    name: "order_out_of_stock",
    status: "error",
    completeness: "complete",
    issues: [],
    started_at: "2026-10-11T11:20:00.000Z",
    duration_ms: 17,
    event_count: 6,
    error_count: 1,
    received_at: "2026-10-11T11:20:01.000Z",
    updated_at: "2026-10-11T11:20:01.000Z",
    ...overrides,
  };
}

/** Replaces fetch with a function that answers by URL. */
export function mockFetch(routes: Record<string, () => { status?: number; body: unknown } | Promise<never>>) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const match = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((prefix) => url.startsWith(prefix));
    if (!match) throw new Error(`unexpected request: ${url}`);
    const result = await routes[match]();
    return new Response(JSON.stringify(result.body), { status: result.status ?? 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
