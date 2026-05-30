"""
Unit tests for retrieval.diversity.mmr_select.

Pure numpy — no models, no API keys, no index required.  Run with:
    python test_diversity.py
"""

import numpy as np

from retrieval.diversity import mmr_select


def _unit(vecs):
    """L2-normalise rows so the dot product equals cosine (as the BGE embedder does)."""
    arr = np.asarray(vecs, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def test_lambda_one_reproduces_rerank_order():
    """lambda_=1.0 → pure relevance → indices in descending score order."""
    scores = [0.9, 0.5, 0.7, 0.1]
    embs   = _unit([[1, 0], [0, 1], [1, 1], [1, 0]])
    idx = mmr_select(scores, embs, top_k=3, lambda_=1.0)
    assert idx == [0, 2, 1], idx
    print("✓ lambda=1.0 reproduces rerank order")


def test_diversity_demotes_near_duplicate():
    """
    Candidate 1 is the 2nd most relevant but is a near-duplicate of the top hit.
    With diversity on, a less-relevant but distinct chunk should be picked 2nd.
    """
    scores = [0.95, 0.90, 0.60]
    embs   = _unit([[1, 0], [0.99, 0.01], [0, 1]])  # idx0 ≈ idx1, idx2 orthogonal
    idx = mmr_select(scores, embs, top_k=2, lambda_=0.5)
    assert idx[0] == 0, idx
    assert idx[1] == 2, f"expected distinct chunk 2 to beat duplicate 1, got {idx}"
    print("✓ diversity demotes a near-duplicate")


def test_per_source_quota_is_never_exceeded():
    """No source may contribute more than max_per_source chunks to the result."""
    scores  = [0.9, 0.85, 0.8, 0.4]
    embs    = _unit([[1, 0], [1, 0], [1, 0], [0, 1]])
    sources = ["A.pdf", "A.pdf", "A.pdf", "B.pdf"]
    idx = mmr_select(scores, embs, top_k=3, lambda_=1.0,
                     sources=sources, max_per_source=2)
    picked = [sources[i] for i in idx]
    assert picked.count("A.pdf") <= 2, picked
    assert "B.pdf" in picked, picked
    print("✓ per-source quota is never exceeded")


def test_quota_block_terminates_gracefully():
    """When the quota blocks every remaining candidate, return what we have."""
    scores  = [0.9, 0.8, 0.7]
    embs    = _unit([[1, 0], [1, 0], [1, 0]])
    sources = ["A.pdf", "A.pdf", "A.pdf"]
    idx = mmr_select(scores, embs, top_k=3, lambda_=1.0,
                     sources=sources, max_per_source=1)
    assert len(idx) == 1, idx
    print("✓ quota-blocked selection terminates gracefully")


def test_empty_and_small_inputs():
    assert mmr_select([], np.zeros((0, 2)), top_k=5) == []
    idx = mmr_select([0.5], _unit([[1, 0]]), top_k=5)
    assert idx == [0], idx
    print("✓ empty / undersized inputs handled")


def test_degenerate_equal_scores():
    """Equal rerank scores → relevance carries no signal; selection still works."""
    scores = [0.5, 0.5, 0.5]
    embs   = _unit([[1, 0], [0, 1], [1, 1]])
    idx = mmr_select(scores, embs, top_k=2, lambda_=0.7)
    assert len(idx) == 2 and len(set(idx)) == 2, idx
    print("✓ degenerate equal-score case handled")


if __name__ == "__main__":
    test_lambda_one_reproduces_rerank_order()
    test_diversity_demotes_near_duplicate()
    test_per_source_quota_is_never_exceeded()
    test_quota_block_terminates_gracefully()
    test_empty_and_small_inputs()
    test_degenerate_equal_scores()
    print("\nAll diversity tests passed.")
