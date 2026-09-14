"""Read-only application/staging isolation and verified-link audit."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from urllib.parse import urlparse

import asyncpg

from ingestion.staging_db import (
    LocalDatabaseConfig,
    assert_staging_database_name,
    connect_staging,
)


TABLES = ("documents", "chunks", "eligibility_criteria")
LINK_FIELDS = (
    "official_application_url",
    "official_status_url",
    "official_help_url",
)


async def _audit_connection(connection: asyncpg.Connection) -> dict[str, Any]:
    async with connection.transaction(readonly=True):
        counts = {
            table: await connection.fetchval(f"SELECT count(*) FROM {table}")
            for table in TABLES
        }
        corpus_documents = await connection.fetchval(
            "SELECT count(*) FROM documents WHERE metadata ? 'corpus_item_id'"
        )
        duplicate_urls = await connection.fetchval(
            """
            SELECT count(*) FROM (
                SELECT url FROM documents WHERE url IS NOT NULL
                GROUP BY url HAVING count(*) > 1
            ) duplicates
            """
        )
        duplicate_chunk_positions = await connection.fetchval(
            """
            SELECT count(*) FROM (
                SELECT document_id, chunk_index FROM chunks
                GROUP BY document_id, chunk_index HAVING count(*) > 1
            ) duplicates
            """
        )
        link_rows = await connection.fetch(
            """
            SELECT id::text AS document_id, metadata
            FROM documents
            WHERE metadata ?| $1::text[]
            """,
            list(LINK_FIELDS),
        )

    links: list[dict[str, str]] = []
    invalid_links: list[dict[str, str]] = []
    for row in link_rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        for field in LINK_FIELDS:
            value = metadata.get(field) if isinstance(metadata, dict) else None
            if not isinstance(value, str):
                continue
            record = {
                "document_id": row["document_id"],
                "corpus_item_id": str(metadata.get("corpus_item_id", "")),
                "kind": field,
                "url": value,
            }
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                links.append(record)
            else:
                invalid_links.append(record)
    return {
        "counts": counts,
        "corpus_documents": corpus_documents,
        "duplicate_document_urls": duplicate_urls,
        "duplicate_chunk_positions": duplicate_chunk_positions,
        "verified_service_links": len(links),
        "service_links": links,
        "invalid_service_links": invalid_links,
    }


async def run(database_name: str) -> dict[str, Any]:
    assert_staging_database_name(database_name)
    config = LocalDatabaseConfig.from_env_file()
    application = await asyncpg.connect(**config.connection_kwargs("setu"))
    staging = await connect_staging(config, database_name)
    try:
        return {
            "application": await _audit_connection(application),
            "staging": await _audit_connection(staging),
            "application_unchanged_from_baseline": False,
            "staging_matches_checkpoint": False,
        }
    finally:
        await application.close()
        await staging.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-name", default="setu_corpus_staging")
    args = parser.parse_args()
    result = asyncio.run(run(args.database_name))
    result["application_unchanged_from_baseline"] = result["application"]["counts"] == {
        "documents": 8,
        "chunks": 239,
        "eligibility_criteria": 3,
    }
    result["staging_matches_checkpoint"] = result["staging"]["counts"] == {
        "documents": 26,
        "chunks": 331,
        "eligibility_criteria": 0,
    }
    print(json.dumps(result, indent=2))
    return 0 if (
        result["application_unchanged_from_baseline"]
        and result["staging_matches_checkpoint"]
        and result["application"]["corpus_documents"] == 0
        and result["staging"]["duplicate_document_urls"] == 0
        and result["staging"]["duplicate_chunk_positions"] == 0
        and not result["staging"]["invalid_service_links"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
