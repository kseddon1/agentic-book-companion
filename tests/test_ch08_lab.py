"""
tests/test_ch08_lab.py — Chapter 8 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch08_lab.py -v

Or directly with plain Python (no pytest required, matching the Ch1
Lab's pattern):
    python3 tests/test_ch08_lab.py

Exercises two mechanisms, both mirroring real, cited production
constants rather than an invented incident (GOAL.md Section 6):

1. checkpoint.py + publish.publish_batch() crash/resume sequence --
   demonstrates the real gap between "the side effect happened" and
   "the checkpoint recorded it," which is exactly the gap that lets
   AnalysisPipeline/BriefPipeline's complete lack of a state file, or
   MarketSectorPipeline's per-run state reset, leave a duplicate post
   on the live site in production.
2. transport.py's retry_wrapper() -- the exact max_attempts=7 and
   2**attempt backoff from WPPublisher._retry_wrapper.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "sample_sources" / "ch08_reports"
OUT_DIR = REPO_ROOT / "output" / "ch08_lab"
STATE_PATH = OUT_DIR / "state.json"
LOG_PATH = OUT_DIR / "published_posts.log"

sys.path.insert(0, str(REPO_ROOT))
from pipeline.publish import transport  # noqa: E402


def _reset_lab_output():
    """Clean both the custom state-file dir (output/ch08_lab/) and the
    config-driven publisher output dir (output/posts/,
    output/published_posts.log) so each test run starts from a known
    empty state, exactly like a reader re-running the Lab fresh."""
    import shutil
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cfg_out_dir = REPO_ROOT / "output"
    posts_dir = cfg_out_dir / "posts"
    if posts_dir.exists():
        shutil.rmtree(posts_dir)
    log_path = cfg_out_dir / "published_posts.log"
    if log_path.exists():
        log_path.unlink()


def _run_publish_batch(crash_after=None):
    cmd = [
        sys.executable, "-m", "pipeline.publish.publish",
        "--batch-dir", str(FIXTURES_DIR),
        "--state-file", str(STATE_PATH),
    ]
    if crash_after is not None:
        cmd += ["--crash-after", str(crash_after)]
    # publish_batch reads cfg["publisher"]["output_dir"] for the posts
    # log/posts dir; point it at our own scratch dir via a temp config
    # override is unnecessary here because publish_batch is only
    # reachable via the installed config.yaml -- but the Ch8 Lab needs
    # its own output dir, so pass it through the environment-free
    # route: run the CLI with cwd set so config.yaml's output_dir
    # ("output") lands under output/, then we point state-file and
    # inspect output/ + output/ch08_lab manually instead.
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    return result


def test_crash_then_resume_shows_duplicate():
    """Reproduces the Blueprint's Lab steps 2-3: crash after report 3's
    side effect but before its checkpoint; resume; confirm reports 1-2
    are correctly skipped (checkpoint dedup works) while report 3 was
    actually published TWICE across the two runs (the real gap)."""
    _reset_lab_output()

    # Run 1: crash after the 3rd report's side effect lands, before its
    # checkpoint is saved. 4 fixtures sorted alphabetically:
    # Market_energy.txt, Market_financials.txt, Market_market.txt,
    # Market_technology.txt -- so idx 3 is Market_market.txt.
    result1 = _run_publish_batch(crash_after=3)
    assert result1.returncode != 0, (
        f"expected a simulated crash (nonzero exit) on run 1, got 0.\n"
        f"stdout:\n{result1.stdout}\nstderr:\n{result1.stderr}"
    )
    assert "SIMULATE_CRASH" in result1.stdout

    out_dir = REPO_ROOT / "output"  # config.example.yaml publisher.output_dir
    state_after_crash = json.loads(STATE_PATH.read_text())
    published_after_crash = state_after_crash["published_files"]
    assert published_after_crash == ["Market_energy.txt", "Market_financials.txt"], (
        f"checkpoint should show exactly reports 1-2 done after the crash, got: {published_after_crash}"
    )

    log_path = out_dir / "published_posts.log"
    log_lines_after_crash = log_path.read_text().strip().splitlines()
    assert len(log_lines_after_crash) == 3, (
        f"the mock 'WordPress side' should show 3 posts went out (the side "
        f"effect for report 3 landed before the crash), got {len(log_lines_after_crash)}:\n"
        f"{log_lines_after_crash}"
    )
    assert any("Market_market.txt" in line for line in log_lines_after_crash), (
        "report 3's side effect should be logged even though its checkpoint wasn't saved"
    )

    # Run 2: resume with no crash flag. Reports 1-2 must be skipped
    # (checkpoint dedup). Report 3 is NOT in published_files, so it
    # gets republished -- a real duplicate post, demonstrated, not
    # merely claimed.
    result2 = _run_publish_batch(crash_after=None)
    assert result2.returncode == 0, f"resume run should exit cleanly:\n{result2.stdout}\n{result2.stderr}"
    assert "SKIP Market_energy.txt" in result2.stdout
    assert "SKIP Market_financials.txt" in result2.stdout

    final_state = json.loads(STATE_PATH.read_text())
    assert final_state["published_files"] == [
        "Market_energy.txt", "Market_financials.txt", "Market_market.txt", "Market_technology.txt",
    ], f"final checkpoint should have all 4 reports: {final_state['published_files']}"

    final_log_lines = log_path.read_text().strip().splitlines()
    market_count = sum(1 for line in final_log_lines if "Market_market.txt" in line)
    energy_count = sum(1 for line in final_log_lines if "Market_energy.txt" in line)
    financials_count = sum(1 for line in final_log_lines if "Market_financials.txt" in line)

    assert energy_count == 1, f"report 1 must appear exactly once in the published log, got {energy_count}"
    assert financials_count == 1, f"report 2 must appear exactly once in the published log, got {financials_count}"
    assert market_count == 2, (
        f"report 3 (Market_market.txt) must appear TWICE in the published log -- "
        f"once from the crashed run's side effect, once from the resume republishing "
        f"it because its checkpoint was never saved. This IS the duplicate-publication "
        f"gap, demonstrated on fixture data. Got {market_count}."
    )
    print("[test] duplicate confirmed: Market_market.txt was published twice "
          "across the crash/resume sequence, exactly as the real checkpoint gap predicts.")


def test_transport_retry_succeeds_within_max_attempts():
    """fail-times=4 should succeed on attempt 5 -- well inside the real
    WPPublisher.py max_attempts=7 [src: WPPublisher.py:25]."""
    ok, attempts, result = transport.retry_wrapper(fail_times=4, sleep_scale=0.001)
    assert ok is True
    assert attempts == 5
    assert result == "OK"


def test_transport_retry_exhausts_cleanly():
    """fail-times=8 exceeds max_attempts=7 -- the wrapper must give up
    cleanly (no infinite retry) and report failure, matching the real
    wrapper's actual behavior at the end of 7 attempts."""
    ok, attempts, result = transport.retry_wrapper(fail_times=8, sleep_scale=0.001)
    assert ok is False
    assert attempts == transport.MAX_ATTEMPTS == 7


if __name__ == "__main__":
    test_crash_then_resume_shows_duplicate()
    print("OK: crash/resume checkpoint demonstration passed.")
    test_transport_retry_succeeds_within_max_attempts()
    print("OK: transport retry succeeds within max_attempts.")
    test_transport_retry_exhausts_cleanly()
    print("OK: transport retry exhausts cleanly at max_attempts.")
    print("OK: Chapter 8 Lab -- all checkpoint/transport demonstrations passed.")
