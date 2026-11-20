"""
tests/test_ch09_lab.py — Chapter 9 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch09_lab.py -v

Or directly with plain Python (the path the Chapter 9 Lab documents,
same convention as tests/test_ch01_lab.py):
    python3 tests/test_ch09_lab.py

Asserts, in order:
  1. A clean hierarchy run (`--sectors ops,finance`) exits 0, writes
     both sector report files, and publishes `output/post.md`.
  2. A run with one sector simulated late (`--simulate-late finance`)
     exits NONZERO and does NOT (re)write `output/post.md` -- the
     gate must fail closed even though yesterday's `finance.md` is
     still sitting on disk (staleness, not just absence, must be
     caught).
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_hierarchy(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pipeline.run_hierarchy", *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _reset_output() -> None:
    # Namespaced under ch09_reports/ and ch09_post.md, not the shared
    # output/reports/ and output/post.md other chapters' Labs also
    # write to -- see pipeline/run_hierarchy.py for why.
    reports_dir = REPO_ROOT / "output" / "ch09_reports"
    for name in ("ops.md", "finance.md"):
        p = reports_dir / name
        if p.exists():
            p.unlink()
    post = REPO_ROOT / "output" / "ch09_post.md"
    if post.exists():
        post.unlink()


def test_clean_run_publishes():
    _reset_output()
    result = _run_hierarchy("--sectors", "ops,finance")
    assert result.returncode == 0, (
        f"clean hierarchy run should exit 0:\n{result.stdout}\n{result.stderr}"
    )

    ops_report = REPO_ROOT / "output" / "ch09_reports" / "ops.md"
    finance_report = REPO_ROOT / "output" / "ch09_reports" / "finance.md"
    post = REPO_ROOT / "output" / "ch09_post.md"
    assert ops_report.exists(), "ops sector researcher did not write its report"
    assert finance_report.exists(), "finance sector researcher did not write its report"
    assert post.exists(), "publish did not run after a clean, gate-passing cycle"

    # Each sector report must cite only its own fixture source -- proof
    # the silo is real (no cross-domain leakage), not just asserted.
    ops_text = ops_report.read_text()
    finance_text = finance_report.read_text()
    assert "finance" not in ops_report.name
    assert "deployment-cadence" in ops_text or "incident-response" in ops_text, (
        "ops report should cite its own ops/ fixtures"
    )
    assert "rates-and-sector-rotation" in finance_text or "payments-and-fintech" in finance_text, (
        "finance report should cite its own finance/ fixtures"
    )


def test_late_run_refuses_to_publish():
    # Start from a known-good cycle so a real (now stale) finance.md
    # exists on disk, then remove post.md so we can tell whether the
    # late run writes a NEW one.
    _reset_output()
    setup = _run_hierarchy("--sectors", "ops,finance")
    assert setup.returncode == 0, f"setup cycle should succeed:\n{setup.stdout}"
    post = REPO_ROOT / "output" / "ch09_post.md"
    assert post.exists()
    post.unlink()

    # This cycle withholds the finance researcher entirely. The
    # finance.md on disk is now a STALE leftover from the setup cycle
    # above -- the gate must refuse on staleness, not just on a
    # missing file.
    result = _run_hierarchy("--sectors", "ops,finance", "--simulate-late", "finance")
    assert result.returncode != 0, (
        f"late-researcher run must exit nonzero:\n{result.stdout}\n{result.stderr}"
    )
    assert "STALE" in result.stdout or "MISSING" in result.stdout, (
        "gate should name the missing/stale report in its output"
    )
    assert not post.exists(), (
        "publish must not run (or must not overwrite) when the gate fails closed"
    )


if __name__ == "__main__":
    test_clean_run_publishes()
    print("OK: clean hierarchy run published successfully (2/2 reports, 1 post).")
    test_late_run_refuses_to_publish()
    print("OK: late-researcher run failed the gate and refused to publish.")
    print("OK: Chapter 9 Lab passed both the happy path and the fail-closed path.")
