"""Sends recorded events to the ReplayLab collector over HTTP.

Uses only the standard library (urllib), so instrumented apps do not
need extra packages.
"""

import json
import urllib.error
import urllib.request
from typing import Any


class ExportError(RuntimeError):
    """The collector could not be reached or rejected the events."""


def send_events(
    events: list[dict[str, Any]],
    collector_url: str,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """POST all events of one run in a single batch. Returns the collector's JSON reply."""
    if not events:
        raise ExportError("no events to send")

    run_id = events[0]["run_id"]
    url = f"{collector_url.rstrip('/')}/api/runs/{run_id}/events"
    body = json.dumps({"events": events}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ExportError(f"collector rejected the events (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ExportError(f"could not reach the collector at {url}: {exc.reason}") from exc


def send_in_chunks(
    events: list[dict[str, Any]],
    collector_url: str,
    chunk_size: int = 1000,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Send a large run as several batches (the collector accepts up to 1000 per request).

    Events are sent in sequence order, so the run becomes complete with the last batch.
    Returns the collector's reply to the last batch.
    """
    ordered = sorted(events, key=lambda e: e["sequence"])
    reply: dict[str, Any] = {}
    for start in range(0, len(ordered), chunk_size):
        reply = send_events(ordered[start : start + chunk_size], collector_url, timeout_seconds)
    return reply
