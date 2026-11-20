"""
tests/test_ch03_lab.py — Chapter 3 Lab verification.

Run with pytest if installed:
    pytest tests/test_ch03_lab.py -v

Or directly with plain Python (no pytest required, same zero-setup
path Chapter 1's test documents):
    python3 tests/test_ch03_lab.py

Asserts, per the Chapter 3 Blueprint's Lab Specification (Section 4):
  1. semantic_chunk's boundary-aware chunker produces more than one
     chunk on the two-topic fixture, and its boundary differs from
     Chapter 1's paragraph chunker (chunk_text) on the same source --
     specifically, the semantic chunker keeps the two topics in
     separate, pure chunks where paragraph chunking blends them.
  2. expand-rerank retrieval for a worded-differently query returns the
     chunk single-shot retrieval misses at the same top_k.
  3. honcho_stub.recall() returns the fact written in the same run.

This test builds its own isolated vector store (not the shared
data/vector_store.json Chapter 1's Lab writes to) so it never races
with another chapter's Lab/tests touching that file.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.crawler.crawl import chunk_text, ingest  # noqa: E402
from pipeline.crawler.semantic_chunk import chunk_semantic, _load_text  # noqa: E402
from pipeline.researchers.research import retrieve, retrieve_expand_rerank  # noqa: E402
from pipeline.memory import honcho_stub  # noqa: E402

FIXTURE = REPO_ROOT / "sample_sources" / "ch03" / "topic_boundary_fixture.md"
WORDED_DIFFERENTLY_QUERY = (
    "Why does generation speed drop in the middle of a long run, then "
    "recover once things cool down a bit?"
)
TARGET_CHUNK_ID = "topic_boundary_fixture-1"


def test_semantic_chunk_finds_the_topic_boundary():
    text = _load_text(FIXTURE)

    para_chunks = chunk_text(text, chunk_size_words=180)
    sem_chunks = chunk_semantic(text, breakpoint_percentile_threshold=90.0)

    assert len(sem_chunks) > 1, "semantic chunker produced only one chunk on a two-topic fixture"

    # The paragraph chunker's chunk 0 should contain vocabulary from BOTH
    # topics (it blends across the boundary); the semantic chunker's
    # chunk 0 should contain only the first topic's vocabulary ("sync",
    # not "throttle"). That contrast is the whole point of this Lab step.
    assert "throttle" in para_chunks[0].lower(), (
        "expected paragraph chunking to blend topic B's vocabulary into "
        "chunk 0 on this fixture -- if this fails, the fixture or Ch1 "
        "chunker changed and the demo needs re-tuning, not the assertion"
    )
    assert "throttle" not in sem_chunks[0].lower(), (
        "semantic chunking should keep chunk 0 pure to topic A (no "
        "'throttle'); finding it means the boundary detector is not "
        "isolating the topic shift"
    )
    assert "sync" not in sem_chunks[-1].lower(), (
        "semantic chunking's last chunk should be pure topic B (no "
        "'sync' from topic A)"
    )


def test_expand_rerank_recovers_what_single_shot_misses():
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "ch03_vector_store.json"
        ingest(
            REPO_ROOT / "sample_sources",
            store_path,
            chunk_size_words=180,
            clear=True,
        )
        ingest(
            REPO_ROOT / "sample_sources" / "ch03",
            store_path,
            chunk_size_words=180,
            clear=False,
        )

        single_shot = retrieve(WORDED_DIFFERENTLY_QUERY, store_path, top_k=3)
        single_shot_ids = [c["id"] for c in single_shot]
        assert TARGET_CHUNK_ID not in single_shot_ids, (
            f"expected single-shot retrieval to MISS {TARGET_CHUNK_ID} at "
            f"top_k=3 for this worded-differently query; got {single_shot_ids} "
            "-- if this fails, the fixture/query pair needs re-tuning, the "
            "mechanism this Lab demonstrates did not stop working"
        )

        expanded, variants = retrieve_expand_rerank(
            WORDED_DIFFERENTLY_QUERY, store_path, top_k=3
        )
        expanded_ids = [c["id"] for c in expanded]
        assert len(variants) >= 2, "expand_query should produce more than the original query"
        assert TARGET_CHUNK_ID in expanded_ids, (
            f"expected expand-rerank retrieval to SURFACE {TARGET_CHUNK_ID} "
            f"at top_k=3; got {expanded_ids}"
        )


def test_honcho_stub_recalls_what_it_just_remembered():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory_facts.json"
        fact = (
            "the companion repo's crontab-equivalent schedule should stay "
            "paused during Lab runs"
        )
        record = honcho_stub.remember(fact, peer="kseddon", path=path)
        assert record["fact"] == fact
        assert "learned_at" in record

        matches = honcho_stub.recall("crontab", peer="kseddon", path=path)
        assert len(matches) == 1
        assert matches[0]["fact"] == fact

        # A topic that was never remembered should recall nothing --
        # this is NOT retrieval (no ranking, no partial match beyond a
        # plain substring), which is the point of the contrast with
        # retrieve_expand_rerank() above.
        assert honcho_stub.recall("qdrant", peer="kseddon", path=path) == []


def test_cli_entrypoints_run_without_crashing():
    """Smoke test the three new CLI entrypoints directly, the way a
    reader running the documented Lab commands actually would."""
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.crawler.semantic_chunk"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    result = subprocess.run(
        [sys.executable, "-m", "pipeline.researchers.query_transform", "--query", "What is semantic chunking?"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    test_semantic_chunk_finds_the_topic_boundary()
    print("OK: semantic_chunk isolates the two-topic boundary; paragraph chunking blends it.")
    test_expand_rerank_recovers_what_single_shot_misses()
    print("OK: expand-rerank retrieval surfaced the chunk single-shot missed at the same top_k.")
    test_honcho_stub_recalls_what_it_just_remembered()
    print("OK: honcho_stub.recall() returned the fact written in the same run.")
    test_cli_entrypoints_run_without_crashing()
    print("OK: Chapter 3 Lab CLI entrypoints ran without crashing.")
    print("OK: Chapter 3 Lab ran end to end and produced all expected results.")
