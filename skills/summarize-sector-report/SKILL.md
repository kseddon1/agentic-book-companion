---
name: summarize-sector-report
description: Summarize the sector report with a live regime check.
version: 1.0.0
---

# summarize-sector-report

This is the Chapter 4 Lab's reader-written skill: a miniature of Hermes's
real `finance-report` skill (`~/.hermes/skills/finance-report/SKILL.md`),
built against the companion repo's own Chapter 1 fixtures instead of the
real `FinanceResearcher` report and the real `quant-tools` MCP server.
Audit it against the three Contract Integrity pillars before you trust it:

- **Trigger Precision** — "When to Use" below names exact phrases, not a
  vague "summarize things" trigger.
- **Input Strictness** — the Procedure takes two fixed file paths
  (`output/report.md`, `output/market_state.json`), not free-form text.
- **Output Utility** — the output is one Markdown file with a named
  regime field a caller could parse, not an unstructured chat reply.

## When to Use

Call this skill when the user requests:
- "Summarize the latest sector report"
- "What does the report say, and what's the market regime right now?"

## Procedure

1. Read `output/report.md` (written by the Chapter 1 Lab's
   `pipeline.researchers.research` stage) and pull its `## Key Findings`
   bullets.
2. Call the MCP tool-call stand-in for a live regime check:
   `python3 -m pipeline.mcp.market_state_tool --regime-file output/market_state.json`
   — the Lab's stand-in for `mcp__quant_tools__get_regime_identification_tool`
   (`~/Projects/MCP-Server/quant_mcp_server.py:162-172`).
3. Write one short Markdown synthesis to `output/synthesis.md` that cites
   both: the report's Key Findings, and the regime tool's
   `active_regime.name` / `indicators.volatility_level` fields — the same
   two field names the real `finance-report` and `market-intelligence-report`
   skills read off the real tool's JSON.
4. State explicitly whether the two sources align or diverge, the same
   Alignment vs. Divergence check `market-intelligence-report`'s own
   Workflow step 3 performs.

Scripted version of this exact procedure:
`python3 -m pipeline.skills.summarize_sector_report`.

## Pitfalls

- **Missing upstream file.** The MCP stand-in only reads a file the
  Chapter 1 Lab's `pipeline.snapshot.market_state` already wrote. Run the
  Chapter 1 Lab first, or the tool returns `{"error": ...}` instead of a
  regime, and this skill's procedure should stop rather than guess.
- **Single-Signal Bias.** Don't report a regime without the report's
  findings, or the report without the regime — the same pitfall the real
  `finance-report` SKILL.md names explicitly
  (`~/.hermes/skills/finance-report/SKILL.md:54`).
- **Tool-name drift.** This Lab's stand-in function is named
  `get_regime_identification_tool` on purpose, matching the real server's
  current tool name — not the `get_market_regime_tool` name an earlier
  version of the real `finance-report` skill called, which no longer
  exists on the server. Keep the name you call in sync with the name the
  tool actually exposes; this chapter's own "What Broke" section is about
  the cost of not doing that.

## Verification

`output/synthesis.md` exists, contains a line from the report's Key
Findings, and contains the regime tool's `active_regime.name` value.
