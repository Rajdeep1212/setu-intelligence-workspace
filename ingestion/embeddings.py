"""
Embedding — Week 1.

Uses BAAI/bge-m3: one model that handles English, Hindi, and Bengali well
(100+ languages), 1024-dim output, which is what db/init.sql's
`chunks.embedding vector(1024)` column is sized for.

The model is loaded lazily and cached at module level so repeated calls in
one ingestion run don't reload ~2GB of weights each time. First call will
download the model from Hugging Face — that requires network access this
sandbox doesn't have, so run ingestion on your own machine.
"""

from __future__ import annotations

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("BAAI/bge-m3")
    return _model


def embed_chunks(chunks: list[str], batch_size: int = 16) -> list[list[float]]:
    """
    Embed a batch of text chunks. Returns L2-normalized vectors so that
    pgvector's cosine distance operator (`<=>`) behaves as expected.
    """
    if not chunks:
        return []
    model = _get_model()
    vectors = model.encode(
        chunks,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(chunks) > 50,
    )
    return vectors.tolist()
