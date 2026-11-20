# agentic-book-companion

Companion repo for *The Agentic Workflow — A Practitioner's Guide*.

A sanitized, minimal, runnable version of the research pipeline the book
builds chapter by chapter (crawl -> chunk -> embed -> upsert -> research
-> publish -> snapshot). It mirrors the real freemarketresearcher.com
researchers the book documents, with secrets, real hosts, and
production-only pieces removed.

## Status: Chapter 1 and Chapter 4 Labs implemented and runnable

The Chapter 1 scaffold is built and has been run end to end on this
machine (see `04_rewrite/labs/ch01/` in the main `AgenticBook` project
for the exact commands and captured output). Later chapters add real
Qdrant, real WordPress publishing, cron scheduling, and more — this
repo starts intentionally simple.

- `sample_sources/` — four small fixture Markdown files about a
  fictional "Lantern Notes" local-LLM-serving project. Not real
  freemarketresearcher.com content; just enough text to crawl, chunk,
  and retrieve from without any live network call.
- `pipeline/crawler/crawl.py` — crawls `sample_sources/`, chunks by
  paragraph, computes a crude hash-based pseudo-embedding, and upserts
  into a local JSON file (`data/vector_store.json`) that stands in for
  a real vector database.
- `pipeline/researchers/research.py` — retrieves the top-N chunks for a
  query by cosine similarity and synthesizes a short Markdown report
  with an LLM call. Three model paths, tried in order:
  1. **Hosted** — set `OPENROUTER_API_KEY` or `OPENAI_API_KEY` in the
     environment. No SDK needed; calls an OpenAI-compatible
     `/chat/completions` endpoint with the Python stdlib.
  2. **Local** — if no hosted key is set, and an Ollama server is
     already reachable at `http://localhost:11434`, uses it. No GPU is
     required; this is purely "is the port open".
  3. **Mock/dry-run** — if neither is available, prints exactly what
     request it *would* have sent and writes a clearly labeled mock
     report instead of crashing. This is the zero-cost, zero-setup
     path a reader with no API key and no local model can still run.
- `pipeline/publish/publish.py` — dry-run publisher only. Writes a
  Markdown post with frontmatter to `output/post.md`. Never touches
  SSH, `wp-cli`, or a live site — that's Chapter 8 material.
- `pipeline/snapshot/market_state.py` — writes `output/market_state.json`,
  a local stand-in for the real Market State Snapshot (which uploads
  over SSH to `wp-content/uploads/` in production).
- `pipeline/run_pipeline.py` — chains all four stages in one command
  and prints progress at each one.
- `pipeline/config.example.yaml` — the single config file every stage
  reads. Copy it to `pipeline/config.yaml` and edit as needed; it is
  gitignored so your API keys and local edits never get committed.
- `tests/test_ch01_lab.py` — runs the full pipeline and asserts the
  vector store, report, dry-run post, and snapshot files all exist.
  Works with `pytest` if installed, or directly via `python3
  tests/test_ch01_lab.py` if not.

### What's simplified here vs. production

| This repo | freemarketresearcher.com production |
|---|---|
| JSON file as a vector store, hash-based pseudo-embedding | Real Qdrant collection `researcher_docs`, real `nomic-embed-text:v1.5` embeddings via Ollama |
| Paragraph chunking | `RagSystem/core/semantic_chunking.py` |
| One retrieval + one synthesis call | Chained LLM calls: query transformation -> retrieval -> reranking -> synthesis (`RagSystem/core/`, `RagSystem/researchers/`) |
| Dry-run publisher, writes a local file | `WPPublisher.py`: scp + `wp post create`/`wp term create` over SSH, retried up to 7x |
| Local JSON snapshot file | `market_state_publisher.py` uploads to `wp-content/uploads/` over SSH; `functions.php` reads it, max age 5 days |
| Run manually, once | System cron on a fixed schedule (see `production_inventory_freemarketresearcher.md` in the book project) |

## Running the Chapter 1 Lab

```bash
cp pipeline/config.example.yaml pipeline/config.yaml   # edit API keys if using the hosted path

python3 -m pipeline.crawler.crawl --source sample_sources --collection researcher_docs
python3 -m pipeline.researchers.research --query "Latest AI agent developments"
python3 -m pipeline.publish.publish --input output/report.md
python3 -m pipeline.snapshot.market_state --regime "Low-Vol Trending-Up" --output output/market_state.json

ls output/                      # report.md, post.md, market_state.json
python3 tests/test_ch01_lab.py  # or: pytest tests/test_ch01_lab.py -v
```

Or run every stage in one command:

```bash
python3 pipeline/run_pipeline.py --query "What are the basics of serving an LLM locally?"
```

No third-party Python packages are required. `pipeline/config.py`
loads `config.yaml`/`config.example.yaml` with PyYAML if it's
installed, or with a small built-in YAML-subset parser if it isn't.

## Chapter 4 Lab: a skill + an MCP tool-call stand-in

Builds on Chapter 1's output. Adds:

- `skills/summarize-sector-report/SKILL.md` — a real `SKILL.md`,
  modeled on Hermes's real `finance-report` skill shape: retrieve the
  Chapter 1 Lab's `output/report.md`, then call a market-state tool
  for an ad-hoc check. Read it and identify its three Contract
  Integrity pillars (Trigger Precision, Input Strictness, Output
  Utility) before running anything — that's the audit exercise.
- `pipeline/mcp/market_state_tool.py` — a plain-Python,
  JSON-in/JSON-out stand-in for the real `quant-tools` MCP server's
  `get_regime_identification_tool`. No `mcp` SDK, no API key, no GPU:
  it reads `output/market_state.json` (written by Chapter 1's
  `pipeline/snapshot/market_state.py`) and returns the same two
  fields the real `finance-report` and `market-intelligence-report`
  skills read off the real tool — `active_regime.name` and
  `indicators.volatility_level`.
- `pipeline/skills/summarize_sector_report.py` — a scripted,
  deterministic run of the skill's Procedure end to end: reads
  `output/report.md`, calls the MCP stand-in tool once, writes
  `output/synthesis.md` citing both.
- `tests/test_ch04_lab.py` — asserts the skill file's frontmatter is
  well-formed (`name`, `description` present, description ≤ 60 chars),
  the MCP stand-in returns valid JSON with the expected keys (and a
  clean `{"error": ...}` when its input file is missing), and the
  skill's procedure produces a synthesis citing both sources.

```bash
# Prerequisite: run the Chapter 1 Lab first (or just the crawl/research/
# snapshot stages) so output/report.md and output/market_state.json exist.
python3 -m pipeline.crawler.crawl --source sample_sources --collection researcher_docs
python3 -m pipeline.researchers.research --query "What are the basics of serving an LLM locally?"
python3 -m pipeline.snapshot.market_state --regime "High-Vol Trending-Down" --output output/market_state.json

# Call the MCP tool-call stand-in directly.
python3 -m pipeline.mcp.market_state_tool --regime-file output/market_state.json

# Run the skill's procedure end to end.
python3 -m pipeline.skills.summarize_sector_report
cat output/synthesis.md

# Verify.
python3 tests/test_ch04_lab.py
```

See `04_rewrite/labs/ch04/commands.sh` and `run_output.txt` in the main
`AgenticBook` project for the exact commands and captured output this
was verified against.

## Chapter 9 Lab: a 2-researcher hierarchy with an enforced-ordering gate

Builds on Chapter 1's hosted/local/mock research path. Adds:

- `sample_sources/finance/` and `sample_sources/ops/` — two small,
  non-overlapping fixture domains (2 docs each), standing in for the
  real `FinanceResearcher` vs. `AgResearcher-1`/`TechResearcher`
  corpus partition.
- `pipeline/researchers/sector_research.py` — `run_sector(sector_key,
  cfg, report_dir=...)`: two named sector keys (`ops`, `finance`),
  each crawling and querying its *own* fixture domain into its *own*
  JSON vector store (`data/vector_store_<key>.json`), each writing its
  own report under `output/ch09_reports/<key>.md`. Neither reads the
  other's store, report, or existence.
- `pipeline/schedule/gate.py` — `check_ready(expected_report_paths,
  not_before=None)`: the one piece of "coordination" code in this
  Lab. Fails closed on a missing report, and (via `not_before`) on a
  *stale* one too — a leftover file from a prior cycle doesn't count
  as ready just because it exists at the right path.
- `pipeline/publish/publish.py` — new `publish_hierarchy()` function:
  publishes a batch of reports to `output/ch09_post.md`, but only
  after the gate passes; refuses with a clear error and writes
  nothing otherwise.
- `pipeline/run_hierarchy.py` — chains: run each sector researcher
  independently → gate check → publish only if the gate passed.
  `--simulate-late <sector>` withholds one researcher's run entirely,
  to exercise the fail-closed path on demand.
- `tests/test_ch09_lab.py` — asserts a clean run publishes both
  reports and a post, and a late-researcher run exits nonzero and
  writes no post, even when a stale report from an earlier cycle is
  still on disk.

Artifacts live under `output/ch09_reports/` and `output/ch09_post.md`
(not the plain `output/reports/`/`output/post.md` other chapters'
Labs use) — this repo is worked on by several chapters concurrently,
and a shared `output/` path was observed, while building this Lab, to
be overwritten mid-run by another chapter's own test cycle. See
`04_rewrite/core/ch09.md`'s "What Broke" in the main `AgenticBook`
project for the full incident.

```bash
# Clean run: two independent researchers, a passing gate, a publish.
python3 -m pipeline.run_hierarchy --sectors ops,finance

# Deliberate failure: withhold one researcher this cycle.
python3 -m pipeline.run_hierarchy --sectors ops,finance --simulate-late finance

# Inspect: each report should cite only its own fixture source.
cat output/ch09_reports/ops.md
cat output/ch09_reports/finance.md

# Verify.
python3 tests/test_ch09_lab.py
```

See `04_rewrite/labs/ch09/run_output.txt` in the main `AgenticBook`
project for the exact commands and captured output this was verified
against.

## License

MIT — see `LICENSE`.
