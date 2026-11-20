#!/usr/bin/env python3
"""
pipeline/approval/gate.py — Chapter 7 Lab: the approval gate.

PRODUCTION NOTE: freemarketresearcher.com's real publish pipelines
(MarketSectorPipeline, AnalysisPipeline, BriefPipeline) have NO
approval gate today. WPPublisher.clear_category_posts() and
.publish() both already take a dry_run: bool = False parameter
[src: ~/Projects/MarketSectorPipeline/src/WPPublisher.py:133,181,
191-193], but publish_reports.sh calls run_pipeline.py with zero
confirmation step, and no production caller ever sets dry_run=True.
This module is the gate Chapter 7 proposes adding on top of that
existing-but-unused seam. It does not touch WPPublisher.py, SSH, or
wp-cli — it is a teaching stand-in layered on this companion repo's
own dry-run-only publisher from Chapter 1
(pipeline/publish/publish.py).

This module mirrors, in miniature, the real Hermes approvals model
read from this machine's live config on 2026-11-19:

- `approvals.cron_mode` / `approvals.unattended_mode` both default to
  "deny" [src: ~/.hermes/hermes-agent/hermes_cli/config_defaults.py:
  1626-1628] — a cron job or an unattended-platform session that hits
  a gated action does not wait and hope; it fails closed immediately.
- Unattended platforms (webhook, msgraph_webhook, api_server) have no
  `send_exec_approval` / `/approve` channel at all, so a pending
  approval there would just block for the full timeout (60-300s) with
  nobody able to answer it (issues #37284, #87509 in Hermes's own
  tracker) [src: ~/.hermes/hermes-agent/tools/approval_context.py:
  183-251]. `unattended_mode: deny` exists specifically to avoid that
  deadlock by not waiting in the first place.
- `subagent_auto_approve` defaults to False: a delegated worker always
  auto-denies its own approvals, never auto-approves itself
  [src: ~/.hermes/hermes-agent/hermes_cli/config_defaults.py:
  1336-1339].

There is no "self-approved" state anywhere in this module, on
purpose — that state does not exist in the real system either. A
gated action is either PENDING (written, waiting on a human) or
APPROVED (a human explicitly said yes, recorded with a timestamp).
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def requires_approval(attended: bool) -> bool:
    """
    Does this action need an explicit human "yes" before it runs?

    In this Lab, publishing a report is the one gated action class,
    and it always answers True here — mirroring how the real
    `approvals.mode` flags a command as dangerous regardless of *who*
    happens to be running the session. What differs between attended
    and unattended is not whether the gate applies (it always does for
    this action), but *how* it can be resolved: an attended session
    can ask a live human right now via `input()`; an unattended
    session (simulating cron or a webhook — no TTY, nobody watching)
    cannot ask anyone, and must fail closed instead of guessing
    "probably fine" — exactly the reasoning behind
    `cron_mode: deny` / `unattended_mode: deny` in the real config.

    The `attended` parameter is kept in the signature, unused in this
    Lab's single-action policy, as the extension point for a reader's
    own pipeline: not every action needs a human answer, but publish
    does, and a richer policy would decide that here per-action.
    """
    return True


def request_approval(action: str, token_path: Path, **context) -> Path:
    """
    Write a PENDING approval record instead of guessing.

    This is the unattended branch's entire job when it hits a gated
    action: it cannot ask a human right now, so instead of blocking
    for a timeout (or worse, approving itself) it leaves a durable,
    inspectable record of *what* it wanted to do, *when*, and *why it
    stopped* — the file-based stand-in for the prompt a real Hermes
    approval would raise over a chat or gateway channel. Returns the
    path written.
    """
    token_path = Path(token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "action": action,
        "status": "PENDING",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "unattended run has no human to answer an approval prompt; "
            "mirrors approvals.unattended_mode: deny -- fail closed "
            "instead of blocking for a timeout with nobody to answer"
        ),
        **context,
    }
    token_path.write_text(json.dumps(record, indent=2) + "\n")
    return token_path


def check_approval(token_path: Path) -> bool:
    """
    Read back an explicit approval token.

    A human (via the `--resume-pending` flow in run_pipeline.py)
    writes `status: "APPROVED"` into the pending record to simulate
    answering a real approval prompt. Any other outcome — PENDING,
    DENIED, a missing file, malformed JSON — reads as not-approved.
    The gate fails closed by construction; it has no code path that
    fails open.
    """
    token_path = Path(token_path)
    if not token_path.exists():
        return False
    try:
        record = json.loads(token_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return record.get("status") == "APPROVED"


def deny_pending(token_path: Path) -> dict:
    """
    Mark a pending record DENIED in place. A denial is a recorded,
    visible state too -- not a deletion. This is the one Ch7-specific
    traceability fact worth keeping even though the deep observability
    mechanics belong to Chapter 10: PENDING, APPROVED, and DENIED are
    three distinct states a human reviewing this later can tell apart,
    none of which is "we don't know."
    """
    token_path = Path(token_path)
    record = json.loads(token_path.read_text())
    record["status"] = "DENIED"
    record["denied_at"] = datetime.now(timezone.utc).isoformat()
    token_path.write_text(json.dumps(record, indent=2) + "\n")
    return record


def approve_pending(token_path: Path) -> dict:
    """
    Mark a pending record APPROVED in place -- the human closing the
    loop an unattended run opened. Returns the updated record.
    """
    token_path = Path(token_path)
    record = json.loads(token_path.read_text())
    record["status"] = "APPROVED"
    record["approved_at"] = datetime.now(timezone.utc).isoformat()
    token_path.write_text(json.dumps(record, indent=2) + "\n")
    return record
