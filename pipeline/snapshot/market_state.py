#!/usr/bin/env python3
"""
pipeline/snapshot/market_state.py — Chapter 1 Lab: snapshot (right-nav analog)

PRODUCTION NOTE: freemarketresearcher.com's real Market State Snapshot is
QuantModels/publish_market_state.sh -> market_state_publisher.py
(`--publish`), which writes market_state.json and uploads it to
wp-content/uploads/ over SSH. The theme's functions.php
(freemarketresearcher_get_market_state()) reads it back with a 5-day max
age, and sidebar.php renders regime, risk state, trend, volatility,
sector correlation, breadth, as-of time, and a disclaimer. (Note: the
*position-management* tooling that feeds other QuantModels scripts --
opportunity_orchestrator.py, correlationMatrix.py -- is out of scope for
this book per GOAL.md's Scope rule; only the snapshot publisher is used
as an example.)

This module only writes market_state.json locally. The upload-over-SSH
step is out of scope here, same as pipeline/publish/publish.py.

CHAPTER 10 FIX (field-name drift, caught by the Ch10 Blueprint pass):
this module used to write a field called ``as_of``. The real production
publisher writes ``updated_at`` [src:
~/Projects/QuantModels/market_state_publisher.py:145-148], and the real
reader, `functions.php`'s `freemarketresearcher_get_market_state()`, keys
off that exact name and fails closed (returns null / hides the widget) if
it's missing [src:
~/Projects/WordPressThemes/freemarketresearcher/functions.php:117-142].
A companion repo mirroring the wrong field name would teach a reader the
wrong lesson about what that fail-closed check actually keys off of, so
this was a silent schema mismatch worth fixing rather than perpetuating --
not a cosmetic rename. `freshness_check()` below is a direct Python port
of the same fail-closed logic, to make the lesson concrete: missing file,
unreadable file, malformed JSON, missing `updated_at`, and a too-old
`updated_at` all return ``None``, exactly like the PHP function.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402


def publish_snapshot(regime_data: dict, out_dir):
    """Mirrors the production signature `publish_snapshot(regime_data)`
    from the Blueprint. Writes market_state.json locally only."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "market_state.json"

    payload = dict(regime_data)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    out_path.write_text(json.dumps(payload, indent=2))

    print(f"[snapshot] wrote {out_path}")
    print("[snapshot] production equivalent: market_state_publisher.py uploads this "
          "file to wp-content/uploads/ over SSH; functions.php reads it (max age 5 days)")
    return out_path


def freshness_check(path, max_age_days: int = 5):
    """Python port of `freemarketresearcher_get_market_state()`'s fail-closed
    logic [src:
    ~/Projects/WordPressThemes/freemarketresearcher/functions.php:117-142].

    Returns the parsed state dict if the file exists, is readable, parses
    as a JSON object, has an `updated_at` field, and that field is within
    `max_age_days`. Returns None in every other case -- missing file,
    unreadable file, malformed JSON, missing `updated_at`, or a stale
    `updated_at` -- exactly like the PHP function, on the theory that
    silence (hide the widget) is safer than showing stale data as current.
    """
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        state = json.loads(text)
    except ValueError:
        return None
    if not isinstance(state, dict) or not state.get("updated_at"):
        return None
    try:
        updated = datetime.fromisoformat(state["updated_at"])
    except ValueError:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - updated
    if age.total_seconds() > max_age_days * 86400:
        return None
    return state


def main():
    ap = argparse.ArgumentParser(description="Ch1 Lab snapshot (local JSON only, no upload)")
    ap.add_argument("--regime", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = REPO_ROOT / cfg["snapshot"]["output_dir"]
    regime = args.regime or cfg["snapshot"].get("default_regime", "Low-Vol Trending-Up")
    data = {"regime": regime, "risk_state": "Normal", "note": "Chapter 1 Lab mock snapshot"}

    if args.output:
        out_path = Path(args.output)
        publish_snapshot(data, out_path.parent)
    else:
        publish_snapshot(data, out_dir)


if __name__ == "__main__":
    main()
