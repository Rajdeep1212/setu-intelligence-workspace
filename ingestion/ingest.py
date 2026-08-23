"""
Ingestion pipeline — Week 1.

Fetches a curated list of PIB press releases (English + auto-discovered
Hindi/Bengali translations), chunks them language-aware, embeds the chunks
with bge-m3, and writes everything to Postgres/pgvector.

Usage:
    python -m ingestion.ingest --prids 2235812,2224505,2206477

Where to get PRIDs: browse pib.gov.in, open a release, the PRID is the
number in the URL (?PRID=2235812) and also shown as "(Release ID: ...)" at
the bottom of the article. Pick ~20-30 releases across a few ministries for
the Week 1 MVP — myScheme.gov.in documents can be added the same way once
you've inspected that site's page structure (it wasn't covered by this
scaffold; expect it to need its own small scraper module similar to
scraper.py, since it's a different site template).
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from ingestion.chunking import chunk_text
from ingestion.db_writer import get_pool, write_document
from ingestion.embeddings import embed_chunks
from ingestion.scraper import load_documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")


async def run(prids: list[str], languages: tuple[str, ...]) -> None:
    logger.info("Fetching %d PRID(s), languages=%s", len(prids), languages)
    raw_documents = load_documents(prids, languages=languages)
    logger.info("Fetched %d document(s) (including translations)", len(raw_documents))

    pool = await get_pool()
    try:
        for doc in raw_documents:
            try:
                chunks = chunk_text(doc.raw_text, language=doc.language)
                if not chunks:
                    logger.warning("No chunks produced for PRID=%s (%s) — skipping", doc.prid, doc.language)
                    continue

                vectors = embed_chunks(chunks)

                document_id = await write_document(
                    pool,
                    source="PIB",
                    title=doc.title,
                    language=doc.language,
                    url=doc.url,
                    raw_text=doc.raw_text,
                    metadata={"prid": doc.prid, "posted_on": doc.posted_on},
                    chunk_texts=chunks,
                    chunk_embeddings=vectors,
                )
                logger.info(
                    "Wrote PRID=%s lang=%s -> document_id=%s (%d chunks)",
                    doc.prid, doc.language, document_id, len(chunks),
                )
            except Exception as e:
                logger.error("Failed to process PRID=%s lang=%s: %s", doc.prid, doc.language, str(e))
                continue
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Setu Week 1 ingestion pipeline")
    parser.add_argument(
        "--prids",
        required=True,
        help="Comma-separated PIB Release IDs, e.g. 2235812,2224505",
    )
    parser.add_argument(
        "--languages",
        default="en,hi,bn",
        help="Comma-separated language codes to keep (default: en,hi,bn)",
    )
    args = parser.parse_args()

    prids = [p.strip() for p in args.prids.split(",") if p.strip()]
    languages = tuple(l.strip() for l in args.languages.split(",") if l.strip())

    asyncio.run(run(prids, languages))


if __name__ == "__main__":
    main()
