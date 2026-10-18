"""Stores a batch of validated events for one run.

Rules:
    - The whole batch is saved, or nothing is (one database transaction).
    - Every event's run_id must match the run in the URL.
    - Sending the same event twice is safe (idempotent): the copy is skipped.
      This lets a client retry after a network error without creating duplicates.
    - Two DIFFERENT events claiming the same event_id or the same sequence
      number is a conflict (HTTP 409), because one of them must be wrong.
    - Events may arrive in several batches. After each batch the run summary
      (status, completeness...) is recomputed from ALL stored events.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import EventRecord
from app.models.run import RunRecord
from app.schemas.event import Event
from app.services.errors import ConflictError, InvalidTraceError
from app.services.summary import summarize


@dataclass
class IngestResult:
    run: RunRecord
    accepted: int
    duplicates: int


def _same_event(stored: EventRecord, incoming: Event) -> bool:
    return (
        stored.sequence == incoming.sequence
        and stored.event_type == incoming.event_type.value
        and stored.operation_name == incoming.operation_name
        and stored.parent_event_id == (str(incoming.parent_event_id) if incoming.parent_event_id else None)
    )


def _to_record(event: Event, received_at: datetime) -> EventRecord:
    return EventRecord(
        event_id=str(event.event_id),
        run_id=str(event.run_id),
        parent_event_id=str(event.parent_event_id) if event.parent_event_id else None,
        sequence=event.sequence,
        schema_version=event.schema_version,
        event_type=event.event_type.value,
        operation_name=event.operation_name,
        timestamp=event.timestamp,
        duration_ms=event.duration_ms,
        status=event.status.value,
        attributes=event.attributes,
        error=event.error.model_dump(mode="json") if event.error else None,
        received_at=received_at,
    )


def _dedupe_batch(events: list[Event]) -> tuple[list[Event], int]:
    """Remove exact repeats inside the batch; reject contradictory ones."""
    by_id: dict[str, Event] = {}
    id_by_sequence: dict[int, str] = {}
    unique: list[Event] = []
    for event in events:
        event_id = str(event.event_id)
        if event_id in by_id:
            if by_id[event_id] != event:
                raise ConflictError(f"event_id {event_id} appears twice in the batch with different content")
            continue
        other = id_by_sequence.get(event.sequence)
        if other is not None:
            raise ConflictError(f"sequence {event.sequence} is used by two different events in the batch")
        by_id[event_id] = event
        id_by_sequence[event.sequence] = event_id
        unique.append(event)
    return unique, len(events) - len(unique)


def ingest_events(session: Session, run_id: str, events: list[Event]) -> IngestResult:
    if not events:
        raise InvalidTraceError("the batch contains no events")

    wrong_run = sorted(e.sequence for e in events if str(e.run_id) != run_id)
    if wrong_run:
        raise InvalidTraceError(
            "every event must belong to the run in the URL",
            details={"run_id": run_id, "mismatched_sequences": wrong_run[:20]},
        )

    events, duplicates = _dedupe_batch(events)
    now = datetime.now(timezone.utc)

    try:
        # Events that were already stored earlier (for example, a retry).
        ids = [str(e.event_id) for e in events]
        stored_by_id = {
            r.event_id: r for r in session.scalars(select(EventRecord).where(EventRecord.event_id.in_(ids)))
        }
        new_events: list[Event] = []
        for event in events:
            stored = stored_by_id.get(str(event.event_id))
            if stored is None:
                new_events.append(event)
            elif stored.run_id != run_id:
                raise ConflictError(f"event_id {event.event_id} already belongs to another run")
            elif not _same_event(stored, event):
                raise ConflictError(f"event_id {event.event_id} was already stored with different content")
            else:
                duplicates += 1

        # A new event must not reuse a sequence number already taken in this run.
        sequences = [e.sequence for e in new_events]
        taken = session.scalars(
            select(EventRecord.sequence).where(EventRecord.run_id == run_id, EventRecord.sequence.in_(sequences))
        ).all()
        if taken:
            raise ConflictError(
                "sequence numbers already used in this run by other events",
                details={"sequences": sorted(taken)[:20]},
            )

        run = session.get(RunRecord, run_id)
        if run is None:
            run = RunRecord(
                id=run_id, name="unknown", status="unknown", completeness="incomplete",
                issues=[], event_count=0, error_count=0, received_at=now, updated_at=now,
            )
            session.add(run)

        session.add_all(_to_record(e, now) for e in new_events)
        session.flush()

        all_events = session.scalars(
            select(EventRecord).where(EventRecord.run_id == run_id).order_by(EventRecord.sequence)
        ).all()
        summary = summarize(list(all_events))
        run.name = summary.name
        run.status = summary.status
        run.completeness = summary.completeness
        run.issues = summary.issues
        run.started_at = summary.started_at
        run.duration_ms = summary.duration_ms
        run.event_count = summary.event_count
        run.error_count = summary.error_count
        run.updated_at = now

        session.commit()
    except IntegrityError as exc:
        # The database caught a duplicate that slipped past the checks above
        # (for example, two requests at the same time).
        session.rollback()
        raise ConflictError("the events conflict with events already stored") from exc
    except Exception:
        session.rollback()
        raise

    return IngestResult(run=run, accepted=len(new_events), duplicates=duplicates)
