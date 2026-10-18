"""Run comparison endpoint."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas.api import ComparisonOut, ErrorResponse, RunOut
from app.services import queries
from app.services.compare import compare_runs

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _pair(value: tuple[str | None, str | None] | None) -> dict[str, str | None] | None:
    return {"base": value[0], "target": value[1]} if value else None


@router.get("", response_model=ComparisonOut, responses={404: {"model": ErrorResponse}})
def compare(
    base: Annotated[UUID, Query(description="run id of the reference run")],
    target: Annotated[UUID, Query(description="run id of the run to compare against it")],
    session: Annotated[Session, Depends(get_session)],
) -> ComparisonOut:
    base_run = queries.get_run(session, str(base))
    target_run = queries.get_run(session, str(target))
    result = compare_runs(
        queries.all_events(session, base_run.id),
        queries.all_events(session, target_run.id),
        base_name=base_run.name,
        target_name=target_run.name,
        base_complete=base_run.completeness == "complete",
        target_complete=target_run.completeness == "complete",
    )
    entries = []
    for entry in result.entries:
        data = asdict(entry)
        data["status_change"] = _pair(entry.status_change)
        data["error_change"] = _pair(entry.error_change)
        entries.append(data)
    return ComparisonOut.model_validate(
        {
            "base": RunOut.model_validate(base_run),
            "target": RunOut.model_validate(target_run),
            "counts": result.counts,
            "warnings": result.warnings,
            "entries": entries,
        }
    )
