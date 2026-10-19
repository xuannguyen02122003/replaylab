"""Command line for the ReplayLab tracer.

    python -m tracer run my_script.py                 trace a script and send it to the collector
    python -m tracer run my_project/main.py --root my_project
    python -m tracer run tool.py --save trace.json --no-send   keep the events in a file only
    python -m tracer run tool.py --no-send -- data.csv        everything after "--" is passed to the script

Run it from the backend folder, with the backend's virtual environment active.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

from tracer.auto import DEFAULT_MAX_SPANS, trace_script
from tracer.exporter import ExportError, send_in_chunks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tracer", description="ReplayLab tracer")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run a Python script and record every function call in its project")
    run.add_argument("script", type=Path, help="the .py file to run")
    run.add_argument("--root", type=Path, help="project folder to record (default: the script's folder)")
    run.add_argument("--name", help="run name shown in ReplayLab (default: the script name)")
    run.add_argument("--collector", default="http://localhost:8000", help="collector URL (default: %(default)s)")
    run.add_argument("--ui", default="http://localhost:5173", help="frontend URL used for the printed link")
    run.add_argument("--max-spans", type=int, default=DEFAULT_MAX_SPANS, help="stop recording after this many calls")
    run.add_argument("--save", type=Path, help="also write the events to this JSON file")
    run.add_argument("--no-send", action="store_true", help="do not send to the collector")
    return parser


def split_script_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """["run", "x.py", "--no-send", "--", "a.csv"] -> (["run", "x.py", "--no-send"], ["a.csv"])"""
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1 :]
    return argv, []


def main(argv: list[str] | None = None) -> int:
    tracer_argv, args = split_script_args(sys.argv[1:] if argv is None else argv)
    options = build_parser().parse_args(tracer_argv)

    print(f"[replaylab] tracing {options.script} ...", file=sys.stderr)
    recorder, error = trace_script(
        options.script, args, root=options.root, name=options.name, max_spans=options.max_spans
    )

    if error is not None:
        print("\n[replaylab] the script raised an exception (it is recorded in the trace):", file=sys.stderr)
        traceback.print_exception(error, file=sys.stderr)

    finished = next(e for e in recorder.events if e["event_type"] == "run.finished")
    print(
        f"\n[replaylab] recorded {len(recorder.events)} events, "
        f"{finished['attributes'].get('replaylab.recorded_spans', 0)} function calls, "
        f"status={finished['status']}",
        file=sys.stderr,
    )
    if dropped := finished["attributes"].get("replaylab.dropped_spans"):
        print(f"[replaylab] {dropped} calls were not recorded (over --max-spans {options.max_spans})", file=sys.stderr)

    if options.save:
        options.save.write_text(json.dumps(recorder.events, indent=2), encoding="utf-8")
        print(f"[replaylab] events saved to {options.save}", file=sys.stderr)

    if not options.no_send:
        try:
            reply = send_in_chunks(recorder.events, options.collector)
        except ExportError as exc:
            print(f"[replaylab] {exc}", file=sys.stderr)
            return 2
        run = reply["run"]
        print(f"[replaylab] stored run {run['id']} ({run['completeness']} trace)", file=sys.stderr)
        print(f"[replaylab] open {options.ui.rstrip('/')}/runs/{run['id']}", file=sys.stderr)

    return 1 if error is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
