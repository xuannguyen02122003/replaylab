"""Tests for the tracer: does instrumented code produce correct events?"""

import pytest

from app.schemas.event import REDACTED
from tracer import run, set_attribute, span, traced
from tracer.recorder import DROPPED_ATTRIBUTES_KEY, TRUNCATED_SUFFIX, sanitize_attributes


class Boom(Exception):
    pass


@traced("outer")
def outer(fail: bool = False) -> int:
    set_attribute("fail", fail)
    inner()
    if fail:
        failing()
    return 42


@traced("inner")
def inner() -> None:
    pass


@traced("failing")
def failing() -> None:
    raise Boom("it broke")


def by_sequence(events):
    return sorted(events, key=lambda e: e["sequence"])


def test_successful_run_events_and_parents():
    with run("unit_test") as recorder:
        assert outer() == 42  # tracing does not change the return value

    events = by_sequence(recorder.events)
    assert [(e["event_type"], e["operation_name"]) for e in events] == [
        ("run.started", "scenario.unit_test"),
        ("span", "outer"),
        ("span", "inner"),
        ("run.finished", "scenario.unit_test"),
    ]
    started, outer_span, inner_span, finished = events
    assert outer_span["parent_event_id"] is None
    assert inner_span["parent_event_id"] == outer_span["event_id"]
    assert outer_span["attributes"] == {"fail": False}
    assert finished["status"] == "ok"
    assert all(e["run_id"] == started["run_id"] for e in events)


def test_children_are_emitted_before_parents_but_have_higher_sequence():
    with run("unit_test") as recorder:
        outer()

    emitted = [e["operation_name"] for e in recorder.events]
    assert emitted.index("inner") < emitted.index("outer")  # finished first
    seq = {e["operation_name"]: e["sequence"] for e in recorder.events if e["event_type"] == "span"}
    assert seq["outer"] < seq["inner"]  # but started first


def test_exception_is_recorded_once_and_reraised():
    with pytest.raises(Boom):
        with run("unit_test") as recorder:
            outer(fail=True)

    events = by_sequence(recorder.events)
    exceptions = [e for e in events if e["event_type"] == "exception"]
    assert len(exceptions) == 1, "the stack trace must be stored only once"

    exc = exceptions[0]
    failing_span = next(e for e in events if e["operation_name"] == "failing" and e["event_type"] == "span")
    outer_span = next(e for e in events if e["operation_name"] == "outer")
    inner_span = next(e for e in events if e["operation_name"] == "inner")

    assert exc["parent_event_id"] == failing_span["event_id"]
    assert exc["error"]["type"] == "Boom"
    assert exc["error"]["message"] == "it broke"
    assert exc["error"]["stack"][0]["function"] == "failing"  # innermost frame first
    assert exc["error"]["stack"][0]["file"] == "tests/test_tracer.py"  # relative path
    assert failing_span["status"] == "error"
    assert outer_span["status"] == "error"  # the exception passed through it
    assert inner_span["status"] == "ok"  # finished before the failure
    finished = events[-1]
    assert finished["event_type"] == "run.finished"
    assert finished["status"] == "error"
    assert finished["attributes"] == {"error.type": "Boom"}


def test_sequences_are_contiguous():
    with pytest.raises(Boom):
        with run("unit_test") as recorder:
            outer(fail=True)
    assert sorted(e["sequence"] for e in recorder.events) == list(range(len(recorder.events)))


def test_traced_code_works_without_a_run():
    assert outer() == 42  # no recorder: spans are no-ops


def test_nested_runs_are_rejected():
    with run("a"):
        with pytest.raises(RuntimeError):
            with run("b"):
                pass


def test_span_context_manager_and_attributes():
    with run("unit_test") as recorder:
        with span("manual.block", step=1) as current:
            current.set_attribute("password", "hunter2")

    block = next(e for e in recorder.events if e["operation_name"] == "manual.block")
    assert block["attributes"] == {"step": 1, "password": REDACTED}
    assert block["duration_ms"] >= 0


def test_sanitize_attributes_limits():
    attrs = {f"k{i}": i for i in range(25)}
    cleaned = sanitize_attributes(attrs)
    assert len(cleaned) == 20
    assert cleaned[DROPPED_ATTRIBUTES_KEY] == 6

    long = sanitize_attributes({"note": "x" * 900})
    assert len(long["note"]) == 500
    assert long["note"].endswith(TRUNCATED_SUFFIX)

    odd = sanitize_attributes({"bad key!": [1, 2], "ratio": float("nan")})
    assert odd == {"bad_key_": "[1, 2]", "ratio": "nan"}
