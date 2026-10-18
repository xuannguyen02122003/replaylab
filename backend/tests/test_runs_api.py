"""GET endpoints for runs and events, and the scenario runner."""

import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings
from tests.helpers import build_run


def store(client, events):
    assert client.post(f"/api/runs/{events[0]['run_id']}/events", json={"events": events}).status_code == 201
    return events[0]["run_id"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_runs_empty(client):
    assert client.get("/api/runs").json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_runs_pagination_and_filters(client):
    ids = [store(client, build_run()) for _ in range(3)]
    incomplete = build_run()
    store(client, incomplete[:-1])

    page = client.get("/api/runs?limit=2&offset=0").json()
    assert page["total"] == 4
    assert len(page["items"]) == 2

    second = client.get("/api/runs?limit=2&offset=2").json()
    all_ids = {r["id"] for r in page["items"] + second["items"]}
    assert all_ids == set(ids) | {incomplete[0]["run_id"]}  # no run lost or repeated

    only_incomplete = client.get("/api/runs?completeness=incomplete").json()
    assert [r["id"] for r in only_incomplete["items"]] == [incomplete[0]["run_id"]]
    assert client.get("/api/runs?status=ok").json()["total"] == 3


def test_invalid_query_parameters(client):
    assert client.get("/api/runs?limit=0").status_code == 422
    assert client.get("/api/runs?limit=101").status_code == 422
    assert client.get("/api/runs?status=maybe").status_code == 422


def test_unknown_run_is_404(client):
    response = client.get(f"/api/runs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.get(f"/api/runs/{uuid.uuid4()}/events").status_code == 404


def test_unknown_route_uses_same_error_shape(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_event_filters(client):
    run_id = store(client, build_run())
    spans = client.get(f"/api/runs/{run_id}/events?event_type=span").json()
    assert {e["event_type"] for e in spans["items"]} == {"span"}

    both = client.get(f"/api/runs/{run_id}/events?event_type=run.started&event_type=run.finished").json()
    assert [e["event_type"] for e in both["items"]] == ["run.started", "run.finished"]

    page = client.get(f"/api/runs/{run_id}/events?limit=1&offset=1").json()
    assert page["total"] == 4
    assert [e["sequence"] for e in page["items"]] == [1]


def test_list_scenarios(client):
    names = [s["name"] for s in client.get("/api/scenarios").json()]
    assert "order_success" in names
    assert "order_out_of_stock" in names


def test_execute_scenario_stores_real_events(client):
    response = client.post("/api/scenarios/order_out_of_stock/runs")
    assert response.status_code == 201
    run = response.json()["run"]
    assert run["name"] == "order_out_of_stock"
    assert run["status"] == "error"
    assert run["completeness"] == "complete"
    assert run["error_count"] == 1

    events = client.get(f"/api/runs/{run['id']}/events").json()["items"]
    exception = next(e for e in events if e["event_type"] == "exception")
    assert exception["error"]["type"] == "OutOfStockError"


def test_unknown_scenario_is_404(client):
    assert client.post("/api/scenarios/rm_rf/runs").status_code == 404


def test_scenario_runner_can_be_disabled():
    app = create_app(make_settings(enable_scenario_runner=False))
    with TestClient(app) as disabled:
        response = disabled.post("/api/scenarios/order_success/runs")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "feature_disabled"
