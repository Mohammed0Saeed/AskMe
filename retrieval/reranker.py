from typing import List, Tuple

from sentence_transformers import CrossEncoder

from ingestion.models import DocumentChunk

# ms-marco-MiniLM-L-6-v2 is the standard production cross-encoder for passage
# re-ranking.  It was trained on 500k+ query-passage pairs from the MS MARCO
# dataset and generalises well to financial/legal text.  The MiniLM architecture
# keeps inference fast (~10 ms per batch of 20 on CPU).
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    """
    Cross-encoder re-ranker: jointly encodes (query, document) rather than
    encoding them separately like a bi-encoder.  This joint encoding lets the
    model see exactly how every query token interacts with every document token,
    producing far more accurate relevance scores than cosine similarity alone.
    The trade-off is that it is O(N) in candidates — which is why we first
    narrow to top-20 via hybrid search before calling the re-ranker.
    """

    def __init__(self) -> None:
        self._model = CrossEncoder(RERANKER_MODEL)

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[float, DocumentChunk]],
        top_k: int = 5,
    ) -> List[Tuple[float, DocumentChunk]]:
        """
        Scores each (query, chunk.content) pair and returns the top_k highest
        scoring chunks.  The cross-encoder score is a logit (unbounded float);
        higher means more relevant.  We keep the raw score rather than
        sigmoid-normalising here so the pipeline has full numeric range for
        downstream thresholding if needed.
        """
        if not candidates:
            return []

        pairs  = [(query, chunk.content) for _, chunk in candidates]
        scores = self._model.predict(pairs)

        ranked = sorted(
            zip(scores.tolist(), [chunk for _, chunk in candidates]),
            key=lambda x: x[0],
            reverse=True,
        )
        return ranked[:top_k]
