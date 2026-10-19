"""Automatic tracing: record ANY Python script without changing its code.

    python -m tracer run path/to/script.py [script args...]

How it works:
    Python 3.12 added `sys.monitoring`, an official low-overhead API that calls
    us back when functions start and end. We listen to three events:

        PY_START   a Python function starts       -> start_span()
        PY_RETURN  it returns normally            -> end_span()
        PY_UNWIND  it exits because of an exception -> end_span(exc)

    Only functions defined in files under the project root are recorded.
    For any other code (standard library, installed packages, ReplayLab itself)
    the callback returns sys.monitoring.DISABLE, which tells Python to stop
    reporting that code location. That keeps the overhead low.

What is recorded:
    - one span per function call: "module.function", duration, ok/error
    - attributes: file and line where the function is defined
    - exceptions, with a stack trace of project files only
    Function arguments and local variables are NEVER recorded.

Limitations:
    - Python 3.12+ only.
    - Generators and async functions are skipped (they pause and resume, so
      "start" and "end" do not map to one span).
    - Only the main thread is traced.
    - At most `max_spans` spans are kept (default 5000). Extra calls are counted
      in the run.finished attribute "replaylab.dropped_spans", not hidden.
"""

from __future__ import annotations

import inspect
import os
import runpy
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import CodeType
from typing import Any

from tracer.recorder import Recorder, SpanHandle, end_span, run, start_span

# Folders that are never "your code", even if they are inside the project.
IGNORED_DIR_NAMES = {".venv", "venv", "env", "site-packages", "node_modules", "__pycache__", ".git"}
SKIPPED_CODE_FLAGS = inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR
DEFAULT_MAX_SPANS = 5000

_TRACER_DIR = Path(__file__).resolve().parent


def _require_monitoring() -> Any:
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is None:
        raise RuntimeError("automatic tracing needs Python 3.12 or newer (sys.monitoring)")
    return monitoring


class AutoTracer:
    """Turns sys.monitoring callbacks into ReplayLab spans."""

    def __init__(self, recorder: Recorder, root: Path, max_spans: int = DEFAULT_MAX_SPANS):
        self.recorder = recorder
        self.root = root.resolve()
        self.max_spans = max_spans
        self.thread_id = threading.get_ident()
        self.recorded = 0
        self.dropped = 0
        # Stack of (code object, span handle or None if dropped), innermost last.
        self._stack: list[tuple[CodeType, SpanHandle | None]] = []
        self._names: dict[CodeType, str | None] = {}
        # True while we are inside our own callback. Code that WE run there
        # (validation, uuid...) must never be recorded as part of the script.
        self._busy = False

    # -- deciding what to trace -------------------------------------------

    def _operation_name(self, code: CodeType) -> str | None:
        """'pricing.apply_discount' for project code, None for code we skip."""
        if code in self._names:
            return self._names[code]
        name = self._compute_name(code)
        self._names[code] = name
        return name

    def _compute_name(self, code: CodeType) -> str | None:
        if code.co_flags & SKIPPED_CODE_FLAGS or code.co_filename.startswith("<"):
            return None
        path = Path(code.co_filename).resolve()
        if _TRACER_DIR == path.parent or _TRACER_DIR in path.parents:
            return None
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return None  # outside the project
        if any(part in IGNORED_DIR_NAMES for part in relative.parts):
            return None
        module = ".".join(relative.with_suffix("").parts)
        function = "module" if code.co_name == "<module>" else code.co_qualname
        return f"{module}.{function}"

    # -- monitoring callbacks ---------------------------------------------

    def on_start(self, code: CodeType, _offset: int) -> Any:
        if self._busy:
            return None
        self._busy = True
        try:
            name = self._operation_name(code)
            if name is None:
                return sys.monitoring.DISABLE  # never report this code location again
            if threading.get_ident() != self.thread_id:
                return None  # other threads are not traced
            if self.recorded >= self.max_spans:
                self.dropped += 1
                self._stack.append((code, None))
                return None
            self.recorded += 1
            attributes = {
                "code.file": Path(code.co_filename).resolve().relative_to(self.root).as_posix(),
                "code.line": code.co_firstlineno,
            }
            self._stack.append((code, start_span(name, attributes)))
            return None
        finally:
            self._busy = False

    def on_return(self, code: CodeType, _offset: int, _value: Any) -> Any:
        self._close(code, None)

    def on_unwind(self, code: CodeType, _offset: int, exc: BaseException) -> Any:
        self._close(code, exc)

    def _close(self, code: CodeType, exc: BaseException | None) -> None:
        if self._busy or threading.get_ident() != self.thread_id or self._operation_name(code) is None:
            return
        self._busy = True
        try:
            self._close_until(code, exc)
        finally:
            self._busy = False

    def _close_until(self, code: CodeType, exc: BaseException | None) -> None:
        # A function that started BEFORE tracing began has no span: ignore it.
        if not any(c is code for c, _ in self._stack):
            return
        # Normally the top of the stack is this code. If not, something exited
        # without an event we saw; close the abandoned spans so the tree stays valid.
        while self._stack:
            top_code, handle = self._stack.pop()
            if handle is not None:
                end_span(handle, exc if top_code is code else None)
            if top_code is code:
                return

    def close_remaining(self) -> None:
        """Close spans still open when tracing stops (e.g. sys.exit inside a function)."""
        while self._stack:
            _, handle = self._stack.pop()
            if handle is not None:
                end_span(handle)


@contextmanager
def auto_instrument(recorder: Recorder, root: Path, max_spans: int = DEFAULT_MAX_SPANS) -> Iterator[AutoTracer]:
    monitoring = _require_monitoring()
    tool = monitoring.PROFILER_ID
    try:
        monitoring.use_tool_id(tool, "replaylab")
    except ValueError as exc:
        raise RuntimeError("another profiler is already using sys.monitoring") from exc

    tracer = AutoTracer(recorder, root, max_spans)
    events = monitoring.events
    try:
        monitoring.register_callback(tool, events.PY_START, tracer.on_start)
        monitoring.register_callback(tool, events.PY_RETURN, tracer.on_return)
        monitoring.register_callback(tool, events.PY_UNWIND, tracer.on_unwind)
        monitoring.restart_events()  # forget DISABLE decisions from earlier runs
        monitoring.set_events(tool, events.PY_START | events.PY_RETURN | events.PY_UNWIND)
        yield tracer
    finally:
        monitoring.set_events(tool, 0)
        for event in (events.PY_START, events.PY_RETURN, events.PY_UNWIND):
            monitoring.register_callback(tool, event, None)
        monitoring.free_tool_id(tool)
        tracer.close_remaining()
        if tracer.dropped:
            recorder.finish_attributes["replaylab.dropped_spans"] = tracer.dropped
        recorder.finish_attributes["replaylab.recorded_spans"] = tracer.recorded


def trace_script(
    script: Path,
    args: list[str] | None = None,
    *,
    root: Path | None = None,
    name: str | None = None,
    max_spans: int = DEFAULT_MAX_SPANS,
) -> tuple[Recorder, BaseException | None]:
    """Run a Python file as __main__ under the automatic tracer.

    Returns the recorder and the exception the script raised (or None).
    The exception is returned instead of raised so the events can still
    be sent: a crash is exactly what you want to look at.
    """
    script = script.resolve()
    if not script.is_file():
        raise FileNotFoundError(f"script not found: {script}")
    root = (root or script.parent).resolve()
    run_name = name or f"{script.parent.name}.{script.stem}"

    old_argv, old_path = sys.argv[:], sys.path[:]
    sys.argv = [str(script), *(args or [])]
    sys.path.insert(0, str(script.parent))  # same as `python script.py`
    old_cwd = os.getcwd()
    error: BaseException | None = None
    recorder: Recorder | None = None
    try:
        with run(run_name, attributes={"mode": "auto", "script": script.relative_to(root).as_posix() if script.is_relative_to(root) else script.name}, project_root=root) as recorder:
            with auto_instrument(recorder, root, max_spans):
                try:
                    runpy.run_path(str(script), run_name="__main__")
                except SystemExit as exit_:
                    if exit_.code not in (0, None):
                        raise
    except BaseException as exc:  # noqa: BLE001 - we report it, not hide it
        if isinstance(exc, KeyboardInterrupt):
            raise
        error = exc
    finally:
        sys.argv, sys.path[:] = old_argv, old_path
        os.chdir(old_cwd)
    assert recorder is not None
    return recorder, error
