"""
tests/test_ch04_lab.py — Chapter 4 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch04_lab.py -v

Or directly with plain Python (no pytest required, same as test_ch01_lab.py):
    python3 tests/test_ch04_lab.py

Asserts:
  1. skills/summarize-sector-report/SKILL.md exists with well-formed
     frontmatter (name, description present; description length <= 60
     chars, the convention this authoring environment's own
     skill-creation tooling enforces -- see
     optional-skills/software-development/hermes-agent-skill-authoring/
     SKILL.md:73 on the Hermes install this book documents).
  2. The MCP stand-in tool (pipeline/mcp/market_state_tool.py) returns
     valid JSON with the expected keys when output/market_state.json
     exists, and a clean {"error": ...} (not a crash) when it doesn't.
  3. Running the skill's Procedure end to end (pipeline/skills/
     summarize_sector_report.py) against the Chapter 1 Lab's own
     fixtures produces output/synthesis.md citing both the report and
     the live regime call.

This test runs its own crawl/research/snapshot stages directly (not
via run_pipeline.py) so it has no dependency on any other chapter's
in-progress companion-repo work.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SKILL_PATH = REPO_ROOT / "skills" / "summarize-sector-report" / "SKILL.md"
MAX_DESCRIPTION_CHARS = 60


def _parse_frontmatter(text: str) -> dict:
    """Minimal YAML-frontmatter reader: just the top-level scalar keys
    between the two '---' fences. Good enough for this repo's own
    skill files; not a general YAML parser (same philosophy as
    pipeline/config.py's hand-rolled fallback)."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md has no '---' frontmatter block"
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def test_skill_file_has_valid_frontmatter():
    assert SKILL_PATH.exists(), f"{SKILL_PATH} does not exist"
    fm = _parse_frontmatter(SKILL_PATH.read_text())
    assert "name" in fm and fm["name"], "SKILL.md frontmatter missing 'name'"
    assert "description" in fm and fm["description"], "SKILL.md frontmatter missing 'description'"
    assert len(fm["description"]) <= MAX_DESCRIPTION_CHARS, (
        f"description is {len(fm['description'])} chars, over the "
        f"{MAX_DESCRIPTION_CHARS}-char convention this repo follows"
    )


def test_mcp_standin_handles_missing_file_cleanly():
    from pipeline.mcp.market_state_tool import get_regime_identification_tool

    result = get_regime_identification_tool("output/__does_not_exist__.json")
    assert "error" in result, "stand-in tool should return {'error': ...}, not raise, on a missing file"


def test_mcp_standin_returns_expected_keys_when_file_exists():
    from pipeline.crawler.crawl import ingest
    from pipeline.snapshot.market_state import publish_snapshot
    from pipeline.mcp.market_state_tool import get_regime_identification_tool

    store_path = REPO_ROOT / "data" / "vector_store.json"
    out_dir = REPO_ROOT / "output"
    ingest(REPO_ROOT / "sample_sources", store_path, clear=True)
    publish_snapshot({"regime": "High-Vol Trending-Down", "risk_state": "Elevated"}, out_dir)

    result = get_regime_identification_tool(out_dir / "market_state.json")
    assert "active_regime" in result and "name" in result["active_regime"]
    assert "indicators" in result and "volatility_level" in result["indicators"]
    assert result["active_regime"]["name"] == "High-Vol Trending-Down"
    assert result["indicators"]["volatility_level"] == "Elevated"
    assert "as_of" in result


def test_skill_procedure_runs_end_to_end():
    from pipeline.crawler.crawl import ingest
    from pipeline.researchers.research import synthesize
    from pipeline.snapshot.market_state import publish_snapshot
    from pipeline.config import load_config

    store_path = REPO_ROOT / "data" / "vector_store.json"
    out_dir = REPO_ROOT / "output"
    cfg = load_config()

    # Chapter 1 Lab stages, run directly (no dependency on run_pipeline.py
    # or another chapter's in-progress telemetry work).
    ingest(REPO_ROOT / "sample_sources", store_path, clear=True)
    report_md, chunks, mode = synthesize(
        "What are the basics of serving an LLM locally?", cfg, store_path
    )
    report_path = out_dir / "report.md"
    report_path.write_text(report_md)
    publish_snapshot({"regime": "Low-Vol Trending-Up", "risk_state": "Normal"}, out_dir)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipeline.skills.summarize_sector_report",
            "--report",
            str(report_path),
            "--regime-file",
            str(out_dir / "market_state.json"),
            "--output",
            str(out_dir / "synthesis.md"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"summarize_sector_report failed:\n{result.stdout}\n{result.stderr}"

    synthesis_path = out_dir / "synthesis.md"
    assert synthesis_path.exists(), "skill procedure did not write output/synthesis.md"
    synthesis = synthesis_path.read_text()
    assert "Low-Vol Trending-Up" in synthesis, "synthesis does not cite the live regime call"
    assert "## From the Report" in synthesis, "synthesis does not cite the report"


if __name__ == "__main__":
    test_skill_file_has_valid_frontmatter()
    print("OK: skills/summarize-sector-report/SKILL.md has valid frontmatter.")
    test_mcp_standin_handles_missing_file_cleanly()
    print("OK: MCP stand-in tool fails clean (JSON error, no crash) on a missing file.")
    test_mcp_standin_returns_expected_keys_when_file_exists()
    print("OK: MCP stand-in tool returns active_regime.name / indicators.volatility_level.")
    test_skill_procedure_runs_end_to_end()
    print("OK: Chapter 4 Lab skill procedure ran end to end and produced output/synthesis.md.")
