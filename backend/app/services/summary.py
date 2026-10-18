"""Builds the summary stored on a run from that run's events."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.services.completeness import find_issues


class SummaryEvent(Protocol):
    event_id: str
    parent_event_id: str | None
    sequence: int
    event_type: str
    status: str
    operation_name: str
    timestamp: datetime
    duration_ms: float | None
    attributes: dict[str, Any]


@dataclass
class RunSummary:
    name: str
    status: str  # ok | error | unknown
    completeness: str  # complete | incomplete
    issues: list[dict[str, str]] = field(default_factory=list)
    started_at: datetime | None = None
    duration_ms: float | None = None
    event_count: int = 0
    error_count: int = 0


def summarize(events: list[SummaryEvent]) -> RunSummary:
    issues = find_issues(events)  # type: ignore[arg-type]
    started = next((e for e in events if str(e.event_type) == "run.started"), None)
    finished = next((e for e in events if str(e.event_type) == "run.finished"), None)

    if started is not None:
        name = str(started.attributes.get("scenario") or started.operation_name)
    elif finished is not None:
        name = finished.operation_name.removeprefix("scenario.")
    else:
        name = "unknown"

    if finished is not None:
        status = str(finished.status)
    elif any(str(e.status) == "error" for e in events):
        status = "error"
    else:
        status = "unknown"  # we cannot say it succeeded if it never finished

    return RunSummary(
        name=name[:100],
        status=status,
        completeness="complete" if not issues else "incomplete",
        issues=[i.to_dict() for i in issues],
        started_at=started.timestamp if started else None,
        duration_ms=finished.duration_ms if finished else None,
        event_count=len(events),
        error_count=sum(1 for e in events if str(e.event_type) == "exception"),
    )
