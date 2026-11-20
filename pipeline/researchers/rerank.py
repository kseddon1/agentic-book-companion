#!/usr/bin/env python3
"""
pipeline/researchers/rerank.py — Chapter 3 Lab: a lexical-overlap
rerank stand-in.

PRODUCTION NOTE: freemarketresearcher.com's real reranker is
RagSystem/core/reranking.py's CrossEncoderReranker. It loads a
sentence-transformers cross-encoder (default
`cross-encoder/ms-marco-MiniLM-L-6-v2`) and scores each (query, chunk)
pair directly -- a real neural relevance model, not a word-overlap
heuristic -- then keeps the top `k` [src:
~/Projects/RagSystem/core/reranking.py:15-52]. When no cross-encoder
model is installed, the real system degrades gracefully to the
original order rather than crashing [src: same file, lines 44-49].

This module is an HONEST stand-in, not a cross-encoder: it scores each
candidate by token overlap with the query (the fraction of the query's
tokens that also appear in the chunk), which is a real, working
heuristic and a documented simplification -- it has none of a cross-
encoder's semantic understanding. It exists to let the Chapter 3 Lab
show the *shape* of "retrieve a wider candidate set, then re-score it
before synthesis" without requiring a model download, matching the
zero-GPU guarantee from the Chapter 1 Lab.
"""
import argparse
import re
from typing import Optional

_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _tokenize(text: str):
    return {w.lower() for w in _WORD_RE.findall(text)}


def lexical_overlap_score(query: str, text: str) -> float:
    """Fraction of the query's unique tokens that also appear in `text`.
    0.0 if the query has no tokens or shares none with `text`."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = _tokenize(text)
    return len(q_tokens & t_tokens) / len(q_tokens)


def rerank(query: str, candidates: list, top_k: Optional[int] = None) -> list:
    """Re-score `candidates` (each a dict with a "text" key) by lexical
    overlap with `query`, best first. Ties keep their original relative
    order (stable sort), same user-visible contract as
    RagSystem.core.reranking.CrossEncoderReranker.rerank [src:
    ~/Projects/RagSystem/core/reranking.py:41-52]."""
    scored = [
        (lexical_overlap_score(query, c.get("text", "")), c) for c in candidates
    ]
    # Stable sort on negative score keeps ties in original order while
    # putting the highest score first (Python's sort is stable).
    scored.sort(key=lambda pair: -pair[0])
    k = top_k if top_k is not None else len(scored)
    out = []
    for score, c in scored[:k]:
        item = dict(c)
        item["rerank_score"] = round(score, 4)
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description="Ch3 Lab: lexical-overlap rerank stand-in")
    ap.add_argument("--query", required=True)
    ap.add_argument("--text", action="append", required=True, help="repeatable")
    args = ap.parse_args()
    candidates = [{"id": f"doc-{i}", "text": t} for i, t in enumerate(args.text)]
    ranked = rerank(args.query, candidates)
    for item in ranked:
        print(f"[rerank] score={item['rerank_score']:.3f} {item['id']}: {item['text'][:80]}")


if __name__ == "__main__":
    main()
