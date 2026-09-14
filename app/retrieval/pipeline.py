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

import asyncio
import logging
import time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import DatabaseUnavailableError, RetrievalUnavailableError
from app.observability import get_request_id
from app.retrieval.dense import dense_search
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword import keyword_search
from app.retrieval.rerank import rerank
from app.retrieval.embeddings import embed_chunks


logger = logging.getLogger(__name__)


async def retrieve(
    session: AsyncSession,
    query: str,
    language: str | None = None,
    candidate_k: int = 20,
    final_k: int = 5,
) -> list[dict]:
    total_started = time.perf_counter()
    try:
        stage_started = time.perf_counter()
        query_vector = (await asyncio.to_thread(embed_chunks, [query]))[0]
        embedding_ms = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()
        dense_results = await dense_search(session, query_vector, language, candidate_k)
        dense_ms = (time.perf_counter() - stage_started) * 1000
        stage_started = time.perf_counter()
        keyword_results = await keyword_search(session, query, language, candidate_k)
        keyword_ms = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()
        await session.rollback()
        database_release_ms = (time.perf_counter() - stage_started) * 1000

        stage_started = time.perf_counter()
        fused = reciprocal_rank_fusion([dense_results, keyword_results])[:candidate_k]
        fusion_ms = (time.perf_counter() - stage_started) * 1000
        stage_started = time.perf_counter()
        ranked = await asyncio.to_thread(rerank, query, fused, top_k=final_k)
        rerank_ms = (time.perf_counter() - stage_started) * 1000
        logger.info(
            "retrieval_profile request_id=%s query_characters=%s candidate_limit=%s "
            "dense_count=%s keyword_count=%s fused_count=%s final_count=%s "
            "embedding_ms=%.2f dense_ms=%.2f keyword_ms=%.2f "
            "database_release_ms=%.2f fusion_ms=%.2f rerank_ms=%.2f total_ms=%.2f",
            get_request_id(),
            len(query),
            candidate_k,
            len(dense_results),
            len(keyword_results),
            len(fused),
            len(ranked),
            embedding_ms,
            dense_ms,
            keyword_ms,
            database_release_ms,
            fusion_ms,
            rerank_ms,
            (time.perf_counter() - total_started) * 1000,
        )
        return ranked
    except SQLAlchemyError as exc:
        logger.error("retrieval_database_failure request_id=%s", get_request_id())
        raise DatabaseUnavailableError() from exc
    except (DatabaseUnavailableError, RetrievalUnavailableError):
        raise
    except Exception as exc:
        logger.error(
            "retrieval_failure request_id=%s error_type=%s",
            get_request_id(),
            type(exc).__name__,
        )
        raise RetrievalUnavailableError() from exc
