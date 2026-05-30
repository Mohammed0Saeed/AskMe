"""
Diversity-aware selection for the final top-K of the retrieval pipeline.

The cross-encoder re-ranker scores every candidate independently against the
query, so the highest-scoring chunks tend to cluster — often several near-
duplicate passages from the same document.  That wastes the top-K budget and
starves cross-source synthesis: the LLM never sees the second source because
it never made the cut.

`mmr_select` re-introduces diversity *after* relevance ranking using Maximal
Marginal Relevance, optionally constrained by a hard per-source quota.  It is a
pure, model-free function (numpy only) so it is fast and trivially testable.
"""

from typing import List, Optional, Sequence

import numpy as np


def _normalize(scores: np.ndarray) -> np.ndarray:
    """
    Min-max scales rerank logits into [0, 1] so they are directly comparable to
    cosine similarities inside the MMR objective.  When every candidate has the
    same score (degenerate range) we return all-ones — relevance carries no
    signal, so selection falls back to pure diversity.
    """
    lo, hi = float(scores.min()), float(scores.max())
    if hi <= lo:
        return np.ones_like(scores)
    return (scores - lo) / (hi - lo)


def mmr_select(
    rerank_scores: Sequence[float],
    embeddings: np.ndarray,
    top_k: int,
    lambda_: float = 0.7,
    sources: Optional[Sequence[str]] = None,
    max_per_source: Optional[int] = None,
) -> List[int]:
    """
    Greedy Maximal Marginal Relevance over already-reranked candidates.

    Returns the SELECTED INDICES (into the candidate list) in pick order, so the
    caller can map them straight back to its own (score, chunk) tuples and keep
    every existing sub-score intact.

    Objective for each not-yet-selected candidate c:

        MMR(c) = lambda_ * relevance(c)
                 - (1 - lambda_) * max  similarity(c, s)
                                   s in selected

      relevance(c)      = min-max normalised rerank score (per-chunk accuracy)
      similarity(c, s)  = cosine between chunk embeddings.  Embeddings are
                          expected L2-normalised (as the BGE embedder produces),
                          so the dot product IS the cosine.

    lambda_ == 1.0 reproduces the plain rerank order (diversity off).
    lambda_ lower trades relevance for spread.

    max_per_source, when set, is a hard cap on how many selected chunks may share
    the same `sources[i]` value (e.g. source_file) — guaranteeing breadth even
    when MMR alone would not enforce it.
    """
    n = len(rerank_scores)
    if n == 0:
        return []
    top_k = min(top_k, n)

    rel = _normalize(np.asarray(rerank_scores, dtype=np.float32))
    sim = embeddings @ embeddings.T  # NxN cosine (embeddings are unit-norm)

    selected: List[int] = []
    per_source: dict = {}

    while len(selected) < top_k:
        best_i, best_val = None, -np.inf
        for i in range(n):
            if i in selected:
                continue
            # Enforce the per-source quota as a hard constraint.
            if max_per_source is not None and sources is not None:
                if per_source.get(sources[i], 0) >= max_per_source:
                    continue
            redundancy = max((sim[i][j] for j in selected), default=0.0)
            val = lambda_ * float(rel[i]) - (1.0 - lambda_) * float(redundancy)
            if val > best_val:
                best_i, best_val = i, val

        if best_i is None:
            # Every remaining candidate is blocked by its source quota.
            break

        selected.append(best_i)
        if sources is not None:
            key = sources[best_i]
            per_source[key] = per_source.get(key, 0) + 1

    return selected
