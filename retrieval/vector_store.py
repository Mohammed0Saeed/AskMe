import os
import pickle
from typing import List, Tuple

import faiss
import numpy as np

from ingestion.models import DocumentChunk
from retrieval.embedder import EMBEDDING_DIM


class VectorStore:
    """
    Wraps a FAISS IndexFlatIP (inner-product index) with a parallel list of
    DocumentChunk objects so the index position always maps back to its chunk.
    IndexFlatIP performs exact nearest-neighbour search — no approximate
    shortcuts that could silently miss relevant documents.  For corpora up to
    ~500k chunks the brute-force scan is fast enough (<50 ms).
    """

    def __init__(self, index_dir: str = "index") -> None:
        self._index_dir  = index_dir
        self._index      = faiss.IndexFlatIP(EMBEDDING_DIM)
        self._chunks: List[DocumentChunk] = []
        self._chunk_ids: set = set()
        os.makedirs(index_dir, exist_ok=True)

    def add(self, embeddings: np.ndarray, chunks: List[DocumentChunk]) -> int:
        """
        Adds new chunks to the FAISS index.  Deduplicates by chunk_id so
        re-ingesting the same document does not create phantom duplicates that
        would artificially boost a chunk's apparent relevance.
        Returns the number of chunks actually added (after dedup).
        """
        new_embs, new_chunks = [], []
        for emb, chunk in zip(embeddings, chunks):
            if chunk.chunk_id not in self._chunk_ids:
                self._chunk_ids.add(chunk.chunk_id)
                new_embs.append(emb)
                new_chunks.append(chunk)

        if new_embs:
            self._index.add(np.array(new_embs, dtype="float32"))
            self._chunks.extend(new_chunks)

        return len(new_embs)

    def search(
        self, query_embedding: np.ndarray, top_k: int = 20
    ) -> List[Tuple[float, DocumentChunk]]:
        """
        Returns up to top_k (score, chunk) tuples ordered by cosine similarity.
        FAISS returns -1 as an index when fewer results exist than top_k; those
        are filtered out so callers never receive invalid entries.
        """
        if self._index.ntotal == 0:
            return []

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(
            query_embedding.reshape(1, -1).astype("float32"), k
        )
        return [
            (float(s), self._chunks[i])
            for s, i in zip(scores[0], indices[0])
            if i >= 0
        ]

    def save(self) -> None:
        """Persists both the FAISS binary index and the chunk list to disk."""
        faiss.write_index(self._index, os.path.join(self._index_dir, "faiss.bin"))
        with open(os.path.join(self._index_dir, "chunks.pkl"), "wb") as f:
            pickle.dump((self._chunks, self._chunk_ids), f)

    def load(self) -> bool:
        """
        Loads a previously saved index from disk.  Returns True on success so
        the pipeline can decide whether to log 'index loaded' or 'starting fresh'.
        """
        fp = os.path.join(self._index_dir, "faiss.bin")
        cp = os.path.join(self._index_dir, "chunks.pkl")
        if not (os.path.exists(fp) and os.path.exists(cp)):
            return False
        self._index = faiss.read_index(fp)
        with open(cp, "rb") as f:
            self._chunks, self._chunk_ids = pickle.load(f)
        return True

    @property
    def size(self) -> int:
        return len(self._chunks)
