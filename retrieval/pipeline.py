import logging
from typing import List, Optional, Tuple

from config import DIVERSITY_POOL, ENABLE_DIVERSITY, MAX_PER_SOURCE, MMR_LAMBDA
from ingestion.models import DocumentChunk
from retrieval.bm25_index import BM25Index
from retrieval.diversity import mmr_select
from retrieval.embedder import Embedder
from retrieval.hybrid_search import reciprocal_rank_fusion
from retrieval.models import RetrievalResult
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Retrieve this many candidates from each index before fusion + re-ranking.
# 20 is the sweet spot: wide enough to catch recall misses from either index,
# narrow enough that the cross-encoder re-ranker finishes in < 200 ms on CPU.
CANDIDATE_K = 20

# Access levels ordered from least to most permissive.  A user at level N can
# see all documents at level <= N, mirroring a typical information security model.
_ACCESS_HIERARCHY = ["public", "internal", "confidential", "restricted"]


def _access_rank(level: str) -> int:
    """Returns the numeric rank of an access level string (0 = public)."""
    try:
        return _ACCESS_HIERARCHY.index(level)
    except ValueError:
        return 0


class RetrievalPipeline:
    """
    Orchestrates the full hybrid retrieval flow:
      1. Embed query with BGE
      2. Vector search (FAISS) → top-20 candidates
      3. BM25 keyword search → top-20 candidates
      4. Reciprocal Rank Fusion → merged top-20
      5. Optional access-level and domain filters
      6. Cross-encoder re-rank → final top-K results

    All heavy models (embedder, cross-encoder) are loaded once at construction
    so per-request latency stays low after the first warm-up.
    """

    def __init__(self, index_dir: str = "index") -> None:
        logger.info("Loading retrieval models…")
        self._embedder     = Embedder()
        self._vector_store = VectorStore(index_dir=index_dir)
        self._bm25         = BM25Index(index_dir=index_dir)
        self._reranker     = Reranker()
        logger.info("Retrieval models ready.")

    def load_index(self) -> bool:
        """
        Loads persisted FAISS and BM25 indexes from disk.  Called once at app
        startup so a previously ingested corpus is immediately searchable without
        re-ingesting.  Returns True if both indexes were found on disk.
        """
        vec_ok  = self._vector_store.load()
        bm25_ok = self._bm25.load()
        if vec_ok and bm25_ok:
            logger.info("Index loaded: %d chunks", self._vector_store.size)
        else:
            logger.info("No existing index found — starting fresh.")
        return vec_ok and bm25_ok

    def index(self, chunks: List[DocumentChunk]) -> int:
        """
        Embeds and indexes a batch of DocumentChunks into both FAISS and BM25,
        then persists both indexes to disk.  Deduplication happens inside each
        store so this method is safe to call repeatedly with overlapping batches.
        Returns the number of new chunks that were actually added.
        """
        if not chunks:
            return 0

        texts      = [c.content for c in chunks]
        embeddings = self._embedder.embed_documents(texts)
        added_vec  = self._vector_store.add(embeddings, chunks)
        added_bm25 = self._bm25.add(chunks)

        self._vector_store.save()
        self._bm25.save()

        n = max(added_vec, added_bm25)
        logger.info("Indexed %d new chunks. Total in index: %d", n, self.total_chunks)
        return n

    def search(
        self,
        query: str,
        top_k: int = 5,
        user_access_level: Optional[str] = None,
        domain_filter: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        Full hybrid-search pipeline.  access_level filtering is hierarchical:
        passing "confidential" returns public + internal + confidential chunks
        but not restricted ones.  domain_filter is an exact-match string filter
        applied after fusion to further narrow results (e.g. "Legal").
        """
        if self.total_chunks == 0:
            return []

        # ── Step 1: embed query ───────────────────────────────────
        query_emb = self._embedder.embed_query(query)

        # ── Step 2 & 3: vector + BM25 candidate retrieval ────────
        vector_hits = self._vector_store.search(query_emb, top_k=CANDIDATE_K)
        bm25_hits   = self._bm25.search(query, top_k=CANDIDATE_K)

        # ── Step 4: access-level filter ───────────────────────────
        if user_access_level:
            max_rank = _access_rank(user_access_level)
            vector_hits = [(s, c) for s, c in vector_hits if _access_rank(c.metadata.access_level) <= max_rank]
            bm25_hits   = [(s, c) for s, c in bm25_hits   if _access_rank(c.metadata.access_level) <= max_rank]

        # ── Step 5: domain filter ─────────────────────────────────
        if domain_filter:
            vector_hits = [(s, c) for s, c in vector_hits if c.metadata.domain == domain_filter]
            bm25_hits   = [(s, c) for s, c in bm25_hits   if c.metadata.domain == domain_filter]

        # ── Step 6: Reciprocal Rank Fusion ────────────────────────
        fused = reciprocal_rank_fusion(vector_hits, bm25_hits)[:CANDIDATE_K]
        if not fused:
            return []

        # ── Step 7: cross-encoder re-rank (wide) + diversity select ─
        # Re-rank a wider pool than we need, then re-select the final top_k for
        # relevance AND source diversity so the LLM is not handed near-duplicate
        # chunks from a single document.  With diversity disabled this collapses
        # to the legacy behaviour (rerank straight to top_k).
        reranked = self._reranker.rerank(query, fused, top_k=DIVERSITY_POOL)
        reranked = self._select_diverse(reranked, top_k)

        # ── Step 8: build RetrievalResult objects ─────────────────
        # Build fast lookup dicts so we don't O(N²) scan for each score
        vec_scores  = {c.chunk_id: s for s, c in vector_hits}
        bm25_scores = {c.chunk_id: s for s, c in bm25_hits}
        rrf_scores  = {c.chunk_id: s for s, c in fused}

        results = []
        for rank, (rerank_score, chunk) in enumerate(reranked, start=1):
            results.append(RetrievalResult(
                chunk=chunk,
                vector_score=vec_scores.get(chunk.chunk_id, 0.0),
                bm25_score=bm25_scores.get(chunk.chunk_id, 0.0),
                rrf_score=rrf_scores.get(chunk.chunk_id, 0.0),
                rerank_score=float(rerank_score),
                rank=rank,
            ))

        return results

    def _select_diverse(
        self,
        reranked: List[Tuple[float, DocumentChunk]],
        top_k: int,
    ) -> List[Tuple[float, DocumentChunk]]:
        """
        Re-selects the final top_k from a wider reranked pool using Maximal
        Marginal Relevance plus a per-source quota.  Falls back to a plain
        top_k slice when diversity is disabled or the pool is already small —
        in which case behaviour is byte-for-byte identical to legacy retrieval.
        Chunk embeddings are computed on the small candidate set only (≤ pool
        size), so the added cost is one tiny embedding batch per query.
        """
        if not ENABLE_DIVERSITY or len(reranked) <= top_k:
            return reranked[:top_k]

        scores  = [s for s, _ in reranked]
        chunks  = [c for _, c in reranked]
        embs    = self._embedder.embed_documents([c.content for c in chunks])
        sources = [c.metadata.source_file for c in chunks]

        idx = mmr_select(
            scores, embs, top_k,
            lambda_=MMR_LAMBDA,
            sources=sources,
            max_per_source=MAX_PER_SOURCE,
        )
        return [reranked[i] for i in idx]

    def list_documents(self) -> list:
        """Returns one dict per unique source document with aggregated metadata."""
        import os as _os
        seen: dict = {}
        for chunk in self._vector_store._chunks:
            sf = _os.path.basename(chunk.metadata.source_file) or "Unknown"
            if sf not in seen:
                seen[sf] = {
                    "source_file":   sf,
                    "title":         chunk.metadata.title or sf,
                    "domain":        chunk.metadata.domain or "Unknown",
                    "access_level":  chunk.metadata.access_level,
                    "source_system": chunk.metadata.source_system,
                    "author":        chunk.metadata.author or "—",
                    "date":          chunk.metadata.date or "—",
                    "chunk_count":   0,
                }
            seen[sf]["chunk_count"] += 1
        return sorted(seen.values(), key=lambda d: d["domain"])

    @property
    def total_chunks(self) -> int:
        return self._vector_store.size
