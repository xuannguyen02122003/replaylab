"""Read-only queries for runs and events."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import EventRecord
from app.models.run import RunRecord
from app.services.errors import NotFoundError


def list_runs(
    session: Session,
    *,
    status: str | None = None,
    completeness: str | None = None,
    name: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[RunRecord], int]:
    query = select(RunRecord)
    if status:
        query = query.where(RunRecord.status == status)
    if completeness:
        query = query.where(RunRecord.completeness == completeness)
    if name:
        query = query.where(RunRecord.name == name)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    # id as a tie-breaker so the order is stable when two runs share a timestamp.
    items = session.scalars(
        query.order_by(RunRecord.received_at.desc(), RunRecord.id).limit(limit).offset(offset)
    ).all()
    return list(items), total


def get_run(session: Session, run_id: str) -> RunRecord:
    run = session.get(RunRecord, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    return run


def list_events(
    session: Session,
    run_id: str,
    *,
    event_types: list[str] | None = None,
    status: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> tuple[list[EventRecord], int]:
    get_run(session, run_id)  # 404 if the run does not exist
    query = select(EventRecord).where(EventRecord.run_id == run_id)
    if event_types:
        query = query.where(EventRecord.event_type.in_(event_types))
    if status:
        query = query.where(EventRecord.status == status)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    # Always ordered by sequence: never by timestamp or arrival order.
    items = session.scalars(query.order_by(EventRecord.sequence).limit(limit).offset(offset)).all()
    return list(items), total


def all_events(session: Session, run_id: str) -> list[EventRecord]:
    get_run(session, run_id)
    return list(
        session.scalars(select(EventRecord).where(EventRecord.run_id == run_id).order_by(EventRecord.sequence))
    )
