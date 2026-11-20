#!/usr/bin/env python3
"""
pipeline/publish/publish.py — Chapter 1 Lab: publish (dry-run only)

PRODUCTION NOTE: freemarketresearcher.com's real publishers
(MarketSectorPipeline, AnalysisPipeline, BriefPipeline) export
WP_SSH_HOST / WP_SSH_USER / WP_SSH_KEY_PATH / WP_PATH, then run
`WPPublisher.py`, which scp's the post body to the Bluehost host and
runs `wp post create` / `wp term create` over SSH -- NOT the WordPress
REST API -- with a retry wrapper (up to 7 attempts) for transient
SSH/SCP failures, and `clear_category_posts()` to replace the prior
post set in a category. That mechanism is Chapter 8 material.

This module only ever writes to a local file under `output/`. It never
imports `ssh`/`scp`/`wp-cli` and never makes a network call --
"dry-run" is not a flag you can turn off here, it is the only publish
target this companion repo implements.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402
from pipeline.publish import checkpoint  # noqa: E402


def publish(report_md_path, out_dir, category: str = "Commentary", target: str = "dryrun"):
    """Dry-run publisher. Mirrors the production signature
    `publish(report_md, target="dryrun")` from the Blueprint."""
    if target != "dryrun":
        raise NotImplementedError(
            "Only target='dryrun' is implemented in the companion repo. "
            "Real WordPress publishing over SSH + wp-cli is Chapter 8 material."
        )

    report_md_path = Path(report_md_path)
    report_text = report_md_path.read_text()
    first_nonblank = next((l for l in report_text.splitlines() if l.strip()), "Untitled Report")
    title = first_nonblank.lstrip("#").strip() or "Untitled Report"

    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f'category: "{category}"\n'
        'status: "dryrun"\n'
        f'published_at: "{datetime.now(timezone.utc).isoformat()}"\n'
        f'source_report: "{report_md_path.name}"\n'
        "---\n\n"
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "post.md"
    out_path.write_text(frontmatter + report_text)

    print(f"[publish] DRY-RUN: wrote {out_path} (category={category})")
    print("[publish] production equivalent: scp body + `wp post create`/`wp term create` "
          "over SSH, retried up to 7x (WPPublisher.py, Chapter 8)")
    return out_path


def _publish_side_effect(report_path, out_dir, category, posts_log_path):
    """Chapter 8 Lab: the "it actually went out" half of a publish.

    Mirrors what WPPublisher.publish() really does on the wire: the
    post body gets written/sent FIRST (scp + `wp post create`), and
    only after that call returns success does PublicationManager
    record it in state.json [src: PublicationManager.py:148-156].
    This function is that first half -- it writes a dry-run post file
    under out_dir/posts/ AND appends one line to a mock
    "published_posts.log" representing the mock WordPress side
    actually receiving a new post. It does NOT touch the checkpoint;
    the caller (publish_batch) decides afterward whether to record it.
    """
    report_path = Path(report_path)
    posts_dir = Path(out_dir) / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    report_text = report_path.read_text()
    first_nonblank = next((l for l in report_text.splitlines() if l.strip()), "Untitled Report")
    title = first_nonblank.lstrip("#").strip() or "Untitled Report"

    post_path = posts_dir / f"{report_path.stem}.md"
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f'category: "{category}"\n'
        'status: "dryrun"\n'
        f'published_at: "{datetime.now(timezone.utc).isoformat()}"\n'
        f'source_report: "{report_path.name}"\n'
        "---\n\n"
    )
    post_path.write_text(frontmatter + report_text)

    posts_log_path = Path(posts_log_path)
    with open(posts_log_path, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} PUBLISHED {report_path.name} -> {post_path.name}\n")

    return post_path


def publish_batch(report_paths, state_path, out_dir, category: str = "Commentary",
                   crash_after: Optional[int] = None):
    """Chapter 8 Lab: publish a *list* of reports, checkpointed, the
    way PublicationManager.run_cycle() does [src: PublicationManager.py:
    127-180] -- sorted by filename, skip anything already recorded in
    `published_files`, append + save state after each success.

    `crash_after` simulates a hard process kill (os._exit, no Python
    cleanup, no atexit) after report N's side effect has gone out but
    BEFORE its checkpoint is saved -- the exact race the real
    AnalysisPipeline/BriefPipeline gap and MarketSectorPipeline's
    reset-every-run behavior make possible in production (Chapter 8,
    "What Broke"). This is a designed experiment, not a replay of a
    historical incident; see the chapter's Lab section for why.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    posts_log_path = out_dir / "published_posts.log"

    state = checkpoint.load_state(state_path)
    sorted_reports = sorted(report_paths, key=lambda p: Path(p).name)

    for idx, report_path in enumerate(sorted_reports, start=1):
        basename = Path(report_path).name
        if basename in state["published_files"]:
            print(f"[publish_batch] SKIP {basename} (already in published_files -- checkpoint dedup working)")
            continue

        print(f"[publish_batch] publishing {basename} (report {idx}/{len(sorted_reports)})")
        _publish_side_effect(report_path, out_dir, category, posts_log_path)
        print(f"[publish_batch]   side effect done: {basename} is now in published_posts.log")

        if crash_after is not None and idx == crash_after:
            print(
                f"[publish_batch] SIMULATE_CRASH after report {idx} ({basename}): "
                f"the side effect already landed, but the checkpoint for it was "
                f"never written. os._exit(1) now -- no Python cleanup, no finally "
                f"blocks, exactly like a real `kill -9` or an unattended SSH drop "
                f"mid-cycle."
            )
            sys.stdout.flush()
            import os
            os._exit(1)

        state["published_files"].append(basename)
        checkpoint.save_state(state_path, state)
        print(f"[publish_batch]   checkpoint saved: {basename} now in published_files")

    return state


def publish_hierarchy(report_paths, out_dir, gate_report_paths=None, not_before=None,
                       category: str = "Commentary", target: str = "dryrun",
                       out_filename: str = "post.md"):
    """Chapter 9 Lab: publish a BATCH of independently-produced sector
    reports, but ONLY after the schedule gate passes.

    Mirrors the real Stage 2 -> Stage 3 handoff: `MarketSectorPipeline/
    src/publish_reports.sh` fires 20 minutes after the last sector
    researcher's cron line with no check in between
    [src: 01_notes/production_inventory_freemarketresearcher.md,
    Stage 2/3]. This function is the Lab's deliberate addition of the
    check production does NOT have: it calls
    `pipeline.schedule.gate.check_ready()` first and refuses outright
    (raises, writes nothing) if even one expected report is missing or
    stale, instead of publishing whatever happens to exist. Still only
    ever writes a local file under `output/` -- no SSH, no wp-cli, same
    dry-run-only convention as `publish()` above.

    `gate_report_paths` defaults to `report_paths` themselves; pass it
    separately when the caller wants to gate on a WIDER set of expected
    files than what actually got produced (e.g. a late/withheld
    researcher's report was never written at all, but its *path* must
    still be gated on so the gate can name it as missing).

    `out_filename` defaults to "post.md" (matching `publish()` above),
    but the Chapter 9 Lab passes "ch09_post.md" -- this companion repo
    is worked on by several chapters' Labs concurrently, and a shared
    `output/post.md` was observed, while building this Lab, to be
    overwritten mid-run by another chapter's own test cycle. Namespacing
    the output filename per chapter is this Lab's fix for that, not a
    claim that the real WordPress publish step has (or needs) one.
    """
    from pipeline.schedule.gate import check_ready

    gate_paths = list(gate_report_paths) if gate_report_paths is not None else list(report_paths)
    if not check_ready(gate_paths, not_before=not_before):
        missing_or_stale = [str(p) for p in gate_paths]
        raise RuntimeError(
            "publish refused: the schedule gate did not pass for "
            f"{missing_or_stale}. See the [gate] lines above for which "
            "report(s) were missing or stale, and why. Nothing was published."
        )

    report_paths = [Path(p) for p in report_paths]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_filename

    parts = [
        "---\n",
        'title: "Sector Hierarchy Publish"\n',
        f'category: "{category}"\n',
        f'status: "{target}"\n',
        f'published_at: "{datetime.now(timezone.utc).isoformat()}"\n',
        f"source_reports: {[p.name for p in report_paths]}\n",
        "---\n\n",
    ]
    for p in report_paths:
        parts.append(p.read_text())
        parts.append("\n\n")
    out_path.write_text("".join(parts))

    print(f"[publish] DRY-RUN: wrote {out_path} from {len(report_paths)} report(s) "
          f"(category={category})")
    print("[publish] production equivalent: MarketSectorPipeline/src/publish_reports.sh, "
          "20 minutes after the last sector cron line, with NO gate check of its own "
          "(this function's gate check is this Lab's addition, not a claim about "
          "production code)")
    return out_path


def main():
    ap = argparse.ArgumentParser(
        description="Lab publisher: dry-run single report (Ch1 mode) or "
                     "checkpointed batch publish with crash simulation (Ch8 mode)"
    )
    ap.add_argument("--input", default=None,
                     help="[Ch1 mode] report markdown to publish (default: output/report.md)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--batch-dir", default=None,
                     help="[Ch8 mode] directory of report .md/.txt fixture files to "
                          "publish as a checkpointed batch")
    ap.add_argument("--state-file", default=None,
                     help="[Ch8 mode] path to the checkpoint state.json "
                          "(default: <output_dir>/state.json)")
    ap.add_argument("--crash-after", type=int, default=None,
                     help="[Ch8 mode] simulate a hard process kill after report N's "
                          "side effect went out but before its checkpoint is saved")
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = REPO_ROOT / cfg["publisher"]["output_dir"]
    category = cfg["publisher"].get("default_category", "Commentary")

    if args.batch_dir:
        batch_dir = Path(args.batch_dir)
        report_paths = sorted(batch_dir.glob("*.md")) + sorted(batch_dir.glob("*.txt"))
        state_path = Path(args.state_file) if args.state_file else out_dir / "state.json"
        publish_batch(report_paths, state_path, out_dir, category=category,
                      crash_after=args.crash_after)
        return

    target = cfg["publisher"].get("type", "dryrun")
    input_path = Path(args.input) if args.input else out_dir / "report.md"

    publish(input_path, out_dir, category=category, target=target)


if __name__ == "__main__":
    main()
