"""Records real execution events from explicitly instrumented code.

Usage:

    from tracer import run, traced, set_attribute

    @traced("validate_order")
    def validate_order(order):
        set_attribute("order_id", order.id)
        ...

    with run("order_success") as recorder:
        process_order(...)

    recorder.events  # list of event dicts that follow docs/event-schema.md

How it works:
    - run() creates a Recorder and stores it in a context variable, so any
      traced function called inside the `with` block can find it.
    - Each traced function opens a span. The span takes its sequence number
      when it STARTS, but its event is created when it FINISHES.
    - The current span is also kept in a context variable. That is how a
      child span knows its parent_event_id.
    - If an exception passes through a span, the span gets status "error".
      Only the innermost span (where the exception was first seen) records
      an `exception` event, so the stack trace is stored once.

Limitations (v1.0):
    - Synchronous code only. async functions are not supported.
    - One run at a time per thread/context.
"""

from __future__ import annotations

import functools
import math
import re
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from app.schemas.event import (
    MAX_ATTRIBUTE_STRING,
    MAX_ATTRIBUTES,
    MAX_STACK_FRAMES,
    SCHEMA_VERSION,
    Event,
    EventStatus,
    EventType,
    redact_attributes,
)

TRUNCATED_SUFFIX = "…[truncated]"
MAX_ERROR_MESSAGE = 1000
DROPPED_ATTRIBUTES_KEY = "replaylab.dropped_attributes"

# The folder that stack-frame paths are made relative to (the backend folder).
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_TRACER_DIR = Path(__file__).resolve().parent
_INVALID_KEY_CHARS = re.compile(r"[^a-zA-Z0-9_.]")
_INVALID_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_.\-]")
_RECORDED_MARKER = "_replaylab_recorded_run"

_current_recorder: ContextVar[Recorder | None] = ContextVar("replaylab_recorder", default=None)
_current_span: ContextVar[Span | None] = ContextVar("replaylab_span", default=None)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------


def truncate(text: str, limit: int) -> str:
    """Cut text to `limit` characters, ending with "…[truncated]" if it was cut."""
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX


def sanitize_value(value: Any) -> str | int | float | bool | None:
    """Turn any value into one of the types the schema allows."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    text = value if isinstance(value, str) else str(value)
    return truncate(text, MAX_ATTRIBUTE_STRING)


def sanitize_key(key: str) -> str:
    cleaned = _INVALID_KEY_CHARS.sub("_", str(key))[:64]
    return cleaned or "_"


def sanitize_operation_name(name: str) -> str:
    cleaned = _INVALID_NAME_CHARS.sub("_", name)[:100]
    return cleaned or "unnamed"


def sanitize_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Make attributes safe to send: valid keys, allowed types, size limits, redaction.

    If there are too many keys, the first ones are kept and a
    "replaylab.dropped_attributes" key records how many were dropped,
    so the loss is visible instead of silent.
    """
    cleaned = {sanitize_key(k): sanitize_value(v) for k, v in attributes.items()}
    if len(cleaned) > MAX_ATTRIBUTES:
        kept = list(cleaned.items())[: MAX_ATTRIBUTES - 1]
        dropped = len(cleaned) - len(kept)
        cleaned = dict(kept)
        cleaned[DROPPED_ATTRIBUTES_KEY] = dropped
    return redact_attributes(cleaned)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# ---------------------------------------------------------------------------
# Span and Recorder
# ---------------------------------------------------------------------------


class Span:
    """One timed operation that is currently running."""

    def __init__(self, name: str, sequence: int, parent_id: str | None, attributes: dict[str, Any]):
        self.event_id = str(uuid.uuid4())
        self.name = name
        self.sequence = sequence
        self.parent_id = parent_id
        self.attributes: dict[str, Any] = dict(attributes)
        self.status = EventStatus.OK
        self.timestamp = _utc_now()  # wall clock: for display only
        self._start = time.perf_counter()  # monotonic clock: for duration

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 3)


class Recorder:
    """Collects all events of one run, in memory."""

    def __init__(self, scenario: str, project_root: Path | None = None):
        self.run_id = str(uuid.uuid4())
        self.scenario = sanitize_operation_name(scenario)
        self.project_root = (project_root or DEFAULT_PROJECT_ROOT).resolve()
        self.events: list[dict[str, Any]] = []
        self.run_event_id = str(uuid.uuid4())
        # Extra facts added to run.finished (for example, how many spans were dropped).
        self.finish_attributes: dict[str, Any] = {}
        self._next_sequence = 0
        self._lock = threading.Lock()

    def take_sequence(self) -> int:
        with self._lock:
            sequence = self._next_sequence
            self._next_sequence += 1
            return sequence

    def emit(
        self,
        *,
        event_type: EventType,
        sequence: int,
        operation_name: str,
        timestamp: str,
        status: EventStatus,
        parent_event_id: str | None = None,
        event_id: str | None = None,
        duration_ms: float | None = None,
        attributes: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id or str(uuid.uuid4()),
            "run_id": self.run_id,
            "parent_event_id": parent_event_id,
            "sequence": sequence,
            "event_type": event_type.value,
            "operation_name": operation_name,
            "timestamp": timestamp,
            "duration_ms": duration_ms,
            "status": status.value,
            "attributes": sanitize_attributes(attributes or {}),
            "error": error,
        }
        # Validate before storing. If this fails, it is a bug in the tracer,
        # and it is better to find it here than in the collector.
        event = Event.model_validate(raw).model_dump(mode="json")
        with self._lock:
            self.events.append(event)
        return event

    def record_exception(self, exc: BaseException, span: Span) -> None:
        """Record an `exception` event, but only once per exception object."""
        if getattr(exc, _RECORDED_MARKER, None) == self.run_id:
            return  # an inner span already recorded it
        try:
            setattr(exc, _RECORDED_MARKER, self.run_id)
        except AttributeError:
            pass  # some built-in exceptions do not allow new attributes

        self.emit(
            event_type=EventType.EXCEPTION,
            sequence=self.take_sequence(),
            operation_name=span.name,
            timestamp=_utc_now(),
            status=EventStatus.ERROR,
            parent_event_id=span.event_id,
            error={
                "type": type(exc).__name__[:200] or "Exception",
                "message": truncate(str(exc), MAX_ERROR_MESSAGE),
                "stack": self._stack_frames(exc),
            },
        )

    def _stack_frames(self, exc: BaseException) -> list[dict[str, Any]]:
        """Project frames only, innermost first, paths relative to project root."""
        tb = exc.__traceback__
        outer = traceback.extract_stack(tb.tb_frame.f_back) if tb else []
        inner = traceback.extract_tb(tb) if tb else []
        frames = []
        for frame in reversed([*outer, *inner]):
            if frame.filename.startswith("<"):
                continue  # code with no real file, e.g. "<string>" from exec()
            path = Path(frame.filename).resolve()
            if _TRACER_DIR in path.parents or not path.is_relative_to(self.project_root):
                continue  # skip tracer internals, the standard library and packages
            frames.append(
                {
                    "file": path.relative_to(self.project_root).as_posix(),
                    "line": frame.lineno or 1,
                    "function": frame.name[:200],
                }
            )
            if len(frames) == MAX_STACK_FRAMES:
                break
        return frames


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextmanager
def run(
    scenario: str,
    *,
    attributes: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> Iterator[Recorder]:
    """Record one run. Emits run.started at the start and run.finished at the end.

    Exceptions are recorded and then re-raised, so tracing never hides an error.
    """
    if _current_recorder.get() is not None:
        raise RuntimeError("a ReplayLab run is already active in this context")

    recorder = Recorder(scenario, project_root)
    operation = f"scenario.{recorder.scenario}"
    recorder.emit(
        event_type=EventType.RUN_STARTED,
        event_id=recorder.run_event_id,
        sequence=recorder.take_sequence(),
        operation_name=operation,
        timestamp=_utc_now(),
        status=EventStatus.OK,
        attributes={"scenario": recorder.scenario, **(attributes or {})},
    )

    recorder_token = _current_recorder.set(recorder)
    started = time.perf_counter()
    started_at = _utc_now()
    status = EventStatus.OK
    finish_attributes: dict[str, Any] = {}
    try:
        yield recorder
    except BaseException as exc:
        status = EventStatus.ERROR
        finish_attributes = {"error.type": type(exc).__name__}
        raise
    finally:
        _current_recorder.reset(recorder_token)
        recorder.emit(
            event_type=EventType.RUN_FINISHED,
            sequence=recorder.take_sequence(),
            operation_name=operation,
            timestamp=started_at,
            status=status,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            attributes={**recorder.finish_attributes, **finish_attributes},
        )


@dataclass
class SpanHandle:
    """What start_span() returns and end_span() needs to close the span."""

    recorder: Recorder
    span: Span
    token: Token[Span | None]


def start_span(name: str, attributes: dict[str, Any] | None = None) -> SpanHandle | None:
    """Open a span and make it the current span. Returns None outside a run.

    Most code should use span() or @traced. These two low-level functions
    exist for the automatic tracer (auto.py), which opens and closes spans
    from monitoring callbacks instead of a `with` block.
    """
    recorder = _current_recorder.get()
    if recorder is None:
        return None
    parent = _current_span.get()
    current = Span(
        name=sanitize_operation_name(name),
        sequence=recorder.take_sequence(),
        parent_id=parent.event_id if parent else None,
        attributes=attributes or {},
    )
    return SpanHandle(recorder, current, _current_span.set(current))


def end_span(handle: SpanHandle, exc: BaseException | None = None) -> None:
    """Close a span opened by start_span(). Pass the exception if it failed."""
    current = handle.span
    if exc is not None:
        current.status = EventStatus.ERROR
        handle.recorder.record_exception(exc, current)
    _current_span.reset(handle.token)
    handle.recorder.emit(
        event_type=EventType.SPAN,
        event_id=current.event_id,
        sequence=current.sequence,
        operation_name=current.name,
        timestamp=current.timestamp,
        status=current.status,
        parent_event_id=current.parent_id,
        duration_ms=current.elapsed_ms(),
        attributes=current.attributes,
    )


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span | None]:
    """Time a block of code as one operation.

    Outside a run this does nothing, so instrumented code still works
    when nobody is recording.
    """
    handle = start_span(name, attributes)
    if handle is None:
        yield None
        return
    try:
        yield handle.span
    except BaseException as exc:
        end_span(handle, exc)
        raise
    else:
        end_span(handle)


def traced(name: str | Callable[..., Any] | None = None) -> Any:
    """Decorator that wraps a function in a span.

    @traced("validate_order")   -> operation name "validate_order"
    @traced                     -> operation name is the function name
    """

    def decorator(func: F) -> F:
        operation = name if isinstance(name, str) else func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(operation):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    if callable(name):  # used as @traced without parentheses
        return decorator(name)
    return decorator


def set_attribute(key: str, value: Any) -> None:
    """Attach a value to the span that is currently running (no-op outside a span)."""
    current = _current_span.get()
    if current is not None:
        current.set_attribute(key, value)


def current_run_id() -> str | None:
    recorder = _current_recorder.get()
    return recorder.run_id if recorder else None
