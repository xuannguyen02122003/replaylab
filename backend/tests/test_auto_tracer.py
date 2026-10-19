"""Automatic tracing of ordinary scripts (tracer/auto.py and `python -m tracer run`).

These scripts contain NO ReplayLab code. The tests check that ReplayLab
records them correctly anyway.
"""

import json
import textwrap
import urllib.request
from pathlib import Path

import pytest

from app.schemas.event import Event
from app.services.completeness import find_issues
from tracer.__main__ import main as tracer_cli, split_script_args
from tracer.auto import trace_script

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
INVOICE = SAMPLES / "invoice_report"


def spans(recorder, name=None):
    events = sorted(recorder.events, key=lambda e: e["sequence"])
    return [e for e in events if e["event_type"] == "span" and (name is None or e["operation_name"] == name)]


def assert_valid_and_complete(recorder):
    events = [Event.model_validate(e) for e in recorder.events]
    assert find_issues(events) == []


def write_script(tmp_path: Path, code: str, name: str = "script.py") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(code), encoding="utf-8")
    return path


# ---------- The invoice sample project ----------


def test_traces_a_whole_project_without_changing_it(capsys):
    recorder, error = trace_script(INVOICE / "main.py")

    assert error is None
    assert "Grand total" in capsys.readouterr().out  # the script really ran
    assert_valid_and_complete(recorder)
    assert len(spans(recorder, "pricing.price_order")) == 4  # one per CSV row
    assert len(spans(recorder, "loader.parse_row")) == 4

    started = recorder.events[0]
    assert started["operation_name"] == "scenario.invoice_report.main"
    assert started["attributes"]["mode"] == "auto"


def test_parent_child_structure_follows_the_call_tree():
    recorder, _ = trace_script(INVOICE / "main.py")
    by_id = {e["event_id"]: e for e in recorder.events}

    for price in spans(recorder, "pricing.price_order"):
        assert by_id[price["parent_event_id"]]["operation_name"] == "main.main"
    for discount in spans(recorder, "pricing.apply_discount"):
        assert by_id[discount["parent_event_id"]]["operation_name"] == "pricing.price_order"


def test_records_where_functions_are_defined_but_never_argument_values():
    recorder, _ = trace_script(INVOICE / "main.py")
    discount = spans(recorder, "pricing.apply_discount")[0]
    assert discount["attributes"] == {"code.file": "pricing.py", "code.line": 25}

    dump = json.dumps(recorder.events)
    assert "Linh" not in dump  # customer names from the CSV
    assert "1200.0" not in dump  # prices passed as arguments


def test_bug_in_sample_is_recorded_where_it_happens():
    recorder, error = trace_script(INVOICE / "main.py", [str(INVOICE / "data" / "orders_bad.csv")])

    assert isinstance(error, KeyError)
    assert_valid_and_complete(recorder)  # the trace is complete even though the run failed

    exceptions = [e for e in recorder.events if e["event_type"] == "exception"]
    assert len(exceptions) == 1
    exc = exceptions[0]
    by_id = {e["event_id"]: e for e in recorder.events}
    assert by_id[exc["parent_event_id"]]["operation_name"] == "pricing.apply_discount"
    assert exc["error"]["type"] == "KeyError"
    assert exc["error"]["stack"][0] == {"file": "pricing.py", "line": 26, "function": "apply_discount"}

    prices = spans(recorder, "pricing.price_order")
    assert [p["status"] for p in prices] == ["ok", "ok", "error"]  # third row fails
    assert spans(recorder, "main.main")[0]["status"] == "error"
    finished = recorder.events[-1]
    assert finished["status"] == "error"
    assert finished["attributes"]["error.type"] == "KeyError"


# ---------- Behaviour on small scripts ----------


def test_caught_exception_marks_only_the_failing_function(tmp_path):
    script = write_script(
        tmp_path,
        """
        def risky():
            raise ValueError("bad input")

        def safe():
            try:
                risky()
            except ValueError:
                return "recovered"

        safe()
        """,
    )
    recorder, error = trace_script(script)

    assert error is None
    assert spans(recorder, "script.risky")[0]["status"] == "error"
    assert spans(recorder, "script.safe")[0]["status"] == "ok"
    assert recorder.events[-1]["status"] == "ok"
    assert_valid_and_complete(recorder)


def test_recursion_creates_nested_spans(tmp_path):
    script = write_script(
        tmp_path,
        """
        def factorial(n):
            return 1 if n <= 1 else n * factorial(n - 1)

        factorial(4)
        """,
    )
    recorder, _ = trace_script(script)
    calls = spans(recorder, "script.factorial")
    assert len(calls) == 4
    for parent, child in zip(calls, calls[1:]):
        assert child["parent_event_id"] == parent["event_id"]


def test_generators_and_standard_library_are_not_recorded(tmp_path):
    script = write_script(
        tmp_path,
        """
        import json

        def numbers():
            yield 1
            yield 2

        def total():
            return sum(numbers()) + len(json.dumps({"a": 1}))

        total()
        """,
    )
    recorder, _ = trace_script(script)
    names = {e["operation_name"] for e in spans(recorder)}
    assert names == {"script.module", "script.total"}


def test_sys_exit_codes(tmp_path):
    ok = write_script(tmp_path, "import sys\nsys.exit(0)\n", "ok.py")
    recorder, error = trace_script(ok)
    assert error is None and recorder.events[-1]["status"] == "ok"

    failing = write_script(tmp_path, "import sys\nsys.exit(3)\n", "failing.py")
    recorder, error = trace_script(failing)
    assert isinstance(error, SystemExit)
    assert recorder.events[-1]["status"] == "error"


def test_max_spans_limit_is_reported_not_hidden(tmp_path):
    script = write_script(
        tmp_path,
        """
        def tick(i):
            return i

        for i in range(50):
            tick(i)
        """,
    )
    recorder, _ = trace_script(script, max_spans=10)
    assert len(spans(recorder)) == 10
    finished = recorder.events[-1]
    assert finished["attributes"]["replaylab.recorded_spans"] == 10
    assert finished["attributes"]["replaylab.dropped_spans"] == 41  # module + 50 calls - 10
    assert_valid_and_complete(recorder)


def test_tracing_can_run_twice_in_one_process(tmp_path):
    script = write_script(tmp_path, "def f():\n    return 1\n\nf()\n")
    first, _ = trace_script(script)
    second, _ = trace_script(script)
    assert len(spans(first)) == len(spans(second)) == 2


def test_missing_script(tmp_path):
    with pytest.raises(FileNotFoundError):
        trace_script(tmp_path / "nope.py")


# ---------- Command line ----------


def test_split_script_args():
    assert split_script_args(["run", "x.py", "--no-send", "--", "a.csv", "--flag"]) == (
        ["run", "x.py", "--no-send"],
        ["a.csv", "--flag"],
    )
    assert split_script_args(["run", "x.py"]) == (["run", "x.py"], [])


def test_cli_saves_events_and_returns_script_failure(tmp_path, capsys):
    out = tmp_path / "trace.json"
    code = tracer_cli(
        ["run", str(INVOICE / "main.py"), "--no-send", "--save", str(out), "--", str(INVOICE / "data" / "orders_bad.csv")]
    )
    assert code == 1  # the script failed
    events = json.loads(out.read_text(encoding="utf-8"))
    assert any(e["event_type"] == "exception" for e in events)
    assert "KeyError" in capsys.readouterr().err


def test_cli_sends_to_a_real_collector(server_url):
    code = tracer_cli(["run", str(INVOICE / "main.py"), "--collector", server_url])
    assert code == 0

    with urllib.request.urlopen(f"{server_url}/api/runs") as response:
        runs = json.loads(response.read())["items"]
    assert [r["name"] for r in runs] == ["invoice_report.main"]
    assert runs[0]["completeness"] == "complete"
    assert runs[0]["status"] == "ok"


def test_large_runs_are_sent_in_several_batches(server_url, tmp_path):
    script = write_script(tmp_path, "def f(i):\n    return i\n\nfor i in range(2500):\n    f(i)\n")
    code = tracer_cli(["run", str(script), "--collector", server_url, "--max-spans", "3000"])
    assert code == 0
    with urllib.request.urlopen(f"{server_url}/api/runs") as response:
        run = json.loads(response.read())["items"][0]
    assert run["event_count"] == 2503  # run.started + module + 2500 calls + run.finished
    assert run["completeness"] == "complete"
