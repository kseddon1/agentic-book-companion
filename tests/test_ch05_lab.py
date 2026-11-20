"""
tests/test_ch05_lab.py — Chapter 5 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch05_lab.py -v

Or directly with plain Python (no pytest required, same pattern as
tests/test_ch01_lab.py):
    python3 tests/test_ch05_lab.py

Asserts: after pipeline/run_pipeline.py runs once, output/status/
companion-pipeline.jsonl exists, starts with a run_start event, has at
least one "running"/"done" pair per pipeline stage (crawl, research,
publish, snapshot), and ends with a run_end event where ok is true.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_STAGES = {"crawl", "research", "publish", "snapshot"}

# Isolated, test-only status directory (pipeline/telemetry's
# COMPANION_STATUS_DIR override) so this test's run never shares a file
# with a manual `python3 pipeline/run_pipeline.py` invocation, or with
# another chapter's Lab test, running at the same time on the same repo.
STATUS_DIR = REPO_ROOT / "output" / "_test_ch05_status"


def _read_jsonl(path: Path):
    events = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def test_pipeline_emits_telemetry():
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    for f in STATUS_DIR.glob("*.jsonl"):
        f.unlink()
    status_path = STATUS_DIR / "companion-pipeline.jsonl"

    env = dict(os.environ)
    env["COMPANION_STATUS_DIR"] = str(STATUS_DIR)

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "pipeline" / "run_pipeline.py"),
            "--query",
            "What are the basics of serving an LLM locally?",
            "--mode",
            "unattended",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert result.returncode == 0, f"run_pipeline.py failed:\n{result.stdout}\n{result.stderr}"

    assert status_path.exists(), f"telemetry file was not created at {status_path}"
    events = _read_jsonl(status_path)
    assert len(events) >= 6, f"expected at least 6 events (run_start + 4 stages x running/done + run_end), got {len(events)}"

    assert events[0]["type"] == "run_start", "first event must be run_start"
    assert events[0]["researcher"] == "companion-pipeline"
    assert "pid" in events[0]

    stage_events = [e for e in events if e["type"] == "stage"]
    seen_stages = {e["name"] for e in stage_events}
    assert EXPECTED_STAGES.issubset(seen_stages), f"missing stage events: {EXPECTED_STAGES - seen_stages}"
    for name in EXPECTED_STAGES:
        states = [e["state"] for e in stage_events if e["name"] == name]
        assert "running" in states, f"stage {name} never reported running"
        assert "done" in states, f"stage {name} never reported done"

    run_end_events = [e for e in events if e["type"] == "run_end"]
    assert len(run_end_events) == 1, "expected exactly one run_end event"
    assert run_end_events[0]["ok"] is True, "run_end.ok should be true for a clean run"

    assert events[-1]["type"] == "exit", "last event must be exit"


if __name__ == "__main__":
    test_pipeline_emits_telemetry()
    print("OK: Chapter 5 Lab pipeline emitted JSONL telemetry end to end.")
