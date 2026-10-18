"""The demo scenarios must produce the traces described in the README."""

import pytest

from app.schemas.event import REDACTED, Event
from app.services.completeness import find_issues
from examples.order_service.scenarios import SCENARIOS, run_scenario


def ops(recorder, event_type="span"):
    return [e["operation_name"] for e in sorted(recorder.events, key=lambda e: e["sequence"]) if e["event_type"] == event_type]


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_every_scenario_produces_a_complete_valid_trace(name):
    recorder = run_scenario(name)
    events = [Event.model_validate(e) for e in recorder.events]
    assert find_issues(events) == []
    finished = next(e for e in events if e.event_type == "run.finished")
    assert finished.status.value == SCENARIOS[name].expected_status


def test_success_flow_covers_all_steps():
    recorder = run_scenario("order_success")
    assert ops(recorder) == [
        "process_order",
        "request.received",
        "validate_order",
        "repository.get_product",
        "repository.get_product",
        "pricing.calculate_total",
        "repository.get_product",
        "repository.get_product",
        "inventory.reserve_stock",
        "inventory.reserve_stock",
        "payment.charge",
        "order.confirm",
        "repository.save_order",
    ]


def test_out_of_stock_fails_at_second_reservation():
    recorder = run_scenario("order_out_of_stock")
    exceptions = [e for e in recorder.events if e["event_type"] == "exception"]
    assert len(exceptions) == 1
    assert exceptions[0]["error"]["type"] == "OutOfStockError"
    assert exceptions[0]["operation_name"] == "inventory.reserve_stock"
    assert "payment.charge" not in ops(recorder)  # never reached


def test_card_token_is_redacted():
    recorder = run_scenario("order_success")
    charge = next(e for e in recorder.events if e["operation_name"] == "payment.charge")
    assert charge["attributes"]["card_token"] == REDACTED
    assert "tok_visa" not in str(recorder.events)
