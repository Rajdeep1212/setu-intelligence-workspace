"""
Hybrid retrieval pipeline — Week 2.

  query
    -> embed (bge-m3)                         \
    -> dense_search (pgvector cosine, top-20)   } -> reciprocal rank fusion -> top-20
    -> keyword_search (Postgres FTS, top-20)   /
    -> rerank (bge-reranker-v2-m3)             -> top-5

Note: this reuses ingestion.embeddings.embed_chunks to embed the query with
the *same* model used to embed the corpus at ingest time — using a different
embedding model for queries vs. documents would put them in different vector
spaces and silently wreck retrieval quality. Because of this, the API
container now needs the same torch/sentence-transformers/FlagEmbedding deps
ingestion does (see requirements.txt) — that's a deliberate change from the
Week 1 scaffold, which kept the API image dependency-light since it didn't
need to run any models yet.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.dense import dense_search
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword import keyword_search
from app.retrieval.rerank import rerank
from ingestion.embeddings import embed_chunks


async def retrieve(
    session: AsyncSession,
    query: str,
    language: str | None = None,
    candidate_k: int = 20,
    final_k: int = 5,
) -> list[dict]:
    query_vector = embed_chunks([query])[0]

    dense_results = await dense_search(session, query_vector, language, candidate_k)
    keyword_results = await keyword_search(session, query, language, candidate_k)

    fused = reciprocal_rank_fusion([dense_results, keyword_results])[:candidate_k]
    return rerank(query, fused, top_k=final_k)
