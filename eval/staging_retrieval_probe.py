"""Read-only hybrid retrieval probe against the isolated local staging DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from ingestion.staging_db import LocalDatabaseConfig, assert_staging_database_name


os.environ.setdefault("OPENVINO_TELEMETRY_DISABLED", "1")
LINK_FIELDS = (
    "official_application_url",
    "official_status_url",
    "official_help_url",
)


async def run(query: str, database_name: str) -> list[dict]:
    assert_staging_database_name(database_name)
    settings.local_inference_backend = "openvino"
    settings.openvino_model_dir = str(Path("models/openvino").resolve())
    from app.retrieval.pipeline import retrieve

    config = LocalDatabaseConfig.from_env_file()
    engine = create_async_engine(config.sqlalchemy_url(database_name))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            results = await retrieve(session, query, language=None)
    finally:
        await engine.dispose()

    safe_results = []
    for rank, result in enumerate(results, start=1):
        metadata = result.get("document_metadata")
        links = {
            field: metadata[field]
            for field in LINK_FIELDS
            if isinstance(metadata, dict) and isinstance(metadata.get(field), str)
        }
        safe_results.append(
            {
                "rank": rank,
                "chunk_id": str(result["id"]),
                "document_id": str(result["document_id"]),
                "title": result.get("title"),
                "source_url": result.get("url"),
                "language": result.get("language"),
                "rerank_score": result.get("rerank_score"),
                "passage_excerpt": str(result.get("content", ""))[:320],
                "verified_service_links": links,
            }
        )
    return safe_results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--database-name", default="setu_corpus_staging")
    args = parser.parse_args()
    result = asyncio.run(run(args.query, args.database_name))
    print(
        json.dumps(
            {
                "query": args.query,
                "database": args.database_name,
                "provider_calls": 0,
                "results": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
