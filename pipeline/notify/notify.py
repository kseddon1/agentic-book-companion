#!/usr/bin/env python3
"""
pipeline/notify/notify.py — Chapter 6 Lab: notify (dry-run only)

This module implements the gap the companion repo's own README and
pipeline/run_pipeline.py docstring flag explicitly: "A notification
stage (Stage 5: emails on cron) -- out of scope here." It was built
from a hand-written Mission Brief (see
04_rewrite/labs/ch06/mission_brief.md in the main AgenticBook project),
the Chapter 6 analog of writing a Mission Brief for a Claude Code child
or a Hermes `delegate_task` subagent: a spec precise enough that an
implementer with zero shared context could build exactly this module.

PRODUCTION NOTE: freemarketresearcher.com's real notification stage is
scripts/send_finance_report_email.py et al., sent over SMTP / the
Himalaya email gateway on cron after a publish pipeline run (see
01_notes/production_inventory_freemarketresearcher.md in the main
AgenticBook project). That mechanism is out of scope for this
companion repo, same convention as pipeline/publish/publish.py's SSH
note: this module only ever writes a local file under output/. It
never imports smtplib, requests, or any networking module, and never
makes a network call. "channel" is a label only; "console" is the
only implemented value, exactly like publish.py's `target` guard.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402


def notify(report_path: Path, out_dir: Path, channel: str = "console") -> Path:
    """Read a synthesized report and write a plain-text notification
    summary. Mirrors the production signature
    `notify(report_path, out_dir, channel="console")` from the
    Mission Brief.

    Raises NotImplementedError for any channel other than "console" --
    this stays a dry-run, the same guard pipeline/publish/publish.py
    uses for its `target` argument.
    """
    if channel != "console":
        raise NotImplementedError(
            "Only channel='console' is implemented in the companion repo. "
            "Real email/iMessage notification delivery is out of scope here "
            "(see scripts/send_finance_report_email.py in production)."
        )

    report_path = Path(report_path)
    report_text = report_path.read_text()
    lines = report_text.splitlines()
    first_nonblank = next((l for l in lines if l.strip()), "Untitled Report")
    title = first_nonblank.lstrip("#").strip() or "Untitled Report"

    # A short preview: the first few non-blank lines after the title,
    # skipping any line that is itself just a markdown heading marker.
    preview_lines = []
    seen_title = False
    for line in lines:
        if not seen_title and line.strip() == first_nonblank.strip():
            seen_title = True
            continue
        if not seen_title:
            continue
        if line.strip():
            preview_lines.append(line.strip())
        if len(preview_lines) >= 3:
            break
    preview = "\n".join(preview_lines) if preview_lines else "(no preview available)"

    generated_at = datetime.now(timezone.utc).isoformat()

    body = (
        "=== Notification (console, dry-run) ===\n"
        f"Title: {title}\n"
        f"Source report: {report_path}\n"
        f"Generated at: {generated_at}\n"
        "\n"
        "Preview:\n"
        f"{preview}\n"
        "\n"
        "--- production equivalent ---\n"
        "scripts/send_finance_report_email.py et al. send this over SMTP /\n"
        "the Himalaya email gateway on cron after a publish pipeline run.\n"
        "See 01_notes/production_inventory_freemarketresearcher.md.\n"
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "notification.txt"
    out_path.write_text(body)

    print(f"[notify] DRY-RUN: wrote {out_path} (channel={channel})")
    print("[notify] production equivalent: scripts/send_finance_report_email.py et al. "
          "over SMTP / the Himalaya email gateway on cron (Stage 5)")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Ch6 Lab notifier (dry-run only)")
    ap.add_argument("--input", default=None, help="report markdown to notify about (default: output/report.md)")
    ap.add_argument("--channel", default="console")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = REPO_ROOT / cfg["publisher"]["output_dir"]
    input_path = Path(args.input) if args.input else out_dir / "report.md"

    notify(input_path, out_dir, channel=args.channel)


if __name__ == "__main__":
    main()
