"""
pipeline/publish/checkpoint.py — Chapter 8 Lab: checkpoint/state-file helpers.

Mirrors the REAL production shape, read live off
~/Projects/MarketSectorPipeline/state.json and
PublicationManager.py:105-119 (_load_state/_save_state):

    {"published_files": ["Market_energy.txt", "Market_financials.txt", ...]}

-- a flat "done list", not a structured transaction log. There is no
timestamp, no post ID, and no pending/failed split in production.
Don't add one here either -- this module demonstrates the real shape,
not an invented, richer one.

ONE DELIBERATE IMPROVEMENT over production, clearly called out:
production's PublicationManager._save_state() does a plain
`json.dump(self.state, f, indent=4)` straight into the real path --
no temp file, no os.replace(), no fsync. If the process is killed
mid-write, the state file itself can be left truncated or corrupted
(a second, distinct failure mode from the crash-between-side-effect-
and-state-write race this chapter's Lab is built around). This module
writes to a sibling `.tmp` file and atomically os.replace()s it over
the real path, so at least the state file's own write can never be
left half-done. This is the companion repo's OWN hardening -- it does
NOT exist in PublicationManager.py today. See Chapter 8, "State
Management and Idempotency," for why that gap matters and why this
Lab adds the fix here instead of pretending production already has it.
"""
import json
import os

DEFAULT_STATE = {"published_files": []}


def load_state(path) -> dict:
    """Load {"published_files": [...]}; returns the default shape on
    a missing file or any parse error -- the same fallback
    PublicationManager._load_state() uses [src: PublicationManager.py:105-110]."""
    path = str(path)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and "published_files" in data:
                return data
        except Exception:
            pass
    return {"published_files": []}


def save_state(path, state: dict) -> None:
    """Atomic write: serialize to a sibling `<path>.tmp`, fsync it,
    then os.replace() it over the real path.

    Production's PublicationManager._save_state() [src:
    PublicationManager.py:112-116] does a plain
    `json.dump(self.state, f, indent=4)` with no temp file and no
    os.replace() -- this atomic-swap version is the companion repo's
    own hardening, not a claim about what ships in production today.
    """
    path = str(path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
