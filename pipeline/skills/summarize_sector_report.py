#!/usr/bin/env python3
"""
pipeline/skills/summarize_sector_report.py — Chapter 4 Lab: executes the
Procedure section of skills/summarize-sector-report/SKILL.md end to end.

PRODUCTION NOTE: this mirrors the two-source shape of Hermes's real
`finance-report` skill in miniature -- read an existing report, then
call an MCP tool for a live check, then synthesize one answer that
cites both and flags alignment vs. divergence
(~/.hermes/skills/finance-report/SKILL.md, Steps 1-4). In production
that skill is loaded by Hermes and run by an LLM turn; this script is
the Lab's deterministic stand-in so the Lab is runnable, scriptable,
and testable with no model call at all, the same zero-cost precedent
set by this repo's Chapter 1 mock path.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.mcp.market_state_tool import get_regime_identification_tool  # noqa: E402


def _extract_key_findings(report_text: str, limit: int = 3):
    """Pull bullet lines out of report.md's 'Key Findings' section --
    the same section pipeline/researchers/research.py's synthesis prompt
    asks the model to always produce (pipeline/config.example.yaml,
    researcher.synthesis_prompt).

    Matched heading-level-agnostically ('# Key Findings', '## Key
    Findings', ...): a real run against the local Ollama path produced
    single-'#' headings even though the prompt template shows '##'
    examples -- models don't always match a template's exact heading
    depth, so a strict '## ' match silently finds nothing. Caught
    running this Lab for real, not assumed."""
    findings = []
    in_section = False
    for line in report_text.splitlines():
        stripped = line.strip()
        heading = stripped.lstrip("#").strip()
        if stripped.startswith("#") and heading.lower() == "key findings":
            in_section = True
            continue
        if in_section and stripped.startswith("#"):
            break
        if in_section and stripped.startswith(("-", "*")):
            findings.append(stripped)
    return findings[:limit]


def run(report_path, regime_file, output_path) -> Path:
    report_path = Path(report_path)
    if not report_path.exists():
        raise SystemExit(
            f"{report_path} not found. Run the Chapter 1 Lab's research stage first: "
            'python3 -m pipeline.researchers.research --query "..."'
        )
    report_text = report_path.read_text()

    regime = get_regime_identification_tool(regime_file)
    if "error" in regime:
        raise SystemExit(f"MCP stand-in tool error: {regime['error']}")

    regime_name = regime["active_regime"]["name"]
    vol_level = regime["indicators"]["volatility_level"]
    findings = _extract_key_findings(report_text)

    lines = [
        "# Sector Report Synthesis (Chapter 4 Lab)",
        "",
        f"**Live regime (MCP stand-in tool call):** {regime_name} "
        f"(volatility_level={vol_level}, as_of={regime.get('as_of')})",
        "",
        "## From the Report",
    ]
    if findings:
        lines.extend(findings)
    else:
        lines.append("(no '## Key Findings' section found in the report)")
    lines += [
        "",
        "## Alignment / Divergence Check",
        (
            f"Quantitative signal: **{regime_name}**. Compare it against the qualitative "
            "findings above -- the same alignment-vs-divergence check the real "
            "`finance-report` and `market-intelligence-report` skills perform in "
            "production, using the real field names `active_regime.name` and "
            "`indicators.volatility_level` this stand-in tool also returns "
            "(~/.hermes/skills/finance-report/SKILL.md:36-37, 48-50)."
        ),
    ]

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"[summarize-sector-report] wrote {out_path}")
    print(f"[summarize-sector-report] regime={regime_name} volatility_level={vol_level}")
    return out_path


def main():
    ap = argparse.ArgumentParser(
        description="Ch4 Lab: run the summarize-sector-report skill procedure end to end"
    )
    ap.add_argument("--report", default="output/report.md")
    ap.add_argument("--regime-file", default="output/market_state.json")
    ap.add_argument("--output", default="output/synthesis.md")
    args = ap.parse_args()
    run(args.report, args.regime_file, args.output)


if __name__ == "__main__":
    main()
