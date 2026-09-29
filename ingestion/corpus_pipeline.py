"""Scheme corpus pipeline (M2.1): collect, validate, index into a staging database.

    python -m ingestion.corpus_pipeline --manifest corpus/manifests/batch-001.json status
    python -m ingestion.corpus_pipeline prepare-db
    python -m ingestion.corpus_pipeline --manifest ... collect [--item-id ID ...]
    python -m ingestion.corpus_pipeline --manifest ... index [--item-id ID ...]
    python -m ingestion.corpus_pipeline --manifest ... verify [--item-id ID ...]
    python -m ingestion.corpus_pipeline rollback-staging --confirm-database-name setu_corpus_staging

collect   fetches each active source with the safe fetcher, stores the bytes
          and extracted text under corpus/staging/<batch>/, and compares them
          with the manifest pin. A source that no longer matches is held as
          ``changed``: a person must re-read it and update the pin. Sources
          that match are checked for their required markers and size.
index     chunks and embeds validated sources and writes them through
          ingestion.db_writer.write_document with jurisdiction, effective
          dates, source hash and retrieval time (migration 0001). Re-indexing
          a URL with new content archives the old row (migration 0002).
verify    runs the manifest's retrieval checks against the staging database
          and writes the results to corpus/staging/<batch>/retrieval.json.

Only a database named setu_corpus_staging[_suffix] on a loopback address is
ever written; see ingestion/staging_db.py. The reviewed manifest is only read.
Nothing here decides eligibility: the corpus holds official text, and SETU's
eligibility answers stay switched off (docs/PROGRESS.md, item E2).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from ingestion.corpus_extract import (
    CHUNKING_VERSION,
    EXTRACTION_VERSION,
    chunk_structured_text,
    extract_document,
    text_fingerprint,
    validate_extraction,
)
from ingestion.corpus_manifest import (
    SERVICE_LINK_FIELDS,
    iter_active_sources,
    load_manifest,
    parse_date,
)
from ingestion.corpus_state import RunState, utc_now

logger = logging.getLogger("setu.corpus")
DEFAULT_MANIFEST = Path("corpus/manifests/batch-001.json")
DEFAULT_STAGE_ROOT = Path("corpus/staging")
DEFAULT_DATABASE = "setu_corpus_staging"
EMBEDDING_DIMENSION = 1024


def _state(manifest: dict[str, Any], stage_root: Path) -> RunState:
    return RunState.load(stage_root / manifest["batch_id"] / "state.json", manifest["batch_id"])


def _selected(manifest: dict[str, Any], item_ids: Iterable[str] | None) -> list[tuple[dict, dict]]:
    active = list(iter_active_sources(manifest))
    if not item_ids:
        return active
    requested = set(item_ids)
    known = {item["stable_id"] for item in manifest["items"]}
    if requested - known:
        raise ValueError(f"Unknown item ids: {sorted(requested - known)}")
    return [(item, source) for item, source in active if item["stable_id"] in requested]


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _suffix(content_type: str, content: bytes) -> str:
    if content.startswith(b"%PDF-") or content_type == "application/pdf":
        return ".pdf"
    if content_type in {"text/html", "application/xhtml+xml"}:
        return ".html"
    return ".txt"


def _pin_matches(pin: dict[str, Any], content_sha256: str, text: str) -> bool:
    if pin["watch"] == "bytes":
        return content_sha256 == pin["sha256"]
    return text_fingerprint(text, pin.get("ignore_lines", [])) == pin["text_sha256"]


def default_fetcher(manifest: dict[str, Any]):
    from ingestion.safe_fetch import SafeHttpFetcher

    policy = manifest["fetch_policy"]
    return SafeHttpFetcher(
        policy["allowed_hosts"],
        connect_timeout=float(policy.get("connect_timeout_seconds", 10)),
        read_timeout=float(policy.get("read_timeout_seconds", 30)),
        max_bytes=int(policy.get("max_response_bytes", 12 * 1024 * 1024)),
        max_redirects=int(policy.get("max_redirects", 5)),
        retries=int(policy.get("retries", 2)),
        min_host_interval=float(policy.get("min_host_interval_seconds", 1)),
        max_retry_after=float(policy.get("max_retry_after_seconds", 30)),
    )


def collect_batch(
    manifest_path: Path,
    stage_root: Path,
    *,
    fetcher=None,
    item_ids: Iterable[str] | None = None,
) -> RunState:
    manifest = load_manifest(manifest_path)
    fetcher = fetcher or default_fetcher(manifest)
    state = _state(manifest, stage_root)
    batch_dir = stage_root / manifest["batch_id"]

    for item, source in _selected(manifest, item_ids):
        source_id = source["source_id"]
        record = state.source(source_id)
        pin_key = json.dumps(source["pin"], sort_keys=True)
        # Collect again when the pin was re-reviewed or the last run stopped short.
        if record.get("pin") == pin_key and state.at_least(source_id, "validated"):
            continue
        record = state.reset(source_id)
        record["pin"] = pin_key
        record["attempts"] += 1
        try:
            started = time.perf_counter()
            fetched = fetcher.fetch(source["official_url"])
            retrieved_at = utc_now()
            snapshot = batch_dir / "snapshots" / f"{source_id}{_suffix(fetched.content_type, fetched.content)}"
            _write_atomic(snapshot, fetched.content)
            record.update(
                {
                    "snapshot": snapshot.relative_to(stage_root).as_posix(),
                    "final_url": fetched.final_url,
                    "content_type": fetched.content_type,
                    "content_bytes": len(fetched.content),
                    "content_sha256": _sha256(fetched.content),
                    "retrieved_at": retrieved_at,
                    "fetch_ms": round((time.perf_counter() - started) * 1000),
                }
            )
            state.advance(source_id, "fetched")

            extracted = extract_document(fetched.content, fetched.content_type)
            extracted_path = batch_dir / "extracted" / f"{source_id}.txt"
            _write_atomic(extracted_path, (extracted.text + "\n").encode("utf-8"))
            record.update(
                {
                    "extracted": extracted_path.relative_to(stage_root).as_posix(),
                    "extraction_version": EXTRACTION_VERSION,
                    "extracted_characters": len(extracted.text),
                    "pdf_pages": extracted.page_count,
                }
            )
            record["pin_matches"] = _pin_matches(source["pin"], record["content_sha256"], extracted.text)
            if not record["pin_matches"]:
                state.hold_changed(
                    source_id,
                    f"Content differs from the pin reviewed at {source['pin']['retrieved_at']} "
                    f"(watched on {source['pin']['watch']}); re-read the source, then update the pin in the manifest",
                )
                logger.warning("source_changed source=%s", source_id)
                continue
            state.advance(source_id, "extracted")

            record["validation"] = validate_extraction(
                extracted,
                source.get("required_markers", []),
                min_characters=source.get("min_extracted_characters", 500),
            )
            state.advance(source_id, "validated")
        except Exception as exc:  # each source is an independent checkpoint
            state.fail(source_id, exc)
            logger.error("collect_failed source=%s stage=%s error=%s", source_id, record["stage"], exc)
        finally:
            state.save()
    state.save()
    return state


def _default_embed(chunks: list[str]) -> list[list[float]]:
    # The app's adapter, so documents and questions use the same model and backend.
    from app.retrieval.embeddings import embed_chunks

    return embed_chunks(chunks, batch_size=4)


def _metadata(manifest: dict[str, Any], item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "corpus_batch_id": manifest["batch_id"],
        "corpus_item_id": item["stable_id"],
        "corpus_source_id": source["source_id"],
        "item_type": item["item_type"],
        "category": item["category"],
        "scheme_title": item["canonical_title"],
        "document_identifier": source.get("document_identifier"),
        "source_type": source["source_type"],
        "publication_date": source.get("publication_date"),
        "updated_date": source.get("updated_date"),
        "source_status": source["source_status"],
        "coverage_scope": source["coverage_scope"],
        "status_as_of": item["status_as_of"],
        "extraction_version": EXTRACTION_VERSION,
        "chunking_version": CHUNKING_VERSION,
    }
    metadata.update({field: item[field] for field in SERVICE_LINK_FIELDS if item.get(field)})
    return metadata


async def index_batch(
    manifest_path: Path,
    stage_root: Path,
    *,
    pool,
    embed: Callable[[list[str]], list[list[float]]] | None = None,
    writer: Callable[..., Awaitable[str]] | None = None,
    item_ids: Iterable[str] | None = None,
) -> RunState:
    if writer is None:
        from ingestion.db_writer import write_document as writer
    embed = embed or _default_embed
    manifest = load_manifest(manifest_path)
    state = _state(manifest, stage_root)

    for item, source in _selected(manifest, item_ids):
        source_id = source["source_id"]
        record = state.source(source_id)
        if not state.at_least(source_id, "validated") or state.at_least(source_id, "indexed"):
            continue
        try:
            text = (stage_root / record["extracted"]).read_text(encoding="utf-8")
            chunks = chunk_structured_text(text)
            if not chunks:
                raise RuntimeError("Structure-aware chunking produced no chunks")
            record.update({"chunk_count": len(chunks), "chunking_version": CHUNKING_VERSION})
            state.advance(source_id, "chunked")

            vectors = await asyncio.to_thread(embed, chunks)
            if len(vectors) != len(chunks) or any(len(v) != EMBEDDING_DIMENSION for v in vectors):
                raise RuntimeError(f"Expected {len(chunks)} embeddings of dimension {EMBEDDING_DIMENSION}")
            document_id = await writer(
                pool,
                source=source["publisher"],
                title=source["document_title"],
                language=source["language"],
                url=source["official_url"],
                raw_text=text,
                metadata=_metadata(manifest, item, source),
                chunk_texts=chunks,
                chunk_embeddings=[list(map(float, v)) for v in vectors],
                jurisdiction=source["jurisdiction"],
                effective_from=parse_date(source.get("effective_from")),
                effective_to=parse_date(source.get("effective_to")),
                source_hash=record["content_sha256"],
                retrieved_at=datetime.fromisoformat(record["retrieved_at"].replace("Z", "+00:00")),
            )
            record["document_id"] = str(document_id)
            state.advance(source_id, "embedded")
            state.advance(source_id, "indexed")
        except Exception as exc:
            state.fail(source_id, exc)
            logger.error("index_failed source=%s stage=%s error=%s", source_id, record["stage"], exc)
        finally:
            state.save()
    state.save()
    return state


def assess_retrieval_check(check: dict[str, Any], results: list[dict[str, Any]], expected_urls: set[str]) -> dict[str, Any]:
    """Pass only when an expected source ranks high enough with a passage holding every marker.

    A check without markers is decided by the expected source's rank alone.
    """
    top_score = float(results[0].get("rerank_score", 0.0)) if results else 0.0
    if check.get("expect_no_supported_item"):
        return {"passed": top_score <= float(check.get("max_top_score", 0.5)), "top_score": top_score}
    markers = [marker.casefold() for marker in check.get("expected_passage_markers", [])]
    source_rank = next((rank for rank, r in enumerate(results, 1) if r.get("url") in expected_urls), None)
    useful_rank = next(
        (
            rank
            for rank, r in enumerate(results, 1)
            if r.get("url") in expected_urls and all(m in str(r.get("content", "")).casefold() for m in markers)
        ),
        None,
    )
    passed = useful_rank is not None and useful_rank <= int(check.get("expected_rank_max", 5))
    return {"passed": passed, "source_rank": source_rank, "useful_passage_rank": useful_rank, "top_score": top_score}


async def verify_retrieval(manifest_path: Path, stage_root: Path, database_name: str, *, item_ids=None) -> dict[str, Any]:
    from sqlalchemy import URL
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.retrieval.pipeline import retrieve
    from ingestion.staging_db import LocalDatabaseConfig, connect_staging

    manifest = load_manifest(manifest_path)
    config = LocalDatabaseConfig.from_env_file()
    await (await connect_staging(config, database_name)).close()
    engine = create_async_engine(
        URL.create("postgresql+asyncpg", username=config.user, password=config.password,
                   host=config.host, port=config.port, database=database_name),
        pool_size=1,
        max_overflow=0,
    )
    wanted = set(item_ids or [])
    checks = []
    for item in manifest["items"]:
        if item.get("excluded") or (wanted and item["stable_id"] not in wanted):
            continue
        urls = {s["official_url"] for s in item["sources"] if not s.get("excluded")}
        checks += [(check, urls) for check in item.get("retrieval_checks", [])]
    if not wanted:
        by_item = {i["stable_id"]: {s["official_url"] for s in i["sources"]} for i in manifest["items"]}
        checks += [(c, by_item.get(c.get("expected_item_id"), set())) for c in manifest.get("batch_retrieval_checks", [])]
    report = {"batch_id": manifest["batch_id"], "checked_at": utc_now(), "checks": []}
    try:
        async with AsyncSession(engine) as session:
            for check, urls in checks:
                started = time.perf_counter()
                try:
                    results = await retrieve(session, check["query"], language=None, candidate_k=20, final_k=5)
                    outcome = assess_retrieval_check(check, results, urls)
                    outcome["results"] = [
                        {"rank": n, "url": r.get("url"), "score": float(r.get("rerank_score", 0.0)),
                         "excerpt": str(r.get("content", ""))[:300]}
                        for n, r in enumerate(results, 1)
                    ]
                except Exception as exc:
                    outcome = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
                outcome.update(check_id=check["check_id"], latency_ms=round((time.perf_counter() - started) * 1000))
                report["checks"].append(outcome)
    finally:
        await engine.dispose()
    report["passed"] = sum(c["passed"] for c in report["checks"])
    _write_atomic(
        stage_root / manifest["batch_id"] / "retrieval.json",
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return report


def _sha256(content: bytes) -> str:
    from ingestion.provenance import source_fingerprint

    return source_fingerprint(content)


def status(manifest_path: Path, stage_root: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    state = _state(manifest, stage_root)
    active = [source["source_id"] for _, source in iter_active_sources(manifest)]
    for source_id in active:
        state.source(source_id)
    return {
        "batch_id": manifest["batch_id"],
        "items": len(manifest["items"]),
        "excluded_items": sum(bool(item.get("excluded")) for item in manifest["items"]),
        "active_sources": len(active),
        "stages": state.counts(),
        "needs_attention": {
            sid: state.sources[sid]["last_error"] for sid in active if state.sources[sid].get("last_error")
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SETU scheme corpus pipeline (staging database only)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--database-name", default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("prepare-db")
    for name in ("collect", "index", "verify"):
        commands.add_parser(name).add_argument("--item-id", action="append", dest="item_ids")
    commands.add_parser("rollback-staging").add_argument("--confirm-database-name", required=True)
    return parser


async def async_main(args: argparse.Namespace) -> dict[str, Any]:
    from ingestion import staging_db

    config = lambda: staging_db.LocalDatabaseConfig.from_env_file()  # noqa: E731 - read .env only when needed
    if args.command == "prepare-db":
        return await staging_db.prepare_staging_database(config(), args.database_name)
    if args.command == "rollback-staging":
        await staging_db.drop_staging_database(config(), args.database_name, confirmation=args.confirm_database_name)
        return {"dropped": args.database_name}
    if args.command == "collect":
        await asyncio.to_thread(collect_batch, args.manifest, args.stage_root, item_ids=args.item_ids)
    elif args.command == "index":
        pool = await staging_db.staging_pool(config(), args.database_name)
        try:
            await index_batch(args.manifest, args.stage_root, pool=pool, item_ids=args.item_ids)
        finally:
            await pool.close()
    elif args.command == "verify":
        report = await verify_retrieval(args.manifest, args.stage_root, args.database_name, item_ids=args.item_ids)
        return {"passed": report["passed"], "checks": len(report["checks"])}
    return status(args.manifest, args.stage_root)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(asyncio.run(async_main(args)), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError) as exc:
        logger.error("corpus_pipeline_failed error=%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
