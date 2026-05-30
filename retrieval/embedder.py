import numpy as np
from sentence_transformers import SentenceTransformer

# BGE models outperform generic models on domain-specific retrieval benchmarks.
# bge-small-en-v1.5 is 384-dimensional — fast enough for real-time queries while
# staying competitive with larger models on financial/legal content.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM   = 384

# BGE requires a specific instruction prefix on *query* strings (not on documents)
# to activate its asymmetric retrieval mode.  Omitting it degrades recall by ~5-10%.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    """
    Wraps sentence-transformers to produce L2-normalised embeddings.
    Normalised vectors make dot-product (inner product) equivalent to cosine
    similarity, which is what FAISS IndexFlatIP computes.
    """

    def __init__(self) -> None:
        # show_progress_bar=False keeps server logs clean during batch indexing
        self._model = SentenceTransformer(EMBEDDING_MODEL)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """
        Embeds a list of document texts.  Documents do NOT get the BGE query prefix —
        that asymmetry is intentional: the query encoder and document encoder
        operate in slightly different semantic spaces, which improves recall.
        Returns a float32 array of shape (N, EMBEDDING_DIM) with unit-norm rows.
        """
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype("float32")

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embeds a single query string with the BGE instruction prefix.
        Returns a 1-D float32 array of length EMBEDDING_DIM.
        """
        return self.embed_documents([BGE_QUERY_PREFIX + query])[0]
