#!/usr/bin/env python3
"""
pipeline/schedule/gate.py — Chapter 9 Lab: the enforced-ordering gate.

PRODUCTION NOTE: freemarketresearcher.com's real coordination mechanism
between the sector researcher block and the publish pipeline is a
cron timing gap, nothing else: the last `market_sectors` sector job
fires at 06:25 and `MarketSectorPipeline/src/publish_reports.sh` fires
at 06:45 [src: 01_notes/production_inventory_freemarketresearcher.md,
Stage 2/Stage 3]. No code anywhere checks that all twelve reports
actually landed before the publish job starts -- the 20-minute gap
*is* the entire coordination contract, and it is invisible: nothing
in production would print a warning if a researcher ran long and the
gap wasn't enough.

This module makes that same bet INSPECTABLE instead of invisible. It
is the only "coordination" code in this whole Lab, and it does not
message, poll, or wait for anything -- it checks filesystem state
once, after the fact, exactly like the real schedule's blind gap, and
it fails CLOSED: any missing or stale expected artifact is a refusal
to proceed, never a best-effort partial publish.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Optional, Union

PathLike = Union[str, Path]


def check_ready(expected_report_paths: Iterable[PathLike],
                 not_before: Optional[float] = None) -> bool:
    """Return True only if every expected report file exists AND (when
    `not_before` is given) was written at or after that timestamp.

    `not_before` is what turns this from a one-time existence check
    into a real freshness check: a report file left over from a prior
    run (a researcher that hung yesterday and never got its output
    overwritten today) must not count as "ready" just because a file
    happens to sit at the expected path. Pass the wall-clock time the
    hierarchy run started as `not_before` so a stale leftover reads
    as stale, not as present.

    Fails closed: any missing or stale path returns False immediately
    on the first one. There is no partial-ready return value and no
    code path that returns True on anything other than "every single
    expected artifact is present and fresh."
    """
    paths = [Path(p) for p in expected_report_paths]
    all_ready = True
    for path in paths:
        if not path.exists():
            print(f"[gate] MISSING: {path}")
            all_ready = False
            continue
        if not_before is not None:
            mtime = path.stat().st_mtime
            if mtime < not_before:
                age_s = round(not_before - mtime, 1)
                print(
                    f"[gate] STALE: {path} was last written {age_s}s before this "
                    f"run started -- it did not run (or finish) this cycle"
                )
                all_ready = False
                continue
        print(f"[gate] ready: {path}")

    if all_ready:
        print(f"[gate] READY: all {len(paths)} expected report(s) present")
    return all_ready


def now() -> float:
    """Thin wrapper so callers (and tests) have one place to patch the
    clock if they ever need to; also documents that `not_before`
    expects the same units as `time.time()` / `Path.stat().st_mtime`."""
    return time.time()
