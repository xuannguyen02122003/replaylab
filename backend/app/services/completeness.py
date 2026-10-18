"""Decides whether a run's trace is complete (docs/event-schema.md, section 7).

These are pure functions: they take a list of events and return a list of
issues. No database, no HTTP, so they are easy to test.

"Complete" is about the TRACE, not the program: a run that crashed with an
exception is still complete if every event was recorded.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Protocol

MAX_LISTED = 10  # avoid huge issue messages for very broken traces


class TraceEvent(Protocol):
    """Anything with these fields works: ORM rows or Pydantic events."""

    event_id: str
    parent_event_id: str | None
    sequence: int
    event_type: str
    status: str


@dataclass(frozen=True)
class Issue:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _id(value: object) -> str:
    return str(value) if value is not None else ""


def _list(values: list[object]) -> str:
    shown = ", ".join(str(v) for v in values[:MAX_LISTED])
    extra = len(values) - MAX_LISTED
    return shown + (f" (+{extra} more)" if extra > 0 else "")


def find_issues(events: list[TraceEvent]) -> list[Issue]:
    if not events:
        return [Issue("no_events", "The run has no events.")]

    issues: list[Issue] = []
    types = Counter(str(e.event_type) for e in events)

    # 1. Exactly one run.started and one run.finished
    for event_type, label in (("run.started", "start"), ("run.finished", "finish")):
        count = types.get(event_type, 0)
        if count == 0:
            issues.append(Issue(f"missing_{event_type.replace('.', '_')}", f"No {event_type} event: the run {label} was not recorded."))
        elif count > 1:
            issues.append(Issue(f"duplicate_{event_type.replace('.', '_')}", f"{count} {event_type} events, expected exactly 1."))

    # 2. Sequence numbers must be 0, 1, 2, ... with no gaps
    sequences = sorted(e.sequence for e in events)
    present = set(sequences)
    missing = [n for n in range(sequences[-1] + 1) if n not in present]
    if missing:
        issues.append(Issue("sequence_gap", f"Missing sequence numbers: {_list(missing)}."))

    # 3. run.finished must be the last event
    finished = [e for e in events if str(e.event_type) == "run.finished"]
    if len(finished) == 1 and finished[0].sequence != sequences[-1]:
        issues.append(Issue("run_finished_not_last", "run.finished is not the event with the highest sequence."))

    # 4. Every parent must exist, be a span, and start before its child
    by_id = {_id(e.event_id): e for e in events}
    missing_parents: list[object] = []
    not_span: list[object] = []
    out_of_order: list[object] = []
    for e in sorted(events, key=lambda e: e.sequence):
        if e.parent_event_id is None:
            continue
        parent = by_id.get(_id(e.parent_event_id))
        if parent is None:
            missing_parents.append(e.sequence)
        elif str(parent.event_type) != "span":
            not_span.append(e.sequence)
        elif parent.sequence >= e.sequence:
            out_of_order.append(e.sequence)
    if missing_parents:
        issues.append(Issue("missing_parent", f"Events whose parent was not received (sequence): {_list(missing_parents)}."))
    if not_span:
        issues.append(Issue("parent_not_span", f"Events whose parent is not a span (sequence): {_list(not_span)}."))
    if out_of_order:
        issues.append(Issue("child_before_parent", f"Events with a lower sequence than their parent: {_list(out_of_order)}."))

    return issues
