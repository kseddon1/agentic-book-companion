#!/usr/bin/env python3
"""
pipeline/mcp/market_state_tool.py — Chapter 4 Lab: MCP tool-call stand-in

PRODUCTION NOTE: the real tool this stands in for is
`get_regime_identification_tool(symbols: List[str])`, one of four
in-scope market-intelligence tools exposed by `~/Projects/MCP-Server/
quant_mcp_server.py` over stdio and reached from Hermes as
`mcp__quant_tools__get_regime_identification_tool` (GOAL.md Stack
Journey row 4; `~/Projects/MCP-Server/quant_mcp_server.py:162-172`).
Hermes's own `finance-report` and `market-intelligence-report` skills
call that tool and read exactly two fields back out of its per-symbol
JSON: `active_regime.name` and `indicators.volatility_level`
(`~/.hermes/skills/finance-report/SKILL.md:36-37`;
`~/.hermes/skills/market-intelligence-report/SKILL.md:10,14`). Those
two field names are deliberately real, copied from the corrected
skill text, not invented for this Lab.

This stand-in does NOT call QuantModels, does NOT need the `mcp`
Python SDK, and does NOT make a network call. It reads the Chapter 1
Lab's own `output/market_state.json` (written by
`pipeline/snapshot/market_state.py`) and reshapes it into the same
two-field JSON contract the real tool returns, so a reader with no
QuantModels install, no GPU, and no live market-data feed can still
see a skill call something that looks and behaves like a live MCP
tool call. Matches GOAL.md's Chapter-4-Lab guidance: "a plain function
call with the same JSON contract keeps the Lab runnable with no GPU,
no API key, and no extra dependency" (GOAL.md:230, citing the Chapter
1 Lab's hosted->local->mock fallback precedent).

Connect to the real server via stdio:
  python quant_mcp_server.py
Run this stand-in directly, no server process required:
  python3 -m pipeline.mcp.market_state_tool --regime-file output/market_state.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


def get_regime_identification_tool(regime_file) -> dict:
    """Stand-in for the production MCP tool of the same name.

    Real signature: get_regime_identification_tool(symbols: List[str]) -> str (JSON).
    This stand-in takes a file path instead of a symbol list (there is no
    live market-data feed in this Lab) but returns the same two fields
    downstream skill code actually reads: active_regime.name and
    indicators.volatility_level. Returns {"error": ...} -- matching the
    real server's "fail loud, return JSON" convention
    (snippets/codetheairwaves-post-mcp-server-quant-tools.md:87) -- if the
    Chapter 1 Lab's snapshot stage hasn't run yet.
    """
    path = Path(regime_file)
    if not path.exists():
        return {
            "error": (
                f"{path} not found. Run the Chapter 1 Lab's snapshot stage first: "
                "python3 -m pipeline.snapshot.market_state --regime \"...\" "
                "--output output/market_state.json"
            )
        }
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {"error": f"{path} is not valid JSON: {exc}"}

    regime_name = data.get("regime", "Unknown")
    risk_state = data.get("risk_state", "Unknown")
    as_of = data.get("as_of", datetime.now(timezone.utc).isoformat())

    return {
        "tool": "get_regime_identification_tool (Chapter 4 Lab stand-in)",
        "symbols": ["LAB"],
        "active_regime": {"name": regime_name},
        "indicators": {"volatility_level": risk_state},
        "as_of": as_of,
        "source_file": str(path),
    }


def main():
    ap = argparse.ArgumentParser(
        description="Ch4 Lab: MCP tool-call stand-in for get_regime_identification_tool"
    )
    ap.add_argument("--regime-file", default="output/market_state.json")
    args = ap.parse_args()
    result = get_regime_identification_tool(args.regime_file)
    print(json.dumps(result, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
