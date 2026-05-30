import os
import pickle
import re
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from ingestion.models import DocumentChunk


def _tokenise(text: str) -> List[str]:
    """
    Lowercases and splits on word boundaries.  Keeping hyphens inside words
    (e.g. 'risk-weighted') matters for financial text where compound terms are
    common — a naive split on all punctuation would lose that signal.
    """
    return re.findall(r"\b[\w-]+\b", text.lower())


class BM25Index:
    """
    Wraps BM25Okapi with the same chunk list interface as VectorStore so the
    hybrid pipeline can treat both identically.
    BM25 is rebuilt in-memory from the saved corpus on each load because the
    BM25Okapi object itself is not serialisable; rebuilding from a token corpus
    of 10k chunks takes < 100 ms and avoids pickle compatibility issues.
    """

    def __init__(self, index_dir: str = "index") -> None:
        self._index_dir = index_dir
        self._bm25: BM25Okapi | None = None
        self._chunks: List[DocumentChunk] = []
        self._chunk_ids: set = set()
        os.makedirs(index_dir, exist_ok=True)

    def add(self, chunks: List[DocumentChunk]) -> int:
        """
        Appends new chunks and rebuilds the BM25 index over the full corpus.
        Rebuilding is cheaper than incremental updates for BM25Okapi and keeps
        the IDF statistics globally consistent.
        Returns the number of chunks actually added (after dedup).
        """
        new_chunks = [c for c in chunks if c.chunk_id not in self._chunk_ids]
        for c in new_chunks:
            self._chunk_ids.add(c.chunk_id)

        if not new_chunks:
            return 0

        self._chunks.extend(new_chunks)
        corpus = [_tokenise(c.content) for c in self._chunks]
        self._bm25 = BM25Okapi(corpus)
        return len(new_chunks)

    def search(self, query: str, top_k: int = 20) -> List[Tuple[float, DocumentChunk]]:
        """
        Returns up to top_k (score, chunk) tuples sorted by BM25 score.
        Chunks with score 0 (no query term overlap) are included in the ranked
        list — they'll be filtered out by the RRF step if vector search also
        disagrees with them.
        """
        if not self._bm25 or not self._chunks:
            return []

        tokens = _tokenise(query)
        scores = self._bm25.get_scores(tokens)

        ranked = sorted(
            zip(scores, self._chunks),
            key=lambda x: x[0],
            reverse=True,
        )
        return [(float(s), c) for s, c in ranked[:top_k]]

    def save(self) -> None:
        """
        Saves only the raw chunk list (not the BM25 object) because BM25Okapi
        cannot be reliably pickled across library versions.
        """
        with open(os.path.join(self._index_dir, "bm25_corpus.pkl"), "wb") as f:
            pickle.dump((self._chunks, self._chunk_ids), f)

    def load(self) -> bool:
        """Loads the chunk corpus from disk and reconstructs BM25Okapi in-memory."""
        path = os.path.join(self._index_dir, "bm25_corpus.pkl")
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            self._chunks, self._chunk_ids = pickle.load(f)
        if self._chunks:
            corpus = [_tokenise(c.content) for c in self._chunks]
            self._bm25 = BM25Okapi(corpus)
        return True

    @property
    def size(self) -> int:
        return len(self._chunks)
