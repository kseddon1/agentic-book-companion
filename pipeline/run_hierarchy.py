#!/usr/bin/env python3
"""
pipeline/run_hierarchy.py — Chapter 9 Lab: run the 2-3-researcher
hierarchy end to end, with enforced cron-gap-style ordering.

This is the single command the Chapter 9 Lab runs twice:

  python3 -m pipeline.run_hierarchy --sectors ops,finance
  python3 -m pipeline.run_hierarchy --sectors ops,finance --simulate-late finance

STAGE 1 runs each sector researcher independently -- no shared state,
no return value one researcher can see from another, each reading
only its own fixture corpus (pipeline/researchers/sector_research.py).

STAGE 2 is the ONLY coordination code in this Lab: a filesystem check,
done once, after the fact (pipeline/schedule/gate.py), mirroring the
real crontab's blind 20-minute gap between the last `market_sectors`
job (06:25) and `MarketSectorPipeline/src/publish_reports.sh` (06:45)
[src: 01_notes/production_inventory_freemarketresearcher.md, Stage
2/3]. Production has no code resembling STAGE 2 at all -- the gap
itself is the whole mechanism, and nothing checks it. This Lab adds
the check as a teaching artifact, not a claim that production already
has one.

STAGE 3 publishes only if STAGE 2 passed (pipeline.publish.publish.
publish_hierarchy), refusing outright and writing nothing otherwise.

`--simulate-late <sector_key>` withholds that sector's researcher run
entirely for this cycle -- the Lab's stand-in for a late or hung
production run that never finished before the publish pipeline's
fixed start time. Combined with `not_before` in the gate check, a
report file left over from an earlier cycle at that sector's expected
path reads as STALE, not as present -- the gate cannot be fooled by a
stale leftover from yesterday's run.
"""
import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.publish.publish import publish_hierarchy  # noqa: E402
from pipeline.researchers.sector_research import run_sector, sector_choices  # noqa: E402
from pipeline.schedule.gate import check_ready  # noqa: E402


def _banner(text: str) -> None:
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ch9 Lab: run a 2-3-researcher hierarchy with an "
                     "enforced cron-gap-style publish gate"
    )
    ap.add_argument("--sectors", default="ops,finance",
                     help="comma-separated sector keys, e.g. 'ops,finance' "
                          f"(available: {','.join(sector_choices())})")
    ap.add_argument("--simulate-late", default=None,
                     help="sector key to withhold this cycle, simulating a "
                          "late/hung researcher run")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    sectors = [s.strip() for s in args.sectors.split(",") if s.strip()]
    unknown = [s for s in sectors if s not in sector_choices()]
    if unknown:
        print(f"[run_hierarchy] ERROR: unknown sector key(s) {unknown}; "
              f"choices are {sector_choices()}")
        return 2

    cfg = load_config(args.config)
    # NOTE: namespaced under output/ch09_reports/, not the shared
    # output/reports/ -- see pipeline/run_hierarchy.py module docstring
    # and 04_rewrite/core/ch09.md "What Broke" for why: this companion
    # repo is worked on by several chapters' Labs concurrently, and a
    # shared output/reports/ directory was observed, while building
    # this Lab, to be cleared mid-run by another chapter's own test
    # cycle. Namespacing by chapter is the fix, not a claim that the
    # production researchers need anything like it (they already each
    # write to their own fixed path, ~/.researcher_reports/Market_
    # <Sector>.txt, with no shared directory to collide on).
    report_dir = REPO_ROOT / "output" / "ch09_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Captured BEFORE any researcher runs this cycle, so the gate can
    # tell "wrote fresh just now" apart from "sitting there from a
    # previous cycle" -- see pipeline/schedule/gate.py's `not_before`.
    cycle_started_at = time.time()

    _banner("STAGE 1/3: run each sector researcher independently (no shared state)")
    expected_paths = [report_dir / f"{sector}.md" for sector in sectors]
    produced_paths = []
    for sector, expected_path in zip(sectors, expected_paths):
        if sector == args.simulate_late:
            print(
                f"[run_hierarchy] SIMULATING LATE/HUNG RUN: withholding the "
                f"{sector!r} researcher this cycle. Its report path "
                f"({expected_path}) will NOT be (re)written -- any file "
                f"sitting there is from a prior cycle, and the gate below "
                f"must treat it as stale, not ready."
            )
            continue
        produced_path = run_sector(sector, cfg, report_dir=report_dir)
        produced_paths.append(produced_path)
        print(f"[run_hierarchy] {sector!r} researcher finished; it has no way to "
              f"know any other sector in this list exists.")

    _banner("STAGE 2/3: schedule gate (the cron-gap, made inspectable)")
    ready = check_ready(expected_paths, not_before=cycle_started_at)

    _banner("STAGE 3/3: publish (only if the gate passed)")
    if not ready:
        missing = [str(p) for p in expected_paths if not p.exists()]
        stale = [str(p) for p in expected_paths
                 if p.exists() and p.stat().st_mtime < cycle_started_at]
        print(f"[run_hierarchy] GATE FAILED. missing={missing or '[]'} stale={stale or '[]'}")
        print("[run_hierarchy] publish refused -- nothing was published this cycle.")
        return 1

    publish_hierarchy(
        produced_paths,
        REPO_ROOT / "output",
        out_filename="ch09_post.md",
        gate_report_paths=expected_paths,
        not_before=cycle_started_at,
        category=cfg["publisher"].get("default_category", "Commentary"),
        target=cfg["publisher"].get("type", "dryrun"),
    )
    print("[run_hierarchy] GATE PASSED: all expected reports were present and fresh; published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
