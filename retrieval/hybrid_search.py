from typing import List, Tuple

from ingestion.models import DocumentChunk

# k=60 is the standard RRF damping constant from the original 2009 paper.
# It prevents a single top-1 hit from dominating the fused ranking and gives
# mid-ranked results from both lists a fair shot at the final top-K.
RRF_K = 60

# Vector search captures semantic similarity; BM25 captures exact keyword overlap.
# 60/40 weighting favours semantic understanding slightly but keeps BM25 strong
# enough that exact financial terms (ticker symbols, regulation codes, clause numbers)
# are not buried by semantic paraphrases.
VECTOR_WEIGHT = 0.6
BM25_WEIGHT   = 0.4


def reciprocal_rank_fusion(
    vector_results: List[Tuple[float, DocumentChunk]],
    bm25_results:   List[Tuple[float, DocumentChunk]],
) -> List[Tuple[float, DocumentChunk]]:
    """
    Merges two ranked lists into a single ordering using Reciprocal Rank Fusion.
    RRF formula:  score(d) = Σ  weight_i / (k + rank_i(d))
    A document that appears highly in both lists gets additive boosts from each,
    making it rise to the top even if it was not #1 in either list alone.
    Documents appearing in only one list still contribute — they just miss one
    additive term, which naturally penalises single-source hits.
    """
    scores: dict[str, list] = {}  # chunk_id → [rrf_score, chunk]

    for rank, (_, chunk) in enumerate(vector_results):
        cid = chunk.chunk_id
        if cid not in scores:
            scores[cid] = [0.0, chunk]
        scores[cid][0] += VECTOR_WEIGHT / (RRF_K + rank + 1)

    for rank, (_, chunk) in enumerate(bm25_results):
        cid = chunk.chunk_id
        if cid not in scores:
            scores[cid] = [0.0, chunk]
        scores[cid][0] += BM25_WEIGHT / (RRF_K + rank + 1)

    merged = sorted(scores.values(), key=lambda x: x[0], reverse=True)
    return [(rrf_score, chunk) for rrf_score, chunk in merged]
