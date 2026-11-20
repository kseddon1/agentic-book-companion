#!/usr/bin/env python3
"""
pipeline/memory/honcho_stub.py — Chapter 3 Lab: a memory stand-in, NOT
a Honcho client.

PRODUCTION NOTE: this project's real long-term memory is self-hosted
Honcho on Docker Desktop -- Postgres + pgvector, reached through
`~/.hermes/config.yaml`'s `memory.provider: honcho`
[src: ~/.hermes/config.yaml:102-109, read 2026-11-19] and
`~/.hermes/honcho.json` [src: read 2026-11-19]. Honcho's own schema has
two kinds of tables that matter for this distinction: `messages` (raw
conversation turns) and `documents` (the deriver's distilled, standing
facts about the user) [src: `docker exec honcho-local-database-1 psql
-U postgres -c '\\dt'`, run 2026-11-19]. A real `documents` row found on
this machine, verified live:

    User's production crontab (freemarketresearcher.com researchers:
    crawl, synthesize, publish, market-state snapshot) is normally
    fully active. The user sometimes comments every line out to save
    local compute...
    [src: `docker exec honcho-local-database-1 psql -U postgres -t -c
    "select ... from documents where content ilike '%crontab%' ..."`,
    run 2026-11-19]

THIS MODULE DOES NOT WRAP THE HONCHO API, run Docker, or need Postgres.
It is a deliberately tiny, explicit teaching shape: a flat JSON file
(`data/memory_facts.json`) of `{peer, fact, learned_at}` records, with
a `remember()` / `recall()` pair that mimics the *shape* of Honcho's
`documents` table (one standing fact per row, accumulated over time,
never bulk-rebuilt the way a RAG corpus is) -- not its API, its
embeddings, or its deriver. The point of this module is the contrast
with pipeline/researchers/research.py's retrieve(): retrieval re-
derives an answer from a corpus that's rebuilt by a crawler; this stub
only ever appends what it's told and recalls it unchanged. Nothing
here is re-synthesized.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PATH = REPO_ROOT / "data" / "memory_facts.json"


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("facts", [])
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: Path, facts: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"facts": facts}, indent=2))


def remember(fact: str, peer: str = "kseddon", path: Path = DEFAULT_PATH) -> dict:
    """Append one standing fact about `peer`. Never rewrites or
    deletes an existing fact -- accumulation, not re-derivation, is the
    whole point of this stand-in (mirrors Honcho's `documents` table
    shape, not a RAG corpus that gets rebuilt by a crawler)."""
    facts = _load(path)
    record = {
        "peer": peer,
        "fact": fact,
        "learned_at": datetime.now(timezone.utc).isoformat(),
    }
    facts.append(record)
    _save(path, facts)
    return record


def recall(topic: str, peer: Optional[str] = None, path: Path = DEFAULT_PATH) -> list:
    """Every remembered fact whose text contains `topic` (case-
    insensitive substring match), optionally filtered to one peer.
    Returns facts in the order they were learned, oldest first --
    exactly what's stored, with no retrieval ranking and no
    re-synthesis, unlike pipeline.researchers.research.retrieve()."""
    facts = _load(path)
    topic_lower = topic.lower()
    out = [
        f
        for f in facts
        if topic_lower in f["fact"].lower() and (peer is None or f["peer"] == peer)
    ]
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Ch3 Lab: memory stand-in (NOT a Honcho client) -- remember/recall"
    )
    ap.add_argument("--peer", default="kseddon")
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--remember", metavar="FACT")
    group.add_argument("--recall", metavar="TOPIC")
    args = ap.parse_args()

    path = Path(args.path)
    if args.remember:
        record = remember(args.remember, peer=args.peer, path=path)
        print(f"[honcho_stub] remembered for {record['peer']} at {record['learned_at']}:")
        print(f"[honcho_stub]   {record['fact']}")
    else:
        matches = recall(args.recall, peer=args.peer, path=path)
        print(f"[honcho_stub] recall(topic={args.recall!r}, peer={args.peer!r}): {len(matches)} match(es)")
        for m in matches:
            print(f"[honcho_stub]   ({m['learned_at']}) {m['fact']}")


if __name__ == "__main__":
    main()
