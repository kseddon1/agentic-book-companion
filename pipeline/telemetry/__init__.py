"""
pipeline/telemetry — Chapter 5 Lab: JSONL status feed for the companion pipeline.

PRODUCTION NOTE: freemarketresearcher.com's real researchers import
RagSystem/adapter/dashboard.py (itself refactored from the older, per-researcher
FinanceResearcher/FinanceResearcher/progress.py, TechResearcher/progress.py, and
AgResearcher-1/progress.py). Every researcher run writes one JSON-lines file,
~/.researcher_status/<name>.jsonl, read live by ResearcherDashboard
(localhost:8765) -- the Chapter 10 subject. See
RagSystem/researchers/base.py:39,172-173 and RagSystem/researchers/finance.py:207
for the real wiring (status_name = "RagSystem_finance").

This module is a minimal, dependency-free re-implementation of that same
contract for the companion repo, so the Chapter 5 Lab produces a real file a
reader can `cat` and inspect, not a description of one. It writes to
./output/status/<name>.jsonl (a repo-local stand-in for ~/.researcher_status/),
overridable with the COMPANION_STATUS_DIR environment variable for testing.

Event shape (one JSON object per line, identical field names to the real
dashboard.py docstring):

    {"t": <epoch>, "type": "run_start", "researcher": <name>, "pid": <pid>}
    {"t": ..., "type": "stage",    "name": ..., "state": "running"|"done"|"failed", "elapsed": s}
    {"t": ..., "type": "progress", "kind": ..., "done": k, "total": N}
    {"t": ..., "type": "run_end",  "ok": bool, "error": str?}
    {"t": ..., "type": "exit"}

Safety contract (same promise the real dashboard.py makes): nothing here
raises into, or blocks, the caller. Until start_run() is called, every
reporting call is a no-op. A write failure disables the feed after one
warning instead of crashing the pipeline. This is a *telemetry* feed, not a
source of truth the pipeline depends on to run correctly.

Typical use::

    from pipeline import telemetry

    telemetry.start_run("companion-pipeline")
    with telemetry.stage("crawl"):
        ...
    telemetry.end_run(ok=True)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

__all__ = ["status_dir", "start_run", "end_run", "stage", "emit", "progress", "is_active"]

_lock = threading.RLock()
_file = None
_name: Optional[str] = None
_ended = False


def status_dir() -> Path:
    """Where status files are written. Override with COMPANION_STATUS_DIR
    (used by tests.test_ch05_lab.py to point at a scratch directory)."""
    override = os.environ.get("COMPANION_STATUS_DIR")
    if override:
        return Path(override)
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / "output" / "status"


def _warn(msg: str) -> None:
    try:
        print(f"[WARN] telemetry: {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def is_active() -> bool:
    return _file is not None


def _write(event_type: str, **fields: Any) -> None:
    """Append one event. Caller must hold ``_lock``."""
    global _file
    if _file is None:
        return
    try:
        line = json.dumps({"t": time.time(), "type": event_type, **fields}, default=str)
        _file.write(line + "\n")
        _file.flush()
    except Exception as e:  # IO error, closed file, unserializable data: drop the feed, never raise
        _warn(f"disabled after write error: {e}")
        try:
            _file.close()
        except Exception:
            pass
        _file = None


def emit(event_type: str, **fields: Any) -> None:
    """Append a raw event to the feed. Never raises."""
    try:
        with _lock:
            _write(event_type, **fields)
    except Exception:
        pass


def start_run(name: str) -> bool:
    """Start (replace) the feed for ``name``, writing to
    ``<status_dir>/<name>.jsonl``. Returns True if the feed is active."""
    global _file, _name, _ended
    try:
        with _lock:
            d = status_dir()
            try:
                d.mkdir(parents=True, exist_ok=True)
                _file = open(d / f"{name}.jsonl", "w", encoding="utf-8")
            except OSError as e:
                _file = None
                _warn(f"disabled: {e}")
                return False
            _name, _ended = name, False
            _write("run_start", researcher=name, pid=os.getpid())
            return _file is not None
    except Exception as e:
        _warn(f"disabled: {e}")
        return False


def end_run(ok: bool = True, error: Optional[str] = None) -> None:
    """Mark the run complete (``run_end``). Only the first call per run is recorded."""
    global _ended
    try:
        with _lock:
            if _file is None or _ended:
                return
            _ended = True
            fields: dict = {"ok": ok}
            if error:
                fields["error"] = error
            _write("run_end", **fields)
            _write("exit")
    except Exception:
        pass


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Report a pipeline stage as running, then done/failed with its elapsed seconds.

    Mirrors RagSystem/adapter/dashboard.py's ``stage()`` context manager
    exactly: emit "running" on entry, "done" (or "failed", on exception) with
    elapsed seconds on exit, and re-raise whatever the caller raised.
    """
    start = time.perf_counter()
    emit("stage", name=name, state="running")
    state = "failed"
    try:
        yield
        state = "done"
    finally:
        emit("stage", name=name, state=state, elapsed=round(time.perf_counter() - start, 3))


def progress(kind: str, done: int, total: int) -> None:
    emit("progress", kind=kind, done=done, total=total)
