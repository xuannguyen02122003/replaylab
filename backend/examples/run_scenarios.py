"""Command-line runner: execute demo scenarios and send their events to the collector.

This is the "real" producer path: the demo app runs in its own process and
talks to the collector over HTTP, exactly like an instrumented app would.

    python -m examples.run_scenarios                   # run all scenarios
    python -m examples.run_scenarios order_success     # run one
    python -m examples.run_scenarios --collector http://localhost:8000
"""

import argparse
import sys

from examples.order_service.scenarios import SCENARIOS, run_scenario
from tracer import ExportError, send_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ReplayLab demo scenarios.")
    parser.add_argument("scenarios", nargs="*", help=f"scenario names (default: all). Choices: {', '.join(SCENARIOS)}")
    parser.add_argument("--collector", default="http://localhost:8000", help="collector base URL")
    args = parser.parse_args(argv)

    names = args.scenarios or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(unknown)}")

    for name in names:
        recorder = run_scenario(name)
        try:
            reply = send_events(recorder.events, args.collector)
        except ExportError as exc:
            print(f"[FAIL] {name}: {exc}", file=sys.stderr)
            return 1
        run = reply["run"]
        print(f"[ OK ] {name:<24} run={run['id']}  events={run['event_count']}  "
              f"status={run['status']}  trace={run['completeness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
