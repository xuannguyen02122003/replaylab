"""Tests for app/schemas/event.py.

Each test answers one question: "does the schema accept good events
and reject bad ones, for the reason the docs say?"
"""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.event import REDACTED, Event, EventType

DOCS_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "event-schema.md"

RUN_ID = "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d"
SPAN_ID = "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e02"


def make_event(**overrides):
    """Return a valid span event as a dict. Tests change one field at a time."""
    event = {
        "schema_version": "1.0",
        "event_id": "6f1c2a8e-1b7d-4c3a-9e2f-0a1b2c3d4e03",
        "run_id": RUN_ID,
        "parent_event_id": SPAN_ID,
        "sequence": 2,
        "event_type": "span",
        "operation_name": "validate_order",
        "timestamp": "2026-10-11T11:20:00.003Z",
        "duration_ms": 1.2,
        "status": "ok",
        "attributes": {"order_id": "ORD-1001"},
        "error": None,
    }
    event.update(overrides)
    return event


VALID_ERROR = {
    "type": "OutOfStockError",
    "message": "Product SKU-123 has 0 units available",
    "stack": [{"file": "examples/order_service/inventory.py", "line": 42, "function": "reserve_stock"}],
}


# ---------- Valid events ----------


def test_valid_span_is_accepted():
    event = Event.model_validate(make_event())
    assert event.event_type == EventType.SPAN
    assert event.duration_ms == 1.2


def test_documented_example_is_valid():
    """The example in docs/event-schema.md section 8 must pass validation.

    This keeps the document and the code in sync: if someone changes a rule
    in the code but not in the docs (or the reverse), this test fails.
    """
    text = DOCS_SCHEMA.read_text(encoding="utf-8")
    section_8 = text.split("## 8.", 1)[1]
    json_block = re.search(r"```json\n(.*?)\n```", section_8, re.DOTALL).group(1)
    events = json.loads(json_block)

    parsed = [Event.model_validate(e) for e in events]

    assert len(parsed) == 6
    assert [e.event_type for e in parsed] == [
        EventType.RUN_STARTED,
        EventType.SPAN,
        EventType.SPAN,
        EventType.SPAN,
        EventType.EXCEPTION,
        EventType.RUN_FINISHED,
    ]


def test_bool_attribute_stays_bool():
    """True must not be turned into 1 (bool is a subtype of int in Python)."""
    event = Event.model_validate(make_event(attributes={"cache_hit": True, "count": 1}))
    assert event.attributes["cache_hit"] is True
    assert event.attributes["count"] == 1


# ---------- Field-level rejections ----------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"schema_version": "2.0"}, id="unknown schema version"),
        pytest.param({"event_id": "not-a-uuid"}, id="event_id not a uuid"),
        pytest.param({"sequence": -1}, id="negative sequence"),
        pytest.param({"event_type": "span.started"}, id="unknown event type"),
        pytest.param({"operation_name": ""}, id="empty operation name"),
        pytest.param({"operation_name": "validate order"}, id="space in operation name"),
        pytest.param({"timestamp": "2026-10-11T11:20:00"}, id="timestamp without timezone"),
        pytest.param({"duration_ms": -0.5}, id="negative duration"),
        pytest.param({"status": "failed"}, id="unknown status"),
        pytest.param({"duraton_ms": 1.0}, id="unknown extra field (typo)"),
        pytest.param({"attributes": {"items": [1, 2]}}, id="nested attribute value"),
        pytest.param({"attributes": {"bad key": 1}}, id="space in attribute key"),
        pytest.param({"attributes": {"note": "x" * 501}}, id="attribute string too long"),
        pytest.param({"attributes": {f"k{i}": i for i in range(21)}}, id="more than 20 attributes"),
    ],
)
def test_invalid_fields_are_rejected(overrides):
    with pytest.raises(ValidationError):
        Event.model_validate(make_event(**overrides))


def test_missing_field_is_rejected():
    event = make_event()
    del event["status"]
    with pytest.raises(ValidationError):
        Event.model_validate(event)


# ---------- Rules that depend on event_type ----------


@pytest.mark.parametrize(
    "overrides, expected_message",
    [
        pytest.param({"duration_ms": None}, "must have duration_ms", id="span without duration"),
        pytest.param({"error": VALID_ERROR}, "must have error = null", id="span with error"),
        pytest.param(
            {"event_type": "exception", "duration_ms": None, "status": "error"},
            "must have an error object",
            id="exception without error",
        ),
        pytest.param(
            {"event_type": "exception", "duration_ms": None, "error": VALID_ERROR, "status": "ok"},
            "status 'error'",
            id="exception with status ok",
        ),
        pytest.param(
            {"event_type": "exception", "duration_ms": None, "error": VALID_ERROR, "status": "error", "parent_event_id": None},
            "must point to the span",
            id="exception without parent",
        ),
        pytest.param(
            {"event_type": "run.started", "duration_ms": None, "parent_event_id": None, "sequence": 3},
            "sequence 0",
            id="run.started not at sequence 0",
        ),
        pytest.param(
            {"event_type": "run.started", "sequence": 0, "parent_event_id": None},
            "duration_ms = null",
            id="run.started with duration",
        ),
        pytest.param({"sequence": 0}, "reserved for run.started", id="span at sequence 0"),
        pytest.param(
            {"event_type": "run.finished", "sequence": 5},
            "parent_event_id = null",
            id="run.finished with parent",
        ),
    ],
)
def test_event_type_rules(overrides, expected_message):
    with pytest.raises(ValidationError, match=re.escape(expected_message)):
        Event.model_validate(make_event(**overrides))


# ---------- Stack frames ----------


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/home/kamiya/replaylab/inventory.py", id="linux absolute"),
        pytest.param("C:\\Users\\kamiya\\replaylab\\inventory.py", id="windows absolute"),
        pytest.param("C:/Users/kamiya/inventory.py", id="windows forward slashes"),
    ],
)
def test_absolute_stack_paths_are_rejected(path):
    error = {**VALID_ERROR, "stack": [{"file": path, "line": 42, "function": "reserve_stock"}]}
    event = make_event(event_type="exception", duration_ms=None, status="error", error=error)
    with pytest.raises(ValidationError, match="relative to the project root"):
        Event.model_validate(event)


# ---------- Sanitization ----------


def test_sensitive_attributes_are_redacted():
    attributes = {
        "User_Password": "hunter2",
        "api_key": "sk-123",
        "card_number": "4111",
        "order_id": "ORD-1001",
    }
    event = Event.model_validate(make_event(attributes=attributes))

    assert event.attributes["User_Password"] == REDACTED
    assert event.attributes["api_key"] == REDACTED
    assert event.attributes["card_number"] == REDACTED
    assert event.attributes["order_id"] == "ORD-1001"
