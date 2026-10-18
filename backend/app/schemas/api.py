"""Request and response models for the HTTP API.

These are separate from the ORM models (app/models) on purpose: the
database shape and the API shape can change independently.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.event import ErrorInfo, Event

MAX_EVENTS_PER_BATCH = 1000


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: Annotated[list[Event], Field(min_length=1, max_length=MAX_EVENTS_PER_BATCH)]


class IssueOut(BaseModel):
    code: str
    message: str


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    completeness: str
    issues: list[IssueOut]
    started_at: datetime | None
    duration_ms: float | None
    event_count: int
    error_count: int
    received_at: datetime
    updated_at: datetime


class IngestResponse(BaseModel):
    run: RunOut
    accepted: int
    duplicates: int


class RunPage(BaseModel):
    items: list[RunOut]
    total: int
    limit: int
    offset: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    run_id: str
    parent_event_id: str | None
    sequence: int
    schema_version: str
    event_type: str
    operation_name: str
    timestamp: datetime
    duration_ms: float | None
    status: str
    attributes: dict[str, Any]
    error: ErrorInfo | None


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    offset: int


class ScenarioOut(BaseModel):
    name: str
    description: str
    expected_status: str


class AttributeChangeOut(BaseModel):
    key: str
    change: str
    base: Any = None
    target: Any = None


class DurationChangeOut(BaseModel):
    base_ms: float
    target_ms: float
    delta_ms: float
    delta_pct: float | None
    significant: bool


class ValueChangeOut(BaseModel):
    base: str | None
    target: str | None


class DiffEntryOut(BaseModel):
    key: str
    kind: str
    event_type: str
    operation_name: str
    depth: int
    base_event_id: str | None
    target_event_id: str | None
    base_sequence: int | None
    target_sequence: int | None
    status_change: ValueChangeOut | None
    attribute_changes: list[AttributeChangeOut]
    error_change: ValueChangeOut | None
    duration: DurationChangeOut | None


class ComparisonOut(BaseModel):
    base: RunOut
    target: RunOut
    counts: dict[str, int]
    warnings: list[str]
    entries: list[DiffEntryOut]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody
