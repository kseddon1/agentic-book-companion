#!/usr/bin/env python3
"""
pipeline/researchers/sector_research.py — Chapter 9 Lab: a 2-3-researcher
hierarchy with no runtime channel between the researchers.

PRODUCTION NOTE: freemarketresearcher.com's real sector hierarchy is
RagSystem/researchers/market_sectors.py: one script, twelve cron
invocations (11 GICS sectors + the aggregate "market"), five minutes
apart (05:30-06:25 weekdays), argparse `--sector` validated against a
fixed `SECTOR_DEFINITIONS` enum [src: RagSystem/researchers/
market_sectors.py:43,55-91,375-389]. Every invocation shares the same
`FinanceResearcher` Qdrant corpus and the same `ResearchSession` base
class [src: RagSystem/researchers/base.py], but each is a fresh,
separate process with no memory of, or channel to, any other
invocation -- not even the one that ran five minutes earlier for a
different sector. Cross-domain researchers (`ag.py`, `tech.py`) go
further: they don't even share the corpus, reading `AgResearcher-1`
and `TechResearcher` respectively instead of `FinanceResearcher`
[src: RagSystem/researchers/ag.py:22; tech.py:24].

This module is the Chapter 9 Lab's minimal stand-in for BOTH silo
shapes at once, collapsed into one `--sector` argument for a 2-3-
researcher Lab:

  - Each `sector_key` below maps to its OWN fixture directory under
    `sample_sources/` and its OWN JSON vector-store file under
    `data/` -- the hard, cross-domain partition `ag.py`/`tech.py`
    actually have (two different corpora, by construction, not by
    accident).
  - Each `run_sector()` call is a fresh function call that only reads
    its own corpus and writes its own report file under
    `output/reports/<sector_key>.md` -- mirroring the soft,
    within-domain silo `market_sectors.py --sector energy` vs
    `--sector healthcare` has even though *those* two really do share
    one corpus: neither ever reads another sector's report, in
    production or here.

What this module deliberately does NOT do: call another sector's
`run_sector()`, read another sector's report file, or share any
in-memory state across sectors. That absence is the whole point --
see pipeline/run_hierarchy.py and pipeline/schedule/gate.py for the
only "coordination" code this Lab has, which checks finished files on
disk after the fact, the same way the real crontab's timing gap does.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.crawler.crawl import ingest  # noqa: E402
from pipeline.researchers.research import synthesize  # noqa: E402

# Each entry is one independent "specialist": its own fixture domain
# (own corpus), its own standing question, its own report label.
# Mirrors SECTOR_DEFINITIONS[key] = {"label", "question", "pillars"}
# in the real market_sectors.py, simplified to what a 2-3-researcher
# Lab needs [src: RagSystem/researchers/market_sectors.py:55-91].
SECTOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    "finance": {
        "label": "Finance Sector — Daily Update",
        "source_dir": "sample_sources/finance",
        "store_path": "data/vector_store_finance.json",
        "question": (
            "What is happening in the finance sector today? Cover bank "
            "earnings drivers, rate sensitivity, payments and fintech "
            "volume trends, and credit quality. Research only -- no "
            "buy/sell/hold language, no position sizing."
        ),
    },
    "ops": {
        "label": "Ops Sector — Daily Update",
        "source_dir": "sample_sources/ops",
        "store_path": "data/vector_store_ops.json",
        "question": (
            "What is happening in engineering operations today? Cover "
            "deployment cadence, rollback practices, and incident "
            "response patterns."
        ),
    },
}


def sector_choices() -> list[str]:
    return sorted(SECTOR_DEFINITIONS)


def run_sector(sector_key: str, cfg: dict, store_path: Optional[Path] = None,
                report_dir: Optional[Path] = None) -> Path:
    """Run one specialist sector researcher end to end: crawl its own
    fixture domain into its own store, retrieve + synthesize, write
    its own report file. Never touches another sector's store or
    report file, and returns only its own `report_path` -- there is
    no return value or side channel another sector could read.

    Mirrors `market_sectors.run(sector, **kw) -> ResearchResult`
    [src: RagSystem/researchers/market_sectors.py:370-372], simplified
    to return the written report path, which is this Lab's hand-off
    artifact -- the same role `~/.researcher_reports/Market_<Sector>.txt`
    plays in production [src: RagSystem/researchers/base.py:53,
    REPORT_DIR].
    """
    if sector_key not in SECTOR_DEFINITIONS:
        raise ValueError(
            f"unknown sector_key {sector_key!r}; expected one of {sector_choices()}"
        )
    definition = SECTOR_DEFINITIONS[sector_key]

    store = Path(store_path) if store_path else REPO_ROOT / definition["store_path"]
    # "Crawl" step: each sector ingests ONLY its own fixture domain into
    # ONLY its own store -- the corpus partition made concrete.
    ingest(definition["source_dir"], store, clear=True)

    report_md, chunks, mode = synthesize(definition["question"], cfg, store)

    header = (
        f"=== {definition['label']} ===\n"
        f"Date: {date.today().isoformat()} | Generated: "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"{'=' * 50}\n\n"
    )
    full_report = header + report_md

    report_dir = Path(report_dir) if report_dir else REPO_ROOT / "output" / "ch09_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{sector_key}.md"
    report_path.write_text(full_report)

    print(f"[sector_research] {sector_key}: mode={mode} chunks_used={len(chunks)} "
          f"corpus={definition['store_path']} -> {report_path}")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ch9 Lab: run one sector specialist researcher"
    )
    parser.add_argument("--sector", choices=sector_choices(), required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--report-dir", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    report_dir = Path(args.report_dir) if args.report_dir else None
    try:
        run_sector(args.sector, cfg, report_dir=report_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
