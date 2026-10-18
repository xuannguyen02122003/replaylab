"""Run and event endpoints: ingest, list, detail."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas.api import (
    ErrorResponse,
    EventOut,
    EventPage,
    IngestRequest,
    IngestResponse,
    RunOut,
    RunPage,
)
from app.services import queries
from app.services.ingest import ingest_events

router = APIRouter(prefix="/api/runs", tags=["runs"])

SessionDep = Annotated[Session, Depends(get_session)]
ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.post("/{run_id}/events", status_code=201, response_model=IngestResponse, responses=ERRORS)
def ingest(run_id: UUID, body: IngestRequest, session: SessionDep) -> IngestResponse:
    """Store a batch of events for one run (all or nothing)."""
    result = ingest_events(session, str(run_id), body.events)
    return IngestResponse(run=RunOut.model_validate(result.run), accepted=result.accepted, duplicates=result.duplicates)


@router.get("", response_model=RunPage)
def list_runs(
    session: SessionDep,
    status: Annotated[str | None, Query(pattern="^(ok|error|unknown)$")] = None,
    completeness: Annotated[str | None, Query(pattern="^(complete|incomplete)$")] = None,
    name: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    items, total = queries.list_runs(
        session, status=status, completeness=completeness, name=name, limit=limit, offset=offset
    )
    return RunPage(items=[RunOut.model_validate(r) for r in items], total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunOut, responses=ERRORS)
def get_run(run_id: UUID, session: SessionDep) -> RunOut:
    return RunOut.model_validate(queries.get_run(session, str(run_id)))


@router.get("/{run_id}/events", response_model=EventPage, responses=ERRORS)
def list_events(
    run_id: UUID,
    session: SessionDep,
    event_type: Annotated[list[str] | None, Query(description="repeat to filter by several types")] = None,
    status: Annotated[str | None, Query(pattern="^(ok|error)$")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    """Events of a run, always ordered by sequence."""
    items, total = queries.list_events(
        session, str(run_id), event_types=event_type, status=status, limit=limit, offset=offset
    )
    return EventPage(items=[EventOut.model_validate(e) for e in items], total=total, limit=limit, offset=offset)
