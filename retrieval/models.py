from dataclasses import dataclass
from ingestion.models import DocumentChunk


@dataclass
class RetrievalResult:
    """
    Holds a retrieved chunk together with all the intermediate scores produced
    during the hybrid-search + re-rank pipeline.  Keeping all three score types
    (vector, BM25, re-rank) lets the UI show users exactly why each result was
    ranked where it was — critical for debugging and for building trust in the system.
    """
    chunk: DocumentChunk
    vector_score: float   # cosine similarity from FAISS [0, 1]
    bm25_score: float     # raw BM25Okapi score (unnormalized)
    rrf_score: float      # Reciprocal Rank Fusion composite score
    rerank_score: float   # cross-encoder score (higher = more relevant)
    rank: int             # 1-based final rank after re-ranking
