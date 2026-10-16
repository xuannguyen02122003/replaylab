"""Pydantic models for ReplayLab execution events.

This file is the code version of docs/event-schema.md (v1.0).
If you change a rule here, change the document too.

What this file checks:
    - Each single event is well-formed (types, limits, formats).
    - Rules that depend on event_type (for example, "an exception must have an error").

What this file does NOT check (done later, at run level, in services/):
    - Whether parent_event_id points to a real span in the same run.
    - Whether sequence numbers are unique and have no gaps.
"""

import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "1.0"

REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key", "authorization", "card")

MAX_ATTRIBUTES = 20
MAX_ATTRIBUTE_STRING = 500
MAX_STACK_FRAMES = 50

# Matches "/home/...", "\\server\...", "C:\..." or "C:/...".
_ABSOLUTE_PATH = re.compile(r"^([A-Za-z]:|[\\/])")


class EventType(str, Enum):
    RUN_STARTED = "run.started"
    SPAN = "span"
    EXCEPTION = "exception"
    RUN_FINISHED = "run.finished"


class EventStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


# Reusable constrained types.
OperationName = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.\-]+$")
]
AttributeKey = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.]+$")
]
AttributeValue = (
    Annotated[str, StringConstraints(max_length=MAX_ATTRIBUTE_STRING)]
    | bool
    | int
    | Annotated[float, Field(allow_inf_nan=False)]
    | None
)
DurationMs = Annotated[float, Field(ge=0, allow_inf_nan=False)]


def redact_attributes(attributes: dict[str, object]) -> dict[str, object]:
    """Replace the value of any sensitive-looking key with "[REDACTED]".

    A key is sensitive if it contains one of SENSITIVE_KEY_PARTS,
    ignoring upper/lower case. Example: "User_Password" -> redacted.
    """
    cleaned: dict[str, object] = {}
    for key, value in attributes.items():
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_KEY_PARTS):
            cleaned[key] = REDACTED
        else:
            cleaned[key] = value
    return cleaned


class StackFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    line: Annotated[int, Field(ge=1)]
    function: Annotated[str, StringConstraints(min_length=1, max_length=200)]

    @field_validator("file")
    @classmethod
    def file_must_be_relative(cls, value: str) -> str:
        if _ABSOLUTE_PATH.match(value):
            raise ValueError("stack frame file must be a path relative to the project root")
        return value


class ErrorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    message: Annotated[str, StringConstraints(max_length=1000)]
    stack: Annotated[list[StackFrame], Field(max_length=MAX_STACK_FRAMES)]


class Event(BaseModel):
    """One recorded execution event. See docs/event-schema.md, section 3."""

    # extra="forbid": an unknown field (for example a typo like "duraton_ms")
    # is an error instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    event_id: UUID4
    run_id: UUID4
    parent_event_id: UUID4 | None
    sequence: Annotated[int, Field(ge=0)]
    event_type: EventType
    operation_name: OperationName
    timestamp: AwareDatetime  # must include a timezone offset, e.g. "Z" or "+07:00"
    duration_ms: DurationMs | None
    status: EventStatus
    attributes: Annotated[dict[AttributeKey, AttributeValue], Field(max_length=MAX_ATTRIBUTES)]
    error: ErrorInfo | None

    @field_validator("attributes")
    @classmethod
    def redact_sensitive_attributes(cls, value: dict[str, object]) -> dict[str, object]:
        # Second line of defence: the instrumentation should already have
        # redacted these, but the collector never trusts that it did.
        return redact_attributes(value)

    @model_validator(mode="after")
    def check_rules_for_event_type(self) -> "Event":
        """Rules that depend on event_type (schema sections 2 and 3)."""
        kind = self.event_type
        has_duration = kind in (EventType.SPAN, EventType.RUN_FINISHED)

        # duration_ms
        if has_duration and self.duration_ms is None:
            raise ValueError(f"{kind.value} events must have duration_ms")
        if not has_duration and self.duration_ms is not None:
            raise ValueError(f"{kind.value} events must have duration_ms = null")

        # error
        if kind == EventType.EXCEPTION and self.error is None:
            raise ValueError("exception events must have an error object")
        if kind != EventType.EXCEPTION and self.error is not None:
            raise ValueError(f"{kind.value} events must have error = null")

        # status
        if kind == EventType.EXCEPTION and self.status != EventStatus.ERROR:
            raise ValueError("exception events must have status 'error'")
        if kind == EventType.RUN_STARTED and self.status != EventStatus.OK:
            raise ValueError("run.started events must have status 'ok'")

        # sequence: 0 is reserved for run.started
        if kind == EventType.RUN_STARTED and self.sequence != 0:
            raise ValueError("run.started must have sequence 0")
        if kind != EventType.RUN_STARTED and self.sequence == 0:
            raise ValueError("sequence 0 is reserved for run.started")

        # parent_event_id
        if kind in (EventType.RUN_STARTED, EventType.RUN_FINISHED) and self.parent_event_id is not None:
            raise ValueError(f"{kind.value} events must have parent_event_id = null")
        if kind == EventType.EXCEPTION and self.parent_event_id is None:
            raise ValueError("exception events must point to the span where they were raised")

        return self
