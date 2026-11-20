"""
tests/test_ch10_lab.py — Chapter 10 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch10_lab.py -v

Or directly with plain Python (no pytest required, same as
tests/test_ch01_lab.py):
    python3 tests/test_ch10_lab.py

Covers every claim this chapter's Lab makes:
  1. Running pipeline/run_pipeline.py produces a status JSONL with
     run_start and exit events (Chapter 5's pipeline.telemetry writer).
  2. pipeline/observability/status_server.py, started as a background
     thread, serves /api/status and shows that run as status=finished.
  3. pipeline/observability/alert_on_failure.py exits 1 against a
     deliberately stale fixture (no exit event, ancient timestamp) and
     exits 0 against the fresh run from step 1.
  4. pipeline/snapshot/market_state.py's freshness_check() returns the
     data for a fresh snapshot and None for a 6-day-old fixture, mirroring
     functions.php's fail-closed behavior.

Uses COMPANION_STATUS_DIR to point pipeline.telemetry (Chapter 5) at an
isolated scratch directory for this test run, so it doesn't collide with
any other run already writing to the repo's default ./output/status/
(this companion repo is a shared, actively-developed target across
chapters; tests must not assume they have ./output/status/ to themselves).
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _run_pipeline_isolated(status_dir: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["COMPANION_STATUS_DIR"] = str(status_dir)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "pipeline" / "run_pipeline.py"),
         "--query", "What does the status feed show during a run?"],
        cwd=REPO_ROOT,
        input="n\n",  # deny the Chapter 7 publish-approval prompt; not this Lab's concern
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


def test_pipeline_emits_run_start_and_exit():
    status_dir = REPO_ROOT / "output" / "_test_ch10_status"
    status_dir.mkdir(parents=True, exist_ok=True)
    for f in status_dir.glob("*.jsonl"):
        f.unlink()

    result = _run_pipeline_isolated(status_dir)
    assert result.returncode == 0, f"run_pipeline.py failed:\n{result.stdout}\n{result.stderr}"

    feed_path = status_dir / "companion-pipeline.jsonl"
    assert feed_path.exists(), "pipeline.telemetry did not write a status feed"

    events = [json.loads(l) for l in feed_path.read_text().splitlines() if l.strip()]
    types = [e["type"] for e in events]
    assert "run_start" in types, f"no run_start event in {types}"
    assert "exit" in types, f"no exit event in {types}"
    assert events[0]["type"] == "run_start"
    assert events[-1]["type"] == "exit"
    return status_dir, feed_path


def test_status_server_shows_finished_run():
    from pipeline.observability import status_server

    status_dir, feed_path = test_pipeline_emits_run_start_and_exit()

    server = status_server.serve(status_dir, host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(0.2)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        runs = {r["researcher"]: r for r in payload["runs"]}
        assert "companion-pipeline" in runs, f"run missing from /api/status: {runs.keys()}"
        assert runs["companion-pipeline"]["status"] == "finished", runs["companion-pipeline"]
    finally:
        server.shutdown()
        server.server_close()


def test_alert_on_failure_catches_stale_fixture_and_passes_fresh_run():
    status_dir, feed_path = test_pipeline_emits_run_start_and_exit()

    # Fresh run from this test's own pipeline execution -> OK, exit 0.
    fresh = subprocess.run(
        [sys.executable, "-m", "pipeline.observability.alert_on_failure",
         "--status-dir", str(status_dir), "--name", "companion-pipeline",
         "--max-age-seconds", "120"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert fresh.returncode == 0, f"expected OK on a fresh run:\n{fresh.stdout}\n{fresh.stderr}"
    assert "OK" in fresh.stdout

    # Deliberately stale fixture -> ALERT, exit 1.
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    stale = subprocess.run(
        [sys.executable, "-m", "pipeline.observability.alert_on_failure",
         "--status-dir", str(fixtures_dir), "--name", "stale_example",
         "--max-age-seconds", "120"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert stale.returncode == 1, f"expected ALERT on the stale fixture:\n{stale.stdout}\n{stale.stderr}"
    assert "ALERT" in stale.stdout and "stale_example" in stale.stdout


def test_market_state_freshness_check():
    from pipeline.snapshot.market_state import freshness_check, publish_snapshot

    scratch = REPO_ROOT / "output" / "_test_ch10_snapshot"
    scratch.mkdir(parents=True, exist_ok=True)
    fresh_path = publish_snapshot({"regime": "Low-Vol Trending-Up"}, scratch)

    fresh_result = freshness_check(fresh_path, max_age_days=5)
    assert fresh_result is not None, "a snapshot written just now should pass freshness_check()"
    assert fresh_result["regime"] == "Low-Vol Trending-Up"

    stale_fixture = REPO_ROOT / "tests" / "fixtures" / "market_state_stale.json"
    stale_result = freshness_check(stale_fixture, max_age_days=5)
    assert stale_result is None, "a 6-day-old snapshot should fail freshness_check(), like functions.php"

    missing_result = freshness_check(scratch / "does_not_exist.json", max_age_days=5)
    assert missing_result is None, "a missing file should fail closed, not raise"


if __name__ == "__main__":
    test_pipeline_emits_run_start_and_exit()
    print("OK: run_pipeline.py emits run_start and exit events via pipeline.telemetry")
    test_status_server_shows_finished_run()
    print("OK: status_server.py /api/status shows the run as status=finished")
    test_alert_on_failure_catches_stale_fixture_and_passes_fresh_run()
    print("OK: alert_on_failure.py -- OK on the fresh run, ALERT+exit1 on the stale fixture")
    test_market_state_freshness_check()
    print("OK: market_state.freshness_check() matches functions.php's fail-closed behavior")
    print()
    print("OK: Chapter 10 Lab ran end to end and verified every claim this chapter makes.")
