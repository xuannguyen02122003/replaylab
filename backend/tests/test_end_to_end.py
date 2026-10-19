"""End-to-end: a real collector server and the demo app talking over HTTP.

This test starts uvicorn on a free port in a background thread, runs the
command-line scenario runner against it, then reads the runs back through
the API. It is the closest test to how the project is really used.
"""

import json
import urllib.request

from examples.run_scenarios import main as run_scenarios_main
from tests.conftest import free_port


def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def test_demo_app_to_collector_over_http(server_url, capsys):
    exit_code = run_scenarios_main(["order_success", "order_out_of_stock", "--collector", server_url])
    assert exit_code == 0
    assert "[ OK ] order_success" in capsys.readouterr().out

    runs = get_json(f"{server_url}/api/runs")["items"]
    by_name = {r["name"]: r for r in runs}
    assert set(by_name) == {"order_success", "order_out_of_stock"}
    assert by_name["order_success"]["status"] == "ok"
    assert by_name["order_out_of_stock"]["status"] == "error"
    assert all(r["completeness"] == "complete" for r in runs)

    events = get_json(f"{server_url}/api/runs/{by_name['order_out_of_stock']['id']}/events")["items"]
    assert events[0]["event_type"] == "run.started"
    assert events[-1]["event_type"] == "run.finished"


def test_unreachable_collector_reports_failure(capsys):
    exit_code = run_scenarios_main(["order_success", "--collector", f"http://127.0.0.1:{free_port()}"])
    assert exit_code == 1
    assert "could not reach the collector" in capsys.readouterr().err
