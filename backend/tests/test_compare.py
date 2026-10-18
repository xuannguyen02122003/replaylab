"""Run comparison: matching rules and the /api/compare endpoint."""

import uuid

from app.schemas.event import Event
from app.services.compare import compare_runs, match_keys
from examples.order_service.scenarios import run_scenario
from tests.helpers import build_run


def parse(events):
    return [Event.model_validate(e) for e in events]


def scenario_events(name):
    return parse(run_scenario(name).events)


def entries_by_kind(result, kind):
    return [e for e in result.entries if e.kind == kind]


def test_match_keys_use_call_path_and_occurrence():
    events = parse(build_run(("process_order", "get_product", "get_product", "save")))
    keys = sorted(match_keys(events).values())
    assert keys == [
        "/$run.finished",
        "/^run.started",
        "/process_order#0",
        "/process_order#0/get_product#0",
        "/process_order#0/get_product#1",
        "/process_order#0/save#0",
    ]


def test_identical_structure_has_only_unchanged_entries():
    base = parse(build_run())
    target = parse(build_run())
    result = compare_runs(base, target)
    assert result.counts == {"unchanged": 4, "changed": 0, "added": 0, "missing": 0}


def test_comparison_is_deterministic():
    base, target = scenario_events("order_success"), scenario_events("order_out_of_stock")
    first = compare_runs(base, target)
    second = compare_runs(list(reversed(base)), list(reversed(target)))  # input order must not matter
    assert [(e.key, e.kind) for e in first.entries] == [(e.key, e.kind) for e in second.entries]


def test_extra_call_does_not_shift_later_matches():
    base = parse(build_run(("process_order", "a", "c")))
    target = parse(build_run(("process_order", "a", "b", "c")))  # "b" inserted
    result = compare_runs(base, target)

    added = entries_by_kind(result, "added")
    assert [e.operation_name for e in added] == ["b"]
    assert result.counts["missing"] == 0
    # "b" is shown in execution order, between "a" and "c"
    names = [e.operation_name for e in result.entries if e.event_type == "span"]
    assert names == ["process_order", "a", "b", "c"]


def test_success_vs_out_of_stock():
    result = compare_runs(
        scenario_events("order_success"),
        scenario_events("order_out_of_stock"),
        base_name="order_success",
        target_name="order_out_of_stock",
    )
    missing = [e.operation_name for e in entries_by_kind(result, "missing")]
    added = [(e.event_type, e.operation_name) for e in entries_by_kind(result, "added")]
    assert missing == ["payment.charge", "order.confirm", "repository.save_order"]
    assert added == [("exception", "inventory.reserve_stock")]

    status_changes = {e.operation_name: e.status_change for e in result.entries if e.status_change}
    assert status_changes["process_order"] == ("ok", "error")
    assert status_changes["inventory.reserve_stock"] == ("ok", "error")
    assert any("different scenarios" in w for w in result.warnings)


def test_attribute_changes_with_discount():
    result = compare_runs(scenario_events("order_success"), scenario_events("order_with_discount"))
    pricing = next(e for e in result.entries if e.operation_name == "pricing.calculate_total")
    changes = {c.key: (c.base, c.target) for c in pricing.attribute_changes}
    assert changes["discount_percent"] == (0, 10)
    assert changes["total_cents"] == (12650, 11385)


def test_slow_repository_durations_are_significant():
    result = compare_runs(scenario_events("order_success"), scenario_events("order_slow_repository"))
    get_product = [e for e in result.entries if e.operation_name == "repository.get_product"]
    assert get_product and all(e.duration.significant for e in get_product)
    assert all(e.duration.delta_ms > 40 for e in get_product)


def test_small_duration_noise_is_not_significant():
    base = parse(build_run())
    target_raw = build_run()
    target_raw[2]["duration_ms"] = 1.4  # 1.0 -> 1.4 ms: +40%, but only 0.4 ms
    result = compare_runs(base, parse(target_raw))
    entry = next(e for e in result.entries if e.operation_name == "validate_order")
    assert entry.kind == "unchanged"
    assert entry.duration.delta_ms == 0.4


def test_compare_endpoint(client):
    base = client.post("/api/scenarios/order_success/runs").json()["run"]["id"]
    target = client.post("/api/scenarios/order_payment_declined/runs").json()["run"]["id"]
    response = client.get(f"/api/compare?base={base}&target={target}")

    assert response.status_code == 200
    body = response.json()
    assert body["base"]["id"] == base
    assert body["counts"]["missing"] == 2  # order.confirm, repository.save_order
    charge = next(e for e in body["entries"] if e["operation_name"] == "payment.charge")
    assert charge["status_change"] == {"base": "ok", "target": "error"}


def test_compare_unknown_run_is_404(client):
    base = client.post("/api/scenarios/order_success/runs").json()["run"]["id"]
    assert client.get(f"/api/compare?base={base}&target={uuid.uuid4()}").status_code == 404
