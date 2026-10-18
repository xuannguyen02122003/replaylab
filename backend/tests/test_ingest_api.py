"""POST /api/runs/{run_id}/events — storing events."""

import uuid

from tests.helpers import build_run, shuffled


def post(client, events, run_id=None):
    run_id = run_id or events[0]["run_id"]
    return client.post(f"/api/runs/{run_id}/events", json={"events": events})


def test_valid_batch_is_stored_and_run_is_complete(client):
    events = build_run()
    response = post(client, events)

    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] == len(events)
    assert body["duplicates"] == 0
    assert body["run"]["completeness"] == "complete"
    assert body["run"]["status"] == "ok"
    assert body["run"]["name"] == "test"
    assert body["run"]["event_count"] == len(events)


def test_malformed_event_rejects_whole_batch(client):
    events = build_run()
    events[2]["duration_ms"] = -5  # one bad event
    response = post(client, events)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"][:3] == ["body", "events", 2]
    # nothing was stored: all or nothing
    assert client.get(f"/api/runs/{events[0]['run_id']}").status_code == 404


def test_not_json_is_rejected(client):
    response = client.post(
        f"/api/runs/{uuid.uuid4()}/events", content=b"not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422


def test_empty_batch_is_rejected(client):
    assert post(client, [], run_id=str(uuid.uuid4())).status_code == 422


def test_invalid_run_id_in_url(client):
    response = client.post("/api/runs/not-a-uuid/events", json={"events": build_run()})
    assert response.status_code == 422


def test_run_id_mismatch_is_rejected(client):
    events = build_run()
    response = post(client, events, run_id=str(uuid.uuid4()))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_trace"


def test_partial_batch_is_stored_as_incomplete(client):
    events = build_run()
    response = post(client, events[:-1])  # run.finished not sent yet

    run = response.json()["run"]
    assert run["completeness"] == "incomplete"
    assert run["status"] == "unknown"  # never claim success without run.finished
    assert [i["code"] for i in run["issues"]] == ["missing_run_finished"]


def test_second_batch_completes_the_run(client):
    events = build_run()
    post(client, events[:2])
    response = post(client, events[2:])

    assert response.status_code == 201
    assert response.json()["run"]["completeness"] == "complete"
    assert response.json()["run"]["event_count"] == len(events)


def test_resending_is_idempotent(client):
    events = build_run()
    post(client, events)
    response = post(client, events)

    assert response.status_code == 201
    assert response.json()["accepted"] == 0
    assert response.json()["duplicates"] == len(events)
    assert response.json()["run"]["event_count"] == len(events)


def test_same_sequence_different_event_is_a_conflict(client):
    events = build_run()
    post(client, events)
    impostor = {**events[2], "event_id": str(uuid.uuid4())}
    response = post(client, [impostor])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_same_event_id_with_different_content_is_a_conflict(client):
    events = build_run()
    post(client, events)
    changed = {**events[2], "operation_name": "something_else"}
    assert post(client, [changed]).status_code == 409


def test_event_id_from_another_run_is_a_conflict(client):
    first = build_run()
    post(client, first)
    second = build_run()
    second[2]["event_id"] = first[2]["event_id"]
    assert post(client, second).status_code == 409


def test_duplicate_sequence_inside_one_batch_is_a_conflict(client):
    events = build_run()
    events.append({**events[2], "event_id": str(uuid.uuid4())})
    assert post(client, events).status_code == 409


def test_events_are_returned_by_sequence_not_arrival_order(client):
    events = build_run(("process_order", "a", "b", "c", "d"))
    post(client, shuffled(events))

    response = client.get(f"/api/runs/{events[0]['run_id']}/events")
    sequences = [e["sequence"] for e in response.json()["items"]]
    assert sequences == sorted(sequences) == list(range(len(events)))


def test_sensitive_attributes_are_redacted_by_the_collector(client):
    events = build_run()
    events[2]["attributes"] = {"api_token": "abc123", "order_id": "ORD-1"}
    post(client, events)

    stored = client.get(f"/api/runs/{events[0]['run_id']}/events").json()["items"][2]
    assert stored["attributes"] == {"api_token": "[REDACTED]", "order_id": "ORD-1"}


def test_oversized_body_is_rejected():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import make_settings

    app = create_app(make_settings(max_request_bytes=1000))
    with TestClient(app) as small_client:
        response = post(small_client, build_run(("p",) + tuple(f"s{i}" for i in range(20))))
    assert response.status_code == 413
