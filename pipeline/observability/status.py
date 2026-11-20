#!/usr/bin/env python3
"""
pipeline/observability/status.py — Chapter 10 Lab: shared status-feed
reading helpers (used by status_server.py and alert_on_failure.py).

REVISED DURING TECHNICAL CORE: this module originally specified a
`StatusWriter` -- a JSONL *writer* -- per this chapter's Blueprint
(Section 6). While this Technical Core pass was in progress, Chapter 5's
own Lab landed in this same companion repo first and already built that
writer: `pipeline/telemetry/` (its own docstring: "Chapter 5 Lab: JSONL
status feed for the companion pipeline"), wired into
`pipeline/run_pipeline.py` as `telemetry.start_run()` /
`telemetry.stage()` / `telemetry.end_run()`, writing the real six-type
event vocabulary to `./output/status/<name>.jsonl`.

Building a second, parallel writer here would misrepresent the real
stack this book documents: production has exactly ONE emitter
(`RagSystem/adapter/dashboard.py`) per researcher, read by an
independent process (`ResearcherDashboard/dashboard.py`) that never
writes to the feed itself [src: ~/Projects/RagSystem/adapter/
dashboard.py:1-20; ~/Projects/ResearcherDashboard/dashboard.py:1-20].
Chapter 10's real job, in both the book and the production system, is
the **reading** side: a dashboard and an alert check, built on top of
whatever already wrote the feed. So this module keeps only the reading
helpers, and `pipeline/observability/status_server.py` and
`alert_on_failure.py` both read from Chapter 5's `pipeline.telemetry`
output directory (`output/status/`) by default -- the same directory, no
new writer, matching the real one-emitter/one-reader split.

(This is also an honest, sourced instance of the cross-chapter
sequencing risk this chapter's own Blueprint flagged in advance, Section
3: "Chapter 5's own Blueprint does not exist yet... a real cross-chapter
dependency risk." It landed mid-Technical-Core, in the companion repo,
not the prose -- this module's revision is the concrete record of it.)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def read_events(path) -> list:
    """Read one status JSONL file into a list of parsed events, tolerating
    a trailing partial line (a process that died mid-write) and any line
    that fails to parse -- same tolerance as ResearcherDashboard/
    dashboard.py's Feed._apply() [src:
    ~/Projects/ResearcherDashboard/dashboard.py:71-80]."""
    path = Path(path)
    events = []
    if not path.exists():
        return events
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


def fold_events(events: list) -> dict:
    """Fold a list of parsed events into one run-state dict -- the same
    reduction ResearcherDashboard/dashboard.py's Feed._apply() does
    incrementally, one line at a time, as new bytes arrive [src:
    ~/Projects/ResearcherDashboard/dashboard.py:88-116]. Here it runs once
    over the whole file per request, which is the simplification this
    Lab's status_server.py documents explicitly."""
    state = {
        "pid": None,
        "started": None,
        "ended": None,
        "exited": None,
        "updated": None,
        "stages": {},
        "progress": {},
        "items": {},
    }
    for ev in events:
        t = ev.get("t")
        state["updated"] = t
        kind = ev.get("type")
        if kind == "run_start":
            state["pid"] = ev.get("pid")
            state["started"] = t
        elif kind == "run_end":
            state["ended"] = t
        elif kind == "exit":
            state["exited"] = t
        elif kind == "stage" and "name" in ev:
            stage = state["stages"].setdefault(ev["name"], {})
            stage["state"] = ev.get("state")
            if ev.get("state") == "running":
                stage["started"] = t
            else:
                stage["elapsed"] = ev.get("elapsed")
        elif kind == "progress" and "kind" in ev:
            state["progress"][ev["kind"]] = {"done": ev.get("done"), "total": ev.get("total")}
        elif kind == "item" and "kind" in ev and "key" in ev:
            # Chapter 5's companion telemetry module doesn't emit "item"
            # events (it covers run_start/stage/progress/run_end/exit
            # only); real production researchers do. Handled here so this
            # reader is forward-compatible with either.
            bucket = state["items"].setdefault(ev["kind"], {})
            item = bucket.setdefault(ev["key"], {"key": ev["key"]})
            for field, value in ev.items():
                if field not in ("t", "type", "kind", "key"):
                    item[field] = value
    return state


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    import os
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def derive_status(state: dict) -> str:
    """Same four-way (five-way counting 'running') status derivation as
    ResearcherDashboard/dashboard.py [src:
    ~/Projects/ResearcherDashboard/dashboard.py:118-127]."""
    alive = _pid_alive(state["pid"])
    if state["exited"]:
        return "finished" if state["ended"] else "stopped"
    if not alive:
        return "finished" if state["ended"] else "killed"
    if state["ended"]:
        return "report_ready"
    return "running"


def last_event_and_exit_seen(path) -> "tuple[Optional[dict], bool]":
    """Return (last_event, exit_seen) for one status JSONL file. Used by
    alert_on_failure.py: a run with no exit event and an old last-event
    timestamp is exactly the "stuck mid-run, nobody notified" gap this
    chapter's Blueprint names as the honest, currently-unfixed hole in
    this stack's observability (GAPS.md item 5 investigation; Section 1.5
    of 04_rewrite/blueprints/ch10.md)."""
    events = read_events(path)
    if not events:
        return None, False
    last = events[-1]
    exit_seen = any(ev.get("type") == "exit" for ev in events)
    return last, exit_seen
