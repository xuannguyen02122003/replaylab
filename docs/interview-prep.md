# Interview Preparation

Questions you should be able to answer about ReplayLab, with where the answer lives in the code. Answers come from the real implementation, not textbook theory. We will go through them together during the teaching phase.

| # | Question | Where to look |
|---|----------|---------------|
| 1 | Why this architecture (a modular monolith with api / services / models layers)? | `docs/architecture.md` §1, `backend/app/` |
| 2 | How does one event travel from the Python app to the screen? | `docs/architecture.md` §2, `tracer/recorder.py`, `services/ingest.py`, `pages/RunDetailPage.tsx` |
| 3 | How are parent and child events linked? How does the tracer know the parent? | `ContextVar` `_current_span` in `tracer/recorder.py`, `lib/tree.ts` |
| 4 | Why do children arrive before their parents, and why is that fine? | `docs/event-schema.md` §6 |
| 5 | How do you handle missing or out-of-order events? | `services/completeness.py`, `queries.list_events` (ORDER BY sequence), `IssuesBanner.tsx` |
| 6 | What is the difference between a complete trace and a successful run? | `services/summary.py` |
| 7 | What happens if the client sends the same batch twice? Or two different events with the same sequence? | `services/ingest.py`, `tests/test_ingest_api.py` |
| 8 | How does recorded replay differ from re-running the program? | `lib/replay.ts`, `hooks/useReplay.ts` |
| 9 | How does the comparison algorithm match events? What are its limits? | `services/compare.py` docstring, `tests/test_compare.py` |
| 10 | Why is a 2 ms → 2.4 ms change not highlighted? | `SIGNIFICANT_DELTA_MS` / `_PCT` in `services/compare.py` |
| 11 | How do you stop sensitive data from leaking into traces? | `redact_attributes`, `sanitize_attributes`, `_stack_frames` |
| 12 | Why validate events in both the tracer and the collector? | `Recorder.emit`, `IngestRequest` |
| 13 | Why `StrEnum` instead of `(str, Enum)`? (a real bug found while building) | `app/schemas/event.py` |
| 14 | Why a custom `UTCDateTime` column type? | `storage/database.py` |
| 15 | How is the frontend tested without a running backend? | `test/fixtures.ts` (`mockFetch`), `pages/*.test.tsx` |
| 16 | What are the current limitations? | README "Limitations" |
| 17 | How would you scale this if event volume grew 1000×? | `docs/architecture.md` §8 |
| 18 | What would you build with one more month? | README "Future improvements" |
| 19 | How can you trace a script without changing its code? Why not `sys.settrace`? | `tracer/auto.py` docstring |
| 20 | What stops the tracer from recording the standard library, or itself? | `_compute_name`, `DISABLE`, `_busy` in `tracer/auto.py` |
