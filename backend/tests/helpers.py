"""Helpers to build event lists for tests."""

import random
import uuid
from typing import Any


def build_run(span_names: tuple[str, ...] = ("process_order", "validate_order")) -> list[dict[str, Any]]:
    """A small valid run: run.started, a parent span with children, run.finished.

    The first name is the parent span; the others are its children.
    """
    run_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())

    def event(sequence: int, event_type: str, name: str, **extra: Any) -> dict[str, Any]:
        base = {
            "schema_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_event_id": None,
            "sequence": sequence,
            "event_type": event_type,
            "operation_name": name,
            "timestamp": f"2026-10-11T11:20:00.{sequence:03d}Z",
            "duration_ms": 1.0 if event_type in ("span", "run.finished") else None,
            "status": "ok",
            "attributes": {},
            "error": None,
        }
        base.update(extra)
        return base

    events = [event(0, "run.started", "scenario.test", attributes={"scenario": "test"})]
    events.append(event(1, "span", span_names[0], event_id=parent_id, duration_ms=10.0))
    for i, name in enumerate(span_names[1:], start=2):
        events.append(event(i, "span", name, parent_event_id=parent_id))
    events.append(event(len(events), "run.finished", "scenario.test", duration_ms=12.0))
    return events


def shuffled(events: list[dict[str, Any]], seed: int = 7) -> list[dict[str, Any]]:
    copy = list(events)
    random.Random(seed).shuffle(copy)
    return copy
