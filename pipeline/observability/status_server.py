#!/usr/bin/env python3
"""
pipeline/observability/status_server.py — Chapter 10 Lab: polling HTTP reader

PRODUCTION NOTE: mirrors ResearcherDashboard/dashboard.py -- a stdlib-only
ThreadingHTTPServer that tails a directory of status JSONL files and serves
/api/status as JSON [src: ~/Projects/ResearcherDashboard/dashboard.py:1-223].
Deliberately simplified and bound to port 8766 (not 8765) so it never
collides with the real dashboard if both happen to be running on the same
machine, per the Blueprint's explicit instruction.

READS, DOES NOT WRITE: this server reads whatever is already in
`--status-dir` (default `output/status/`, matching `pipeline.telemetry`'s
default -- see `pipeline/observability/status.py`'s module docstring for
why Chapter 10 does not ship a second writer). Point it at the Chapter 1
Lab's `run_pipeline.py` output, or at any of the `tests/fixtures/*.jsonl`
files, and it will show up the same way.

Differences from the real dashboard.py, on purpose:
  - No incremental byte-offset tailing across polls (dashboard.py's Feed
    keeps an open seek position between requests). This reader re-reads
    each file in full on every /api/status request -- simpler to read in
    one sitting, at the cost of not scaling to the real stack's 3 MB
    status files, which is exactly why the real one doesn't do it this
    way [src: ~/Projects/ResearcherDashboard/dashboard.py:44-86].
  - No static HTML page; /api/status is the only endpoint, because the
    Lab's point is the JSON feed, not a UI.
  - No KNOWN_RESEARCHERS display-order list; runs are sorted by filename.

Status derivation mirrors dashboard.py's real rule set exactly (see
pipeline/observability/status.py's derive_status()) [src:
~/Projects/ResearcherDashboard/dashboard.py:118-127]:
  finished     -- exit event present, and run_end was seen
  stopped      -- exit event present, but no run_end was seen
  killed       -- process no longer alive, no exit event, no run_end
  report_ready -- run_end seen but process still alive, no exit yet
  running      -- otherwise
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.observability.status import derive_status, fold_events, read_events  # noqa: E402


def read_feed(path: Path) -> dict:
    events = read_events(path)
    state = fold_events(events)
    name = path.name[: -len(".jsonl")] if path.name.endswith(".jsonl") else path.name
    return {
        "researcher": name,
        "status": derive_status(state),
        "pid": state["pid"],
        "started": state["started"],
        "ended": state["ended"],
        "exited": state["exited"],
        "updated": state["updated"],
        "stages": [{"name": n, **s} for n, s in state["stages"].items()],
        "progress": state["progress"],
    }


def snapshot(status_dir: Path) -> dict:
    status_dir = Path(status_dir)
    try:
        names = sorted(f for f in os.listdir(status_dir) if f.endswith(".jsonl"))
    except FileNotFoundError:
        names = []
    runs = [read_feed(status_dir / n) for n in names]
    return {"now": time.time(), "status_dir": str(status_dir), "runs": runs}


def make_handler(status_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/status":
                body = json.dumps(snapshot(status_dir), default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = b"Not found. This Lab server only implements /api/status."
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep the console quiet, same as the real dashboard.py

    return Handler


def serve(status_dir: Path, host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    """Build and return a started-but-not-yet-serving server object, so
    tests can run it in a background thread. main() below calls
    .serve_forever() on the object this returns."""
    return ThreadingHTTPServer((host, port), make_handler(status_dir))


def main():
    ap = argparse.ArgumentParser(
        description="Ch10 Lab: polling HTTP status reader (reads Chapter 5's telemetry feed)"
    )
    ap.add_argument("--port", type=int, default=8766,
                     help="default 8766 -- deliberately not 8765, the real dashboard's port")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--status-dir", default="output/status",
                     help="default matches pipeline.telemetry's default status dir")
    args = ap.parse_args()

    status_dir = Path(args.status_dir)
    server = serve(status_dir, args.host, args.port)
    print(f"[status_server] watching {status_dir}")
    print(f"[status_server] serving http://{args.host}:{args.port}/api/status  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
