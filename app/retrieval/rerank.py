"""Cross-encoder reranking — Week 2.

Reranks the top-N fused candidates with BAAI/bge-reranker-v2-m3, a
multilingual cross-encoder. Cross-encoders score a (query, passage) pair
jointly rather than comparing separately-computed embeddings, which is
slower but noticeably more accurate — cheap enough to run on 20 candidates,
too slow to run over the whole corpus (hence rerank-after-retrieve rather
than rerank-as-retrieval).
"""

from __future__ import annotations

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from FlagEmbedding import FlagReranker

        _reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True, max_length=256)
    return _reranker


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    if not candidates:
        return []

    reranker = _get_reranker()
    pairs = [[query, c["content"]] for c in candidates]
    scores = reranker.compute_score(pairs, normalize=True)

    if isinstance(scores, float):  # compute_score returns a bare float for a single pair
        scores = [scores]

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]
