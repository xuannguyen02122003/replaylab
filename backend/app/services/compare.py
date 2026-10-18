"""Deterministic comparison of two recorded runs.

Step 1 — give every event a MATCH KEY that describes where it sits in the call tree:

    /^run.started                                    run.started
    /process_order#0                                 first top-level process_order
    /process_order#0/validate_order#0
    /process_order#0/validate_order#0/repository.get_product#1   second get_product inside it
    /process_order#0/inventory.reserve_stock#1/!exception#0      exception raised there
    /$run.finished

    The key is: parent's key + "/" + operation name + "#" + occurrence number.
    The occurrence number counts siblings with the same name, in sequence order.

Step 2 — events with the same key in both runs are a MATCH. Keys only in the
base run are MISSING from the target. Keys only in the target are ADDED.

Step 3 — for each match, compare status, attributes, error and duration.

Why not match by sequence number? If the target run has one extra call early
on, every later sequence number shifts by one and everything would look
"changed". Keys based on the call path stay stable.

Known limitation: inside a loop, matching is by position. If the target run
skips the FIRST iteration, the remaining iterations are compared with the
wrong partners (#1 is compared with #0, and so on).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

# A duration change counts as significant only if it is large in BOTH
# absolute and relative terms. This filters out normal timing noise
# (a 2.1 ms -> 2.4 ms change is +14%, but meaningless).
SIGNIFICANT_DELTA_MS = 5.0
SIGNIFICANT_DELTA_PCT = 50.0


class CompareEvent(Protocol):
    event_id: str
    parent_event_id: str | None
    sequence: int
    event_type: str
    operation_name: str
    status: str
    duration_ms: float | None
    attributes: dict[str, Any]
    error: dict[str, Any] | None


@dataclass
class AttributeChange:
    key: str
    change: str  # added | removed | changed
    base: Any = None
    target: Any = None


@dataclass
class DurationChange:
    base_ms: float
    target_ms: float
    delta_ms: float
    delta_pct: float | None
    significant: bool


@dataclass
class DiffEntry:
    key: str
    kind: str  # unchanged | changed | added | missing
    event_type: str
    operation_name: str
    depth: int
    base_event_id: str | None = None
    target_event_id: str | None = None
    base_sequence: int | None = None
    target_sequence: int | None = None
    status_change: tuple[str, str] | None = None
    attribute_changes: list[AttributeChange] = field(default_factory=list)
    error_change: tuple[str | None, str | None] | None = None
    duration: DurationChange | None = None


@dataclass
class Comparison:
    entries: list[DiffEntry]
    counts: dict[str, int]
    warnings: list[str]


_TYPE_PREFIX = {"span": "", "exception": "!", "run.started": "^", "run.finished": "$"}


def match_keys(events: list[CompareEvent]) -> dict[str, str]:
    """Return {event_id: match key}. Events are processed in sequence order,
    so a parent (lower sequence) always gets its key before its children."""
    keys: dict[str, str] = {}
    occurrences: dict[str, int] = defaultdict(int)
    for event in sorted(events, key=lambda e: e.sequence):
        event_type = str(event.event_type)
        if event_type in ("run.started", "run.finished"):
            keys[str(event.event_id)] = f"/{_TYPE_PREFIX[event_type]}{event_type}"
            continue
        parent = str(event.parent_event_id) if event.parent_event_id else None
        parent_key = keys.get(parent, "/?missing-parent") if parent else ""
        name = "exception" if event_type == "exception" else event.operation_name
        base = f"{parent_key}/{_TYPE_PREFIX.get(event_type, '')}{name}"
        keys[str(event.event_id)] = f"{base}#{occurrences[base]}"
        occurrences[base] += 1
    return keys


def _depth(key: str) -> int:
    return max(key.count("/") - 1, 0)


def _attribute_changes(base: dict[str, Any], target: dict[str, Any]) -> list[AttributeChange]:
    changes = []
    for key in sorted(base.keys() | target.keys()):
        if key not in target:
            changes.append(AttributeChange(key, "removed", base=base[key]))
        elif key not in base:
            changes.append(AttributeChange(key, "added", target=target[key]))
        elif base[key] != target[key] or type(base[key]) is not type(target[key]):
            changes.append(AttributeChange(key, "changed", base=base[key], target=target[key]))
    return changes


def _duration_change(base: float | None, target: float | None) -> DurationChange | None:
    if base is None or target is None:
        return None  # not comparable
    delta = round(target - base, 3)
    pct = round(delta / base * 100, 1) if base > 0 else None
    significant = abs(delta) >= SIGNIFICANT_DELTA_MS and (pct is None or abs(pct) >= SIGNIFICANT_DELTA_PCT)
    return DurationChange(base, target, delta, pct, significant)


def _error_label(error: dict[str, Any] | None) -> str | None:
    if not error:
        return None
    return f"{error.get('type')}: {error.get('message')}"


def _compare_pair(key: str, base: CompareEvent, target: CompareEvent) -> DiffEntry:
    entry = DiffEntry(
        key=key,
        kind="unchanged",
        event_type=str(base.event_type),
        operation_name=base.operation_name,
        depth=_depth(key),
        base_event_id=str(base.event_id),
        target_event_id=str(target.event_id),
        base_sequence=base.sequence,
        target_sequence=target.sequence,
    )
    if str(base.status) != str(target.status):
        entry.status_change = (str(base.status), str(target.status))
    entry.attribute_changes = _attribute_changes(base.attributes or {}, target.attributes or {})
    base_error, target_error = _error_label(base.error), _error_label(target.error)
    if base_error != target_error:
        entry.error_change = (base_error, target_error)
    entry.duration = _duration_change(base.duration_ms, target.duration_ms)

    if entry.status_change or entry.attribute_changes or entry.error_change or (entry.duration and entry.duration.significant):
        entry.kind = "changed"
    return entry


def _one_sided(key: str, event: CompareEvent, kind: str) -> DiffEntry:
    entry = DiffEntry(
        key=key,
        kind=kind,
        event_type=str(event.event_type),
        operation_name=event.operation_name,
        depth=_depth(key),
    )
    if kind == "missing":
        entry.base_event_id, entry.base_sequence = str(event.event_id), event.sequence
    else:
        entry.target_event_id, entry.target_sequence = str(event.event_id), event.sequence
    return entry


def compare_runs(
    base_events: list[CompareEvent],
    target_events: list[CompareEvent],
    *,
    base_name: str = "",
    target_name: str = "",
    base_complete: bool = True,
    target_complete: bool = True,
) -> Comparison:
    base_keys = match_keys(base_events)
    target_keys = match_keys(target_events)
    target_by_key = {target_keys[str(e.event_id)]: e for e in target_events}

    # Walk the base run in sequence order: each event is either matched or missing.
    entries: list[DiffEntry] = []
    matched_target_keys: set[str] = set()
    for event in sorted(base_events, key=lambda e: e.sequence):
        key = base_keys[str(event.event_id)]
        partner = target_by_key.get(key)
        if partner is None:
            entries.append(_one_sided(key, event, "missing"))
        else:
            entries.append(_compare_pair(key, event, partner))
            matched_target_keys.add(key)

    # Insert each added event right after the entry that comes just before it
    # in the target run, so the merged list still reads in execution order.
    for event in sorted(target_events, key=lambda e: e.sequence):
        key = target_keys[str(event.event_id)]
        if key in matched_target_keys:
            continue
        position = 0
        for index, entry in enumerate(entries):
            if entry.target_sequence is not None and entry.target_sequence < event.sequence:
                position = index + 1
        entries.insert(position, _one_sided(key, event, "added"))

    counts = {kind: 0 for kind in ("unchanged", "changed", "added", "missing")}
    for entry in entries:
        counts[entry.kind] += 1

    warnings = []
    if base_name and target_name and base_name != target_name:
        warnings.append(
            f"The runs come from different scenarios ({base_name} vs {target_name}). "
            "Differences in the execution path are expected."
        )
    if not base_complete or not target_complete:
        warnings.append("At least one run is incomplete, so 'missing' events may simply not have been received.")

    return Comparison(entries=entries, counts=counts, warnings=warnings)
