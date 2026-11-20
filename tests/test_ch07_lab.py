"""
tests/test_ch07_lab.py — Chapter 7 Lab verification: the approval gate.

Run with pytest if installed:
    pytest tests/test_ch07_lab.py -v

Or directly with plain Python (no pytest required -- matches the
Chapter 1 Lab's own "zero pip installs" rule):
    python3 tests/test_ch07_lab.py

Asserts the three STOP-for-approval cases the Chapter 7 Blueprint
requires (Section 3, "What Technical Core must add" -> tests/
test_ch07_lab.py row):
  1. attended + "y"  -> output/post.md IS written.
  2. attended + "n" (and attended + EOF, simulating a timeout) ->
     output/post.md is NOT (re)written, and the run still exits 0 --
     a denial is a clean stop, not a crash.
  3. unattended -> output/post.md is NOT written, pending/
     publish_commentary_report.json IS written with status=PENDING,
     and the run exits 0 -- a graceful stop is not an error.

A fourth check closes the loop: resolving that pending record with
--resume-pending and answering "y" writes post.md and flips the
record to status=APPROVED.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PENDING_PATH = REPO_ROOT / "pending" / "publish_commentary_report.json"
POST_PATH = REPO_ROOT / "output" / "post.md"
QUERY = "What are the basics of serving an LLM locally?"


def _run(args, stdin_text):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "pipeline" / "run_pipeline.py"), *args],
        cwd=REPO_ROOT,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _reset():
    POST_PATH.unlink(missing_ok=True)
    PENDING_PATH.unlink(missing_ok=True)


def test_attended_approve_publishes():
    _reset()
    result = _run(["--mode", "attended", "--query", QUERY], stdin_text="y\n")
    assert result.returncode == 0, f"attended+y failed:\n{result.stdout}\n{result.stderr}"
    assert POST_PATH.exists(), "attended+y should have written output/post.md"
    assert "DENIED" not in result.stdout


def test_attended_deny_does_not_publish():
    _reset()
    result = _run(["--mode", "attended", "--query", QUERY], stdin_text="n\n")
    assert result.returncode == 0, f"attended+n should exit 0 cleanly:\n{result.stdout}\n{result.stderr}"
    assert not POST_PATH.exists(), "attended+n must not write output/post.md"
    assert "DENIED" in result.stdout


def test_attended_eof_denies_like_a_timeout():
    _reset()
    result = _run(["--mode", "attended", "--query", QUERY], stdin_text="")
    assert result.returncode == 0, f"attended+EOF should exit 0 cleanly:\n{result.stdout}\n{result.stderr}"
    assert not POST_PATH.exists(), "attended+EOF (no answer) must not write output/post.md"
    assert "DENIED" in result.stdout


def test_unattended_stops_for_approval():
    _reset()
    result = _run(["--mode", "unattended", "--query", QUERY], stdin_text="")
    assert result.returncode == 0, (
        f"unattended must exit 0 (a graceful stop is not an error):\n{result.stdout}\n{result.stderr}"
    )
    assert not POST_PATH.exists(), "unattended must never publish on its own"
    assert PENDING_PATH.exists(), "unattended must write a pending/<action>.json record"
    record = json.loads(PENDING_PATH.read_text())
    assert record["status"] == "PENDING"
    assert record["action"] == "publish_commentary_report"
    assert "STOPPED FOR APPROVAL" in result.stdout


def test_resume_pending_closes_the_loop():
    # Depends on the unattended run above having left a pending record.
    test_unattended_stops_for_approval()
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "pipeline" / "run_pipeline.py"),
            "--resume-pending",
            "publish_commentary_report",
        ],
        cwd=REPO_ROOT,
        input="y\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--resume-pending failed:\n{result.stdout}\n{result.stderr}"
    assert POST_PATH.exists(), "resuming a pending approval with 'y' should publish"
    record = json.loads(PENDING_PATH.read_text())
    assert record["status"] == "APPROVED"
    assert "approved_at" in record


if __name__ == "__main__":
    test_attended_approve_publishes()
    print("OK: attended + y -> published")
    test_attended_deny_does_not_publish()
    print("OK: attended + n -> denied, nothing published, clean exit")
    test_attended_eof_denies_like_a_timeout()
    print("OK: attended + EOF (no answer) -> denied like a timeout, clean exit")
    test_unattended_stops_for_approval()
    print("OK: unattended -> STOPPED FOR APPROVAL, pending record written, exit 0")
    test_resume_pending_closes_the_loop()
    print("OK: --resume-pending + y -> published, pending record flipped to APPROVED")
    print("OK: Chapter 7 Lab approval gate verified on both the stop and the approved-continue paths.")
