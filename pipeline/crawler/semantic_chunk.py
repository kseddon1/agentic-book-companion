#!/usr/bin/env python3
"""
pipeline/crawler/semantic_chunk.py — Chapter 3 Lab: a semantic-boundary
chunker, scaled to this repo's pseudo-embedding.

PRODUCTION NOTE: freemarketresearcher.com's real semantic chunker is
RagSystem/core/semantic_chunking.py's SemanticChunker. It splits text
into sentences, embeds each sentence with nomic-embed-text:v1.5 (768-dim,
real neural embedding), computes cosine similarity between adjacent
sentence embeddings, and cuts a new chunk wherever the dissimilarity
exceeds a percentile threshold (default: 95th percentile of the observed
drops) [src: RagSystem/core/semantic_chunking.py:148-154;
RagSystem/core/config.py:27-45 for the real defaults this mirrors:
max_chunk_chars=2500, min_chunk_chars=300, breakpoint_percentile_threshold=95].

This module is the Chapter 3 Lab teaching stand-in: SAME algorithm
shape (split sentences -> embed each -> adjacent cosine distance ->
percentile cutoff -> cut), but using crawl.py's hash_embedding() instead
of a real neural embedding, and a much smaller default percentile
threshold tuned for this Lab's tiny fixture corpus rather than
production's multi-thousand-chunk corpus. It is NOT the real
SemanticChunker and does not try to be -- it exists to show the
*boundary-detection idea* without requiring Ollama, a GPU, or a model
download, matching the zero-setup guarantee from the Chapter 1 Lab.

Chapter 1's chunk_text() (paragraph-merge, no topic awareness) is kept
unmodified in crawl.py; this module is additive, not a replacement.
"""
import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.crawler.crawl import cosine, hash_embedding, chunk_text  # noqa: E402

_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def split_sentences(text: str) -> list:
    """Naive sentence splitter; collapses whitespace first.

    Same shape as RagSystem.core.semantic_chunking.split_sentences
    [src: ~/Projects/RagSystem/core/semantic_chunking.py:45-50].
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [p.strip() for p in _SENTENCE_END_RE.split(text) if p.strip()]


def _percentile(values, p: float) -> float:
    """Linear-interpolated percentile (p in 0..100). Same shape as the
    real SemanticChunker's _percentile helper."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def semantic_boundaries(sentences, breakpoint_percentile_threshold: float = 90.0):
    """Indices of sentences that start a new chunk (always includes 0).

    Mirrors RagSystem.core.semantic_chunking.SemanticChunker._boundaries:
    compute cosine distance between every adjacent pair of (pseudo-)
    embeddings, then cut wherever the distance exceeds the given
    percentile of all observed distances [src:
    ~/Projects/RagSystem/core/semantic_chunking.py:148-154].

    The 90th-percentile default (vs. production's 95th) is a deliberate
    Lab-scale adjustment: a corpus of a few dozen sentences has too few
    gaps for a 95th-percentile cutoff to reliably isolate more than one
    boundary; it is documented here, not silently changed.
    """
    if len(sentences) < 2:
        return [0]
    embeddings = [hash_embedding(s) for s in sentences]
    distances = [1.0 - cosine(a, b) for a, b in zip(embeddings, embeddings[1:])]
    cutoff = _percentile(distances, breakpoint_percentile_threshold)
    return [0] + [i + 1 for i, d in enumerate(distances) if d > cutoff]


def chunk_semantic(
    text: str,
    max_chunk_chars: int = 2500,
    min_chunk_chars: int = 40,
    breakpoint_percentile_threshold: float = 90.0,
) -> list:
    """Split `text` on semantic (topic) boundaries instead of paragraph
    breaks. Falls back to returning the whole text as one chunk when
    there are fewer than 2 sentences (nothing to compare)."""
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return [text.strip()] if text.strip() else []

    starts = semantic_boundaries(sentences, breakpoint_percentile_threshold)
    chunks = [
        " ".join(sentences[s:e])
        for s, e in zip(starts, starts[1:] + [len(sentences)])
    ]

    # Merge an undersized chunk into its neighbour, same spirit as the
    # real SemanticChunker's _post_process merge step (simplified: this
    # Lab stand-in only merges forward into the next chunk).
    merged = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        while len(chunk) < min_chunk_chars and i + 1 < len(chunks):
            i += 1
            chunk = f"{chunk} {chunks[i]}"
        merged.append(chunk)
        i += 1

    # Force-split anything that ended up oversized, same idea as
    # SemanticChunker._force_split (character ceiling, not topic-aware).
    out = []
    for chunk in merged:
        if len(chunk) <= max_chunk_chars:
            out.append(chunk)
        else:
            out.extend(
                chunk[i : i + max_chunk_chars]
                for i in range(0, len(chunk), max_chunk_chars)
            )
    return out


def _load_text(source) -> str:
    source = Path(source)
    if source.is_dir():
        files = sorted(source.glob("*.md")) + sorted(source.glob("*.txt"))
        if not files:
            raise SystemExit(f"no .md/.txt files found in {source}")
        return "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    return source.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(
        description="Ch3 Lab: semantic-boundary chunking vs. Ch1's paragraph chunking"
    )
    ap.add_argument(
        "--source",
        default=str(REPO_ROOT / "sample_sources" / "ch03" / "topic_boundary_fixture.md"),
        help="a file, or a directory of .md/.txt files",
    )
    ap.add_argument("--compare-to", choices=["paragraph"], default="paragraph")
    ap.add_argument("--percentile", type=float, default=90.0)
    args = ap.parse_args()

    text = _load_text(args.source)

    para_chunks = chunk_text(text, chunk_size_words=180)
    sem_chunks = chunk_semantic(text, breakpoint_percentile_threshold=args.percentile)

    print(f"[semantic_chunk] source={args.source}")
    print(f"[semantic_chunk] paragraph chunking (Ch1 chunk_text): {len(para_chunks)} chunk(s)")
    for i, c in enumerate(para_chunks):
        print(f"  --- paragraph chunk {i} ({len(c)} chars) ---")
        print(f"  {c[:220]}{'...' if len(c) > 220 else ''}")

    print(f"\n[semantic_chunk] semantic-boundary chunking: {len(sem_chunks)} chunk(s)")
    for i, c in enumerate(sem_chunks):
        print(f"  --- semantic chunk {i} ({len(c)} chars) ---")
        print(f"  {c[:220]}{'...' if len(c) > 220 else ''}")

    print(
        f"\n[semantic_chunk] RESULT: paragraph chunking produced {len(para_chunks)} "
        f"chunk(s); semantic-boundary chunking produced {len(sem_chunks)} chunk(s) "
        f"on the same source. See core/ch03.md for why that difference matters."
    )


if __name__ == "__main__":
    main()
