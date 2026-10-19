# ReplayLab Architecture

## 1. Parts and responsibilities

```
replaylab/
├── backend/
│   ├── tracer/              PRODUCER: records events from instrumented code
│   │   ├── recorder.py        run(), span(), @traced, set_attribute(), sanitization
│   │   ├── auto.py            automatic tracing of any script with sys.monitoring
│   │   ├── __main__.py        CLI: python -m tracer run script.py
│   │   └── exporter.py        send_events() / send_in_chunks(): HTTP POST (stdlib only)
│   ├── examples/            THE DEMO APP being traced
│   │   ├── order_service/     models, repository, inventory, payment, service, scenarios
│   │   └── run_scenarios.py   CLI: run scenarios and send their events over HTTP
│   ├── app/                 COLLECTOR (FastAPI)
│   │   ├── main.py            create_app(): middleware, error handlers, routers
│   │   ├── config.py          settings from environment variables
│   │   ├── api/               HTTP layer only: parse input, call a service, shape output
│   │   ├── schemas/           Pydantic: event.py (the contract), api.py (request/response)
│   │   ├── services/          business logic: ingest, completeness, summary, compare, queries
│   │   ├── models/            SQLAlchemy ORM tables: runs, events
│   │   └── storage/           engine, sessions, UTC datetime column type
│   └── tests/
├── samples/                 ordinary projects with no ReplayLab code, for automatic tracing
├── frontend/src/
│   ├── api/client.ts        every HTTP call, plus ApiError
│   ├── types/api.ts         TypeScript mirror of the API schemas
│   ├── lib/                 pure logic: tree.ts, timeline.ts, replay.ts, format.ts
│   ├── hooks/               useAsync (loading/error/success), useReplay (timer)
│   ├── components/          TraceTimeline, EventInspector, ReplayControls, RunComparison…
│   └── pages/               RunsPage, RunDetailPage, ComparePage
└── docs/
```

**Rule of thumb:** the `api/` layer knows HTTP, the `services/` layer knows the rules, the `models/` and `storage/` layers know the database. A service never returns an HTTP response. It raises a domain error (`NotFoundError`, `ConflictError`…), and `api/errors.py` turns that into a status code.

## 2. Life of an event

```
inventory.reserve_stock() is called
  │  @traced opens a span: takes sequence 10, reads the parent from a ContextVar
  │  the function raises OutOfStockError
  │  span.__exit__: records an exception event (sequence 11, parent = this span)
  │                  then the span event itself (sequence 10, status "error")
  ▼
the exception passes up through process_order → its span is also "error"
  ▼
run() ends: emits run.finished (sequence 12, status "error")
  ▼
send_events(): POST /api/runs/{run_id}/events   {"events": [...13 events...]}
  ▼
FastAPI + Pydantic validate every field and every per-type rule  → 422 if any is wrong
  ▼
services/ingest.py, inside ONE transaction:
  - every event's run_id matches the URL
  - drop exact duplicates (safe retries), reject contradictory ones (409)
  - insert the new events, then reload ALL events of the run
  - services/summary.py → status, completeness, issues, counts → saved on the run row
  ▼
GET /api/runs/{id}/events → ORDER BY sequence → React builds rows (depth from parents)
```

## 2b. Two ways to produce events

| | Explicit (`@traced`) | Automatic (`python -m tracer run`) |
|---|---|---|
| Code changes | Decorate the functions you care about | None |
| Which functions | Only decorated ones | Every function defined under `--root` |
| Attributes | Business values chosen by the developer (`order_id`, `sku`) | Only `code.file` and `code.line` |
| How | Context manager around the call | `sys.monitoring` callbacks: `PY_START` opens a span, `PY_RETURN` / `PY_UNWIND` closes it |

Both paths use the same `start_span()` / `end_span()` functions, the same validation and the same collector, so the UI cannot tell them apart.

The automatic tracer returns `sys.monitoring.DISABLE` for code outside the project (standard library, packages, ReplayLab itself). Python then stops calling us for that code, which keeps the overhead low. A re-entrancy guard (`_busy`) makes sure code that ReplayLab runs inside its own callback, such as validation, is never recorded as part of the user's script.

## 3. Ordering

- `sequence` is assigned when an operation **starts**, so a parent always has a lower number than its children.
- Events are **emitted** when the operation **finishes**, so children are emitted before their parents. Arrival order is therefore not execution order.
- Everything that displays or compares events sorts by `sequence`. Timestamps are only used to place bars on the time axis.
- The database has a unique constraint on `(run_id, sequence)` as a final safety net.

## 4. Completeness

`services/completeness.py` is a pure function: list of events in, list of issues out. A run is `complete` when it has:

| Check | Issue code |
|-------|------------|
| exactly one `run.started` | `missing_run_started` / `duplicate_run_started` |
| exactly one `run.finished` | `missing_run_finished` / `duplicate_run_finished` |
| sequences 0…N with no gaps | `sequence_gap` |
| `run.finished` is the last sequence | `run_finished_not_last` |
| every parent exists | `missing_parent` |
| every parent is a span | `parent_not_span` |
| parent sequence < child sequence | `child_before_parent` |

The run's `status` comes from `run.finished`. If that event is missing, the status is `unknown` (or `error` if an error was seen). It is never `ok`, because a run that never finished cannot be called successful.

## 5. Run comparison

Implemented in `services/compare.py`.

1. **Match keys.** Walk each run in sequence order and give every event a key made from its path in the call tree:
   `parent key / operation name # occurrence`. For example, `/process_order#0/validate_order#0/repository.get_product#1` is the second `get_product` call inside `validate_order`. Exceptions use `!exception`. `run.started` and `run.finished` get fixed keys.
2. **Match.** The same key in both runs is a match. A key only in the base run is *missing*. A key only in the target run is *added*.
3. **Compare matches.** Status, attributes (added, removed or changed keys), error type and message, and duration.
4. **Duration rule.** A change is *significant* only if it is at least **5 ms and 50%**. This hides timing noise, such as 2.1 ms becoming 2.4 ms.
5. **Order of results.** Base events in sequence order, with each added event inserted after the closest earlier target event.

The same inputs always give the same output, whatever order the events arrive in. Tests check this.

**Why not match by sequence number?** If the target run has one extra call early on, every later number shifts, and the whole run would look changed.

**Limitation:** repeated calls are matched by occurrence number. If the target skips the first iteration of a loop, the later iterations are compared with the wrong partners. Warnings are shown when the runs come from different scenarios or when either trace is incomplete.

## 6. Recorded replay

`frontend/src/lib/replay.ts` is a reducer (a pure state machine) with `index` (null means "not replaying") and `playing`. A timer in `useReplay` dispatches `tick` while playing. The UI dims events after the cursor, draws the playhead at the current event's start time, and points the inspector at the current event. No request is sent to the backend during replay, and no code runs again.

## 7. Security and data handling

- Only predefined scenarios can be executed (`SCENARIOS` dict). Unknown names return 404. The runner can be turned off with `REPLAYLAB_ENABLE_SCENARIO_RUNNER=false`.
- Attributes are explicit, flat, size-limited and redacted by key. This happens in the tracer and again in the collector.
- Stack frames keep only project files, with relative paths, so the developer's home folder never leaks.
- Request bodies over `REPLAYLAB_MAX_REQUEST_BYTES` are rejected with `413`, and batches are limited to 1000 events.
- `extra="forbid"` on every input model: unknown fields are errors, not silently dropped.
- Validation errors return location and message only, never the raw input.

## 8. Scaling (if event volume grew)

1. PostgreSQL instead of SQLite, plus Alembic migrations.
2. Make ingest asynchronous: the API writes batches to a queue, and a worker stores them and recomputes summaries.
3. Send events in chunks during long runs instead of one batch at the end.
4. Retention: delete or archive old runs, and keep summaries.
5. Paginate or window the timeline for runs with tens of thousands of events.
