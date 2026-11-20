#!/usr/bin/env python3
"""
pipeline/run_pipeline.py — Chapter 1 Lab: one command, crawl -> research ->
publish -> snapshot. Chapter 7 Lab: the publish stage is now gated on a
human-on-the-loop approval before anything is written.

Chains every stage of the companion repo's simplified pipeline in one
process and prints progress at each stage. This is the single command
the Chapter 1 Lab runs end to end.

Stage mapping to the real freemarketresearcher.com production system
(see 01_notes/production_inventory_freemarketresearcher.md in the main
AgenticBook project for the ground truth this mirrors):

  crawl    -> RagSystem/crawler/{discovery,web,ingestor,config}.py, on
              cron (finance 05:00/07:00/11:55/15:30/16:55, ag 19:00,
              tech 23:00 weekdays) -> Qdrant collection `researcher_docs`
  research -> RagSystem/researchers/*.py, chained LLM calls (query
              transformation -> retrieval -> reranking -> synthesis) ->
              reports land in ~/.researcher_reports/
  publish  -> MarketSectorPipeline / AnalysisPipeline / BriefPipeline ->
              WPPublisher.py (scp + wp-cli over SSH, retried up to 7x)
  snapshot -> QuantModels/publish_market_state.sh -> market_state.json,
              uploaded to wp-content/uploads/, read by functions.php

Two things the real system has that this scaffold does not:
  - A notification stage (Stage 5: emails on cron) -- added in Chapter 6
    as an OPT-IN step (`--notify`); off by default so Chapters 1-5's
    documented four-stage behavior is unchanged. See
    pipeline/notify/notify.py and 04_rewrite/core/ch06.md in the main
    AgenticBook project for the Mission Brief this was built from.
  - Any SSH, wp-cli, or network call at all -- every stage below only
    reads sample_sources/ and writes to ./data/ and ./output/.

CHAPTER 7 — the publish stage is gated: --mode {attended,unattended}.
  attended   (default) -- simulates a human at a terminal. Prompts
                "Publish this report to <category>? [y/N]" before
                calling publish(). "y" writes output/post.md; "n"
                (or EOF, simulating a timeout with nobody there to
                answer) writes nothing and the run still exits 0 --
                a denial is not an error.
  unattended -- simulates a cron job or a webhook-triggered run: no
                TTY, nobody watching. It can never grant itself the
                approval the gate requires, so instead of calling
                publish() it writes pending/<action>.json (a PENDING
                record), prints "STOPPED FOR APPROVAL", and exits 0 --
                a graceful stop, never a crash, never a silent skip.
                This mirrors approvals.cron_mode / unattended_mode:
                deny in the real Hermes config -- see
                pipeline/approval/gate.py for the full citation.
  --resume-pending <action> resolves an existing pending record: it
  re-displays what was requested and prompts a live human for a
  yes/no, closing the loop the unattended run opened. Skips crawl and
  research entirely -- it is pure approval-resolution, not a re-run.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.approval import gate  # noqa: E402
from pipeline.config import load_config  # noqa: E402
from pipeline.crawler.crawl import ingest  # noqa: E402
from pipeline.notify.notify import notify  # noqa: E402
from pipeline.publish.publish import publish  # noqa: E402
from pipeline.researchers.research import synthesize  # noqa: E402
from pipeline.snapshot.market_state import publish_snapshot  # noqa: E402
from pipeline import telemetry  # noqa: E402

# Chapter 5: the real production researchers write a JSONL event feed on
# every cron-triggered run (RagSystem/adapter/dashboard.py, read by
# ResearcherDashboard -- Chapter 10's subject). This name is this repo's
# equivalent of status_name = "RagSystem_finance" (RagSystem/researchers/
# finance.py:207): fixed, so the Ch5 Lab always finds the same file.
TELEMETRY_RUN_NAME = "companion-pipeline"

# Chapter 7: the one gated action class in this Lab. A richer pipeline
# would have one of these per action that needs a human "yes"; this
# repo has exactly one (publishing the report), so one fixed name is
# enough to find the pending record back again.
PUBLISH_ACTION = "publish_commentary_report"


def _banner(text: str):
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def _prompt_yes_no(question: str) -> bool:
    """input() wrapper that treats EOF (no TTY, empty piped stdin, a
    prompt nobody answered) the same as an explicit "no" -- fail
    closed, not an exception that crashes the run."""
    try:
        answer = input(question).strip().lower()
    except EOFError:
        answer = ""
    return answer == "y"


def resume_pending(action: str, pending_dir: Path) -> int:
    """Resolve one existing pending approval record without re-running
    crawl/research. Returns a process exit code."""
    token_path = pending_dir / f"{action}.json"
    if not token_path.exists():
        print(f"[approval] no pending record found for action={action!r} at {token_path}")
        return 1

    record = json.loads(token_path.read_text())
    print(f"[approval] PENDING record found: action={record.get('action')}")
    print(f"           requested_at: {record.get('requested_at')}")
    print(f"           reason: {record.get('reason')}")
    print(f"           report: {record.get('report_path')}  category: {record.get('category')}")

    if record.get("status") != "PENDING":
        print(f"[approval] record is already status={record.get('status')!r}; nothing to resolve.")
        return 0

    if _prompt_yes_no("Approve this pending action now? [y/N] "):
        gate.approve_pending(token_path)
        out_dir = Path(record["out_dir"])
        report_path = Path(record["report_path"])
        publish(report_path, out_dir, category=record.get("category", "Commentary"), target="dryrun")
        print(f"[approval] APPROVED -- published. {token_path} now shows status=APPROVED (kept as the audit trail).")
        return 0

    gate.deny_pending(token_path)
    print(f"[approval] DENIED by human -- nothing published. {token_path} now shows status=DENIED.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Ch1 Lab: run the whole pipeline end to end")
    ap.add_argument("--query", default="What are the basics of serving an LLM locally?")
    ap.add_argument("--regime", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument(
        "--notify",
        action="store_true",
        help="Chapter 6: also run Stage 5 (dry-run console notification). "
             "Off by default so Chapters 1-5's four-stage pipeline is unchanged.",
    )
    ap.add_argument(
        "--mode",
        choices=["attended", "unattended"],
        default=None,
        help="Chapter 7: attended prompts a human before publishing; "
             "unattended (simulating cron/webhook, no TTY) can never "
             "self-approve and stops for approval instead. Omit this "
             "flag entirely to keep Chapters 1-6's original behavior "
             "(publish runs immediately, no gate, no prompt) -- the "
             "approval gate is opt-in so the locked Chapter 1 Lab "
             "contract (`run_pipeline.py --query ...` with no flags) "
             "is unchanged.",
    )
    ap.add_argument(
        "--resume-pending",
        metavar="ACTION",
        default=None,
        help="Chapter 7: resolve an existing pending/<ACTION>.json record "
             "(prompts a human yes/no) instead of running the pipeline. "
             f"Default action name: {PUBLISH_ACTION}",
    )
    args = ap.parse_args()

    pending_dir = REPO_ROOT / "pending"

    if args.resume_pending is not None:
        action = args.resume_pending
        sys.exit(resume_pending(action, pending_dir))

    cfg = load_config(args.config)
    store_path = REPO_ROOT / cfg["vector_store"]["path"]
    out_dir = REPO_ROOT / cfg["publisher"]["output_dir"]

    telemetry.start_run(TELEMETRY_RUN_NAME)
    ok = True
    error = None
    try:
        _banner("STAGE 1/4: crawl -> chunk -> embed -> upsert")
        with telemetry.stage("crawl"):
            source_dir = cfg["crawler"]["source_dir"]
            chunk_size_tokens = cfg["crawler"].get("chunk_size", 512)
            chunk_size_words = max(20, int(chunk_size_tokens / 1.3))
            n_chunks = ingest(source_dir, store_path, chunk_size_words=chunk_size_words, clear=True)

        _banner("STAGE 2/4: research (retrieve + synthesize)")
        with telemetry.stage("research"):
            report_md, chunks, mode = synthesize(args.query, cfg, store_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            report_path = out_dir / "report.md"
            report_path.write_text(report_md)
            print(f"[run_pipeline] research mode={mode}, {len(chunks)} chunks used -> {report_path}")

        gated = args.mode is not None
        _banner(
            "STAGE 3/4: publish (gated on human approval -- Chapter 7)"
            if gated
            else "STAGE 3/4: publish (dry-run)"
        )
        with telemetry.stage("publish"):
            category = cfg["publisher"].get("default_category", "Commentary")
            target = cfg["publisher"].get("type", "dryrun")
            attended = args.mode == "attended"

            if not gated:
                # No --mode given: Chapters 1-6's original, ungated behavior.
                # The approval gate below is opt-in, not a silent change to
                # the already-locked Chapter 1 Lab contract.
                publish(report_path, out_dir, category=category, target=target)
            elif gate.requires_approval(attended):
                if attended:
                    print(f"[approval] action={PUBLISH_ACTION!r} requires a human answer (mode=attended).")
                    if _prompt_yes_no(f"Publish this report to {category}? [y/N] "):
                        publish(report_path, out_dir, category=category, target=target)
                    else:
                        print(
                            "[approval] DENIED by human -- nothing published. "
                            f"{out_dir / 'post.md'} was not written/overwritten."
                        )
                else:
                    print(
                        f"[approval] action={PUBLISH_ACTION!r} requires a human answer, but this "
                        "is an unattended run (mode=unattended) -- simulates a cron/webhook "
                        "trigger with no TTY and no human watching."
                    )
                    token_path = pending_dir / f"{PUBLISH_ACTION}.json"
                    gate.request_approval(
                        PUBLISH_ACTION,
                        token_path,
                        report_path=str(report_path),
                        out_dir=str(out_dir),
                        category=category,
                    )
                    print(
                        f"[approval] STOPPED FOR APPROVAL -- wrote {token_path}. "
                        "Exiting 0: a graceful stop waiting on a human is not a crash "
                        "and not a silent skip. Resolve it with: "
                        f"python3 pipeline/run_pipeline.py --resume-pending {PUBLISH_ACTION}"
                    )
            else:
                publish(report_path, out_dir, category=category, target=target)

        _banner("STAGE 4/4: snapshot (local JSON stand-in for Market State Snapshot)")
        with telemetry.stage("snapshot"):
            regime = args.regime or cfg["snapshot"].get("default_regime", "Low-Vol Trending-Up")
            data = {"regime": regime, "risk_state": "Normal", "note": "Chapter 1 Lab run_pipeline"}
            publish_snapshot(data, out_dir)

        if args.notify:
            _banner("STAGE 5/5: notify (dry-run, Chapter 6)")
            with telemetry.stage("notify"):
                notify(report_path, out_dir, channel="console")
    except Exception as e:
        ok = False
        error = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        telemetry.end_run(ok=ok, error=error)

    print()
    print(f"Pipeline complete. Vector store has {n_chunks} chunks at {store_path}")
    print(f"Research mode: {mode}")
    print(f"See {out_dir}/ for report.md, post.md (if approved), market_state.json")
    print(f"Telemetry: {telemetry.status_dir() / (TELEMETRY_RUN_NAME + '.jsonl')}")


if __name__ == "__main__":
    main()
