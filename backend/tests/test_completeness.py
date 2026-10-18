"""Tests for trace completeness rules (schema section 7)."""

from app.schemas.event import Event
from app.services.completeness import find_issues
from tests.helpers import build_run


def parse(events):
    return [Event.model_validate(e) for e in events]


def codes(events):
    return [i.code for i in find_issues(parse(events))]


def test_complete_run_has_no_issues():
    assert codes(build_run()) == []


def test_order_of_input_does_not_matter():
    assert codes(list(reversed(build_run()))) == []


def test_empty_run():
    assert [i.code for i in find_issues([])] == ["no_events"]


def test_missing_run_finished():
    events = build_run()[:-1]
    assert codes(events) == ["missing_run_finished"]


def test_missing_run_started_and_gap():
    events = build_run()[1:]  # sequence 0 is gone
    assert codes(events) == ["missing_run_started", "sequence_gap"]


def test_gap_in_the_middle_also_breaks_parent_link():
    events = build_run(("process_order", "a", "b"))
    del events[1]  # remove the parent span (sequence 1)
    result = codes(events)
    assert "sequence_gap" in result
    assert "missing_parent" in result


def test_run_finished_not_last():
    events = build_run()
    events[-1]["sequence"] = 99
    events.append({**events[2], "event_id": "11111111-1111-4111-8111-111111111111", "sequence": 100})
    result = codes(events)
    assert "run_finished_not_last" in result


def test_child_with_lower_sequence_than_parent():
    events = build_run(("process_order", "validate_order"))
    events[1]["sequence"], events[2]["sequence"] = 2, 1  # child now "starts" before parent
    assert "child_before_parent" in codes(events)


def test_parent_must_be_a_span():
    events = build_run()
    events[2]["parent_event_id"] = events[0]["event_id"]  # points at run.started
    assert "parent_not_span" in codes(events)
