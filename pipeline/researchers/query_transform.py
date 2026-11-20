#!/usr/bin/env python3
"""
pipeline/researchers/query_transform.py — Chapter 3 Lab: deterministic
rule-based query expansion.

PRODUCTION NOTE: freemarketresearcher.com's real query transformer is
RagSystem/core/query_transformation.py's QueryTransformer.expand_query.
It returns up to `num_queries` variants of a question: an LLM-backed
rephrasing when an `llm` is supplied, or -- when no LLM is configured --
a deterministic rule-based fallback, `_rule_expand`, so a run never
fails for lack of a model [src:
~/Projects/RagSystem/core/query_transformation.py:56-66, 124-127].

This module mirrors `_rule_expand` exactly in shape: the same three
non-trivial variants (a "latest developments" rephrasing, a
domain-suffix variant, and a question-word-stripped variant), deduped
and capped at `num_queries`. It is deliberately NOT the LLM-backed path
-- this repo has no required model dependency, matching the Chapter 1
Lab's zero-setup guarantee. The honest limitation this mirrors from the
real system: without an LLM, expansion rephrases surface wording, it
does not generate true synonyms ("undervalued assets" vs.
"bargain-priced equities" is a real example of a gap this rule-based
fallback alone would NOT close -- see RagSystem/core/
query_transformation.py's module docstring and core/ch03.md's "What
Broke" section).
"""
import argparse
import re

_QUESTION_WORD_RE = re.compile(r"^(what|how|why|when|where|who|which)\s+", re.I)


def _dedupe(items, limit: int):
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
        if len(out) >= limit:
            break
    return out


def expand_query(query: str, num_queries: int = 3, domain: str = "research") -> list:
    """Up to `num_queries` variants of `query`; the original is always
    first. Deterministic, rule-based -- same shape as RagSystem.core.
    query_transformation._rule_expand [src:
    ~/Projects/RagSystem/core/query_transformation.py:56-66]."""
    core = query.strip().rstrip("?.").strip()
    variants = [
        query,
        f"What are the latest developments regarding {core}?",
        f"{core} — {domain} analysis and outlook",
    ]
    stripped = _QUESTION_WORD_RE.sub("", core).strip()
    if stripped and stripped != core:
        variants.append(stripped)
    return _dedupe(variants, num_queries)


def main():
    ap = argparse.ArgumentParser(description="Ch3 Lab: rule-based query expansion")
    ap.add_argument("--query", required=True)
    ap.add_argument("--num-queries", type=int, default=3)
    ap.add_argument("--domain", default="research")
    args = ap.parse_args()

    variants = expand_query(args.query, num_queries=args.num_queries, domain=args.domain)
    print(f"[query_transform] original: {args.query}")
    for i, v in enumerate(variants):
        print(f"[query_transform] variant {i}: {v}")


if __name__ == "__main__":
    main()
