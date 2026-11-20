#!/usr/bin/env python3
"""
pipeline/crawler/crawl.py — Chapter 1 Lab: crawl -> chunk -> embed -> upsert

PRODUCTION NOTE: freemarketresearcher.com's real crawler is
RagSystem/crawler/{discovery,web,ingestor,config}.py. It pulls live
finance/tech/ag sources on a cron schedule, chunks with
RagSystem/core/semantic_chunking.py, embeds with Ollama's
nomic-embed-text:v1.5, and upserts into a real Qdrant collection
(`researcher_docs`) via RagSystem/db/qdrant_client.py.

This module is the Chapter 1 teaching stand-in:
  - reads fixture documents from sample_sources/ (no live network calls,
    so the Lab is reproducible and free)
  - chunks them per-paragraph, merging short paragraphs up to a target
    size (simple, NOT semantic chunking)
  - computes a crude hash-based pseudo-embedding -- NOT nomic-embed-text,
    NOT a real neural embedding. It is a deterministic bag-of-words hash
    vector so cosine similarity still does *something* sensible without
    any model, GPU, network call, or dependency.
  - upserts chunks + pseudo-embeddings into a local JSON file
    (data/vector_store.json) acting as a vector store, standing in for
    Qdrant.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import load_config  # noqa: E402

EMBED_DIM = 256
WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def tokenize(text: str):
    return [w.lower() for w in WORD_RE.findall(text)]


def hash_embedding(text: str, dim: int = EMBED_DIM):
    """Deterministic hashed bag-of-words pseudo-embedding.

    Stand-in for nomic-embed-text:v1.5's real 768-dim neural embedding.
    Each token hashes into one of `dim` buckets with a +1/-1 sign (the
    classic "hashing trick"); bucket counts are then L2-normalized so
    cosine similarity between two vectors behaves like a crude lexical
    overlap score. This has none of a real embedding model's semantic
    understanding -- it is here purely to show the crawl->chunk->embed->
    upsert *shape* without requiring a model, GPU, or network call.
    """
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a, b) -> float:
    """Both vectors are already L2-normalized by hash_embedding(), so
    cosine similarity is just the dot product."""
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, chunk_size_words: int = 180):
    """Paragraph chunking: split on blank lines, then greedily merge
    consecutive paragraphs until the target word count is reached.
    Simple and fast; production uses semantic_chunking.py instead."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf, buf_words = [], [], 0
    for p in paragraphs:
        words = p.split()
        if buf_words + len(words) > chunk_size_words and buf:
            chunks.append(" ".join(buf))
            buf, buf_words = [], 0
        buf.append(p)
        buf_words += len(words)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def load_sources(source_dir):
    source_dir = Path(source_dir)
    paths = sorted(source_dir.glob("*.md")) + sorted(source_dir.glob("*.txt"))
    return paths


def ingest(source_dir, store_path, chunk_size_words: int = 180, clear: bool = True):
    """Crawl -> chunk -> embed -> upsert.

    Mirrors the production signature `ingest(sample_sources_dir,
    qdrant_client, embed_model)` from the Blueprint, simplified to a
    JSON file path instead of a Qdrant client/embed model object.
    """
    store_path = Path(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if not clear and store_path.exists():
        records = json.loads(store_path.read_text()).get("records", [])

    files = load_sources(source_dir)
    if not files:
        print(f"[crawl] WARNING: no .md/.txt files found in {source_dir}")

    new_count = 0
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        chunks = chunk_text(text, chunk_size_words)
        for i, chunk in enumerate(chunks):
            rec = {
                "id": f"{fp.stem}-{i}",
                "source_file": fp.name,
                "chunk_index": i,
                "text": chunk,
                "embedding": hash_embedding(chunk),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            records.append(rec)
            new_count += 1
        print(f"[crawl] {fp.name}: {len(chunks)} chunks")

    store_path.write_text(
        json.dumps({"collection": "researcher_docs", "records": records}, indent=2)
    )
    print(f"[crawl] upserted {new_count} chunks ({len(records)} total in store) -> {store_path}")
    return len(records)


def main():
    ap = argparse.ArgumentParser(
        description="Ch1 Lab crawler: crawl -> chunk -> embed -> upsert (JSON stand-in for Qdrant)"
    )
    ap.add_argument("--source", default=None, help="sample_sources dir (default: from config)")
    ap.add_argument("--collection", default="researcher_docs", help="label only; this JSON store has one collection")
    ap.add_argument("--config", default=None)
    ap.add_argument("--no-clear", action="store_true", help="append instead of replacing the store")
    ap.add_argument(
        "--chunk-size-words",
        type=int,
        default=None,
        help="Ch3 Lab: override the config-driven chunk size directly in words "
        "(useful for small fixture documents where the default ~394-word "
        "target would merge an entire short file into one chunk)",
    )
    ap.add_argument(
        "--store",
        default=None,
        help="Ch3 Lab: override the config-driven vector store path (e.g. "
        "data/ch03_vector_store.json), so the Ch3 Lab's own fixture corpus "
        "doesn't collide with the shared data/vector_store.json other "
        "chapters' Labs/tests also write to",
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    source_dir = args.source or cfg["crawler"]["source_dir"]
    store_path = Path(args.store) if args.store else REPO_ROOT / cfg["vector_store"]["path"]
    if args.chunk_size_words is not None:
        chunk_size_words = args.chunk_size_words
    else:
        chunk_size_tokens = cfg["crawler"].get("chunk_size", 512)
        chunk_size_words = max(20, int(chunk_size_tokens / 1.3))  # ~1.3 tokens/word

    print(f"[crawl] source={source_dir} collection={args.collection} store={store_path} chunk_size_words={chunk_size_words}")
    ingest(source_dir, store_path, chunk_size_words=chunk_size_words, clear=not args.no_clear)


if __name__ == "__main__":
    main()
