#!/usr/bin/env python3
"""
pipeline/observability/alert_on_failure.py — Chapter 10 Lab: staleness check

PRODUCTION NOTE: this is the smallest honest answer to the gap GAPS.md item
5 investigation surfaced and this chapter's Blueprint names directly:
*nobody is notified if a researcher gets stuck mid-run; a human has to open
localhost:8765 and look* [src:
04_rewrite/blueprints/ch10.md Section 1.5/2.4]. Confirmed independently in
this Technical Core pass: `MarketSectorPipeline/src/publish_reports.sh` has
no `mail`/`sendmail` call [src:
~/Projects/MarketSectorPipeline/src/publish_reports.sh:1-31], no `MAILTO=`
line exists in the live crontab, and no MTA (postfix/sendmail/ssmtp/msmtp)
is installed on this machine. There is no alerting of any kind in
production today -- this script is not a port of an existing production
Watchdog (none exists); it is the Blueprint's deliberately small proposal
for what the *smallest* real fix would look like, built here as a Lab
exercise, not shipped to production.

Exit codes: 0 == OK (every checked run has either exited cleanly, or is
recent), 1 == at least one run is stale or hung.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.observability.status import last_event_and_exit_seen  # noqa: E402


def check_one(path: Path, max_age_seconds: float, now: float) -> "tuple[bool, str]":
    """Returns (is_stale, message). A run with no status file at all is
    reported as missing, not stale (different failure mode, same caller's
    problem to notice)."""
    last, exit_seen = last_event_and_exit_seen(path)
    name = path.name[: -len(".jsonl")] if path.name.endswith(".jsonl") else path.name

    if last is None:
        return True, f"ALERT: {name} has no readable status events at {path}"

    age = now - last.get("t", now)
    if exit_seen:
        return False, f"OK: {name} exited cleanly ({age:.1f}s since last event)"

    if age > max_age_seconds:
        return True, (
            f"ALERT: {name} stale or hung -- last event {age:.1f}s ago "
            f"(threshold {max_age_seconds}s), no exit event written"
        )

    return False, f"OK: {name} still running, last event {age:.1f}s ago (within threshold)"


def main():
    ap = argparse.ArgumentParser(
        description="Ch10 Lab: alert if a status feed looks stale or hung"
    )
    ap.add_argument("--status-dir", default="output/status")
    ap.add_argument("--name", default=None,
                     help="check one run by name (without .jsonl); default: check every "
                          "*.jsonl file in --status-dir")
    ap.add_argument("--max-age-seconds", type=float, default=120)
    args = ap.parse_args()

    status_dir = Path(args.status_dir)
    if args.name:
        paths = [status_dir / f"{args.name}.jsonl"]
    else:
        paths = sorted(status_dir.glob("*.jsonl")) if status_dir.exists() else []

    if not paths:
        print(f"ALERT: no status files found in {status_dir}")
        sys.exit(1)

    now = time.time()
    any_stale = False
    for path in paths:
        is_stale, message = check_one(path, args.max_age_seconds, now)
        print(message)
        any_stale = any_stale or is_stale

    sys.exit(1 if any_stale else 0)


if __name__ == "__main__":
    main()
