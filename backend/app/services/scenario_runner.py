"""Runs a predefined demo scenario inside the collector process and stores its events.

The events are produced by real execution of the demo order service, then go
through the same validation and ingest code as events sent over HTTP.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas.event import Event
from app.services.errors import NotFoundError
from app.services.ingest import IngestResult, ingest_events
from examples.order_service.scenarios import SCENARIOS, run_scenario


@dataclass(frozen=True)
class ScenarioInfo:
    name: str
    description: str
    expected_status: str


def list_scenarios() -> list[ScenarioInfo]:
    return [ScenarioInfo(s.name, s.description, s.expected_status) for s in SCENARIOS.values()]


def execute_scenario(session: Session, name: str) -> IngestResult:
    if name not in SCENARIOS:
        raise NotFoundError(f"scenario {name} not found", details={"available": list(SCENARIOS)})
    recorder = run_scenario(name)
    events = [Event.model_validate(e) for e in recorder.events]
    return ingest_events(session, recorder.run_id, events)
