# ReplayLab Event Schema

Status: **Draft v1.0** (not yet implemented in code)

This document defines the contract between the instrumented Python application (the *producer*) and the ReplayLab collector (the *consumer*). The backend Pydantic schemas and the frontend TypeScript types must both match this document. If they disagree, this document is the source of truth until it is deliberately changed.

---

## 1. Core concepts

| Term | Meaning |
|------|---------|
| **Run** | One execution of a demo scenario, from start to finish. Identified by `run_id`. |
| **Event** | One recorded fact about that execution. Identified by `event_id`. |
| **Span** | An event that represents a timed operation (for example, `validate_order`). It has a duration and a status. |
| **Parent** | The span that was running when another event happened. Used to build the call tree. |

Model choice: **one event per finished operation** (span model).
An operation is recorded once, when it finishes, with its start time and measured duration.

---

## 2. Event types

| `event_type` | When it is emitted | Has duration? | Has error? |
|--------------|--------------------|---------------|------------|
| `run.started` | Once, at the very start of a run | No | No |
| `span` | When an instrumented operation finishes (success or failure) | Yes | No |
| `exception` | When an exception is raised inside a span (recorded once, where it was raised) | No | Yes |
| `run.finished` | Once, at the very end of a run | Yes (total run time) | No |

A span that fails has `status: "error"`. The details of the failure (type, message, stack) live in the `exception` event whose `parent_event_id` points to the innermost failing span. Spans further up the call chain also get `status: "error"` if the exception propagated through them.

---

## 3. Event fields

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `schema_version` | string | yes | Must be `"1.0"` |
| `event_id` | string (UUID v4) | yes | Unique across all runs |
| `run_id` | string (UUID v4) | yes | Same value for every event in a run |
| `parent_event_id` | string (UUID v4) or `null` | yes | `null` only for `run.started`, `run.finished` and top-level spans. Must refer to a `span` in the same run |
| `sequence` | integer ≥ 0 | yes | Unique within a run. Assigned when the operation **starts**. `run.started` is always `0` |
| `event_type` | enum | yes | One of the four types in section 2 |
| `operation_name` | string | yes | 1–100 characters, pattern `^[a-zA-Z0-9_.\-]+$` (for example `repository.get_product`) |
| `timestamp` | string (ISO 8601, UTC, with offset) | yes | Wall-clock time when the operation started or the event occurred |
| `duration_ms` | number ≥ 0 or `null` | yes | Required for `span` and `run.finished`. Must be `null` for `run.started` and `exception` |
| `status` | `"ok"` or `"error"` | yes | `exception` events are always `"error"`. `run.started` is always `"ok"` |
| `attributes` | object | yes (may be `{}`) | See section 5 |
| `error` | object or `null` | yes | Required for `exception`, must be `null` for every other type. See section 4 |

---

## 4. Error object

```json
{
  "type": "OutOfStockError",
  "message": "Product SKU-123 has 0 units available",
  "stack": [
    { "file": "examples/order_service/inventory.py", "line": 42, "function": "reserve_stock" },
    { "file": "examples/order_service/service.py", "line": 18, "function": "process_order" }
  ]
}
```

| Field | Rules |
|-------|-------|
| `type` | Exception class name, 1–200 characters |
| `message` | 0–1000 characters, sanitized (section 5) |
| `stack` | 0–50 frames, innermost frame first. `file` is a path relative to the project root, never an absolute path from the developer's machine |

---

## 5. Attributes and sanitization

`attributes` holds small, explicitly chosen facts about an operation, such as `order_id`, `quantity`, or `cache_hit`.

Limits:
- Flat object only (no nested objects or arrays) in v1.0
- At most 20 keys
- Keys: 1–64 characters, pattern `^[a-zA-Z0-9_.]+$`
- Values: string (max 500 characters), integer, float, boolean, or `null`

Sanitization (applied by the instrumentation **before** sending, and checked again by the collector):
- Keys matching `password`, `secret`, `token`, `api_key`, `authorization`, `card` (case-insensitive substring match) have their value replaced with `"[REDACTED]"`
- Strings longer than the limit are truncated and end with `…[truncated]`
- Local variables are **never** captured automatically. Only values the developer passes on purpose are recorded

---

## 6. Ordering rules

1. **`sequence` is the source of truth for order.** Timestamps are for display only.
2. `sequence` is assigned when an operation *starts*, but the span event is *sent* when it finishes. So children are sent before their parent, but the parent still has the lower sequence number.
3. A child's `sequence` is always greater than its parent's `sequence`.
4. `run.finished` has the highest `sequence` in the run.

Why not sort by timestamp? Two events can share the same millisecond, wall clocks can jump (NTP adjustments), and the order events arrive in is not the order they started in.

Durations are measured with a monotonic clock (`time.perf_counter()`), not by subtracting two wall-clock timestamps.

---

## 7. Run completeness

The collector computes a run's state from the events it has. A run is never shown as complete just because some events arrived.

| State | Condition |
|-------|-----------|
| `complete` | Exactly one `run.started` (sequence 0), exactly one `run.finished`, no sequence gaps, and every `parent_event_id` resolves to a span in the run |
| `incomplete` | Any of those conditions fails. The UI must show which check failed |

A finished run whose code raised an exception is still `complete` (the trace is whole). Its `run.finished` event simply has `status: "error"`. *Trace completeness* and *run success* are separate ideas.

---

## 8. Example: a failed order run

```json
[
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e01",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": null,
    "sequence": 0,
    "event_type": "run.started",
    "operation_name": "scenario.order_out_of_stock",
    "timestamp": "2026-10-11T11:20:00.000Z",
    "duration_ms": null,
    "status": "ok",
    "attributes": { "scenario": "order_out_of_stock" },
    "error": null
  },
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e02",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": null,
    "sequence": 1,
    "event_type": "span",
    "operation_name": "process_order",
    "timestamp": "2026-10-11T11:20:00.002Z",
    "duration_ms": 14.8,
    "status": "error",
    "attributes": { "order_id": "ORD-1001", "item_count": 2 },
    "error": null
  },
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e03",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e02",
    "sequence": 2,
    "event_type": "span",
    "operation_name": "validate_order",
    "timestamp": "2026-10-11T11:20:00.003Z",
    "duration_ms": 1.2,
    "status": "ok",
    "attributes": { "order_id": "ORD-1001" },
    "error": null
  },
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e04",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e02",
    "sequence": 3,
    "event_type": "span",
    "operation_name": "inventory.reserve_stock",
    "timestamp": "2026-10-11T11:20:00.005Z",
    "duration_ms": 9.6,
    "status": "error",
    "attributes": { "sku": "SKU-123", "requested": 3 },
    "error": null
  },
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e05",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e04",
    "sequence": 4,
    "event_type": "exception",
    "operation_name": "inventory.reserve_stock",
    "timestamp": "2026-10-11T11:20:00.014Z",
    "duration_ms": null,
    "status": "error",
    "attributes": {},
    "error": {
      "type": "OutOfStockError",
      "message": "Product SKU-123 has 0 units available",
      "stack": [
        { "file": "examples/order_service/inventory.py", "line": 42, "function": "reserve_stock" },
        { "file": "examples/order_service/service.py", "line": 18, "function": "process_order" }
      ]
    }
  },
  {
    "schema_version": "1.0",
    "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e06",
    "run_id": "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d",
    "parent_event_id": null,
    "sequence": 5,
    "event_type": "run.finished",
    "operation_name": "scenario.order_out_of_stock",
    "timestamp": "2026-10-11T11:20:00.017Z",
    "duration_ms": 17.0,
    "status": "error",
    "attributes": {},
    "error": null
  }
]
```

---

## 9. Out of scope for v1.0

- Nested attribute values (objects, arrays)
- Events for operations that started but never finished (a crash mid-operation shows up as a missing `run.finished`, which makes the run `incomplete`)
- Multiple threads or async tasks running in parallel within one run
- Capturing local variables or function arguments automatically

## 10. Change log

| Version | Date | Change |
|---------|------|--------|
| 1.0 (draft) | 2026-10-11 | Initial draft |
