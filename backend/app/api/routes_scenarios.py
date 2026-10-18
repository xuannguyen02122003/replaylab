"""List and execute the predefined demo scenarios."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_session
from app.config import Settings
from app.schemas.api import ErrorResponse, IngestResponse, RunOut, ScenarioOut
from app.services.errors import FeatureDisabledError
from app.services.scenario_runner import execute_scenario, list_scenarios

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioOut])
def scenarios() -> list[ScenarioOut]:
    return [ScenarioOut(name=s.name, description=s.description, expected_status=s.expected_status) for s in list_scenarios()]


@router.post(
    "/{name}/runs",
    status_code=201,
    response_model=IngestResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def run(
    name: str,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> IngestResponse:
    """Execute one predefined scenario now and store the events it produced."""
    if not settings.enable_scenario_runner:
        raise FeatureDisabledError("the scenario runner is disabled on this server")
    result = execute_scenario(session, name)
    return IngestResponse(run=RunOut.model_validate(result.run), accepted=result.accepted, duplicates=result.duplicates)
