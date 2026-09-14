"""Checkpointed official-source corpus collection, indexing, and verification.

The application database is never a valid target. Every mutating DB operation
is guarded by the ``setu_corpus_staging[_suffix]`` naming convention and a
loopback-only connection configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

# Corpus jobs are local/offline operations; disable optional runtime telemetry
# before importing OpenVINO in index/verification code.
os.environ.setdefault("OPENVINO_TELEMETRY_DISABLED", "1")

from ingestion.corpus_extract import (
    CHUNKING_VERSION,
    EXTRACTION_VERSION,
    chunk_structured_text,
    extract_document,
    validate_extraction,
)
from ingestion.corpus_manifest import (
    PIPELINE_STAGES,
    advance_stage,
    iter_sources,
    load_manifest,
    record_failure,
    refresh_item_stage,
    save_manifest,
    stage_at_least,
    stage_counts,
    utc_now,
)
from ingestion.db_writer import get_pool, write_document
from ingestion.safe_fetch import FetchError, SafeHttpFetcher
from ingestion.staging_db import (
    LocalDatabaseConfig,
    StagingDatabaseError,
    connect_staging,
    drop_staging_database,
    prepare_staging_database,
    staging_metrics,
)


logger = logging.getLogger("setu.corpus")
DEFAULT_MANIFEST = Path("corpus/manifests/batch-001.json")
DEFAULT_STAGE_ROOT = Path("corpus/staging")
DEFAULT_PROGRESS = Path("corpus/progress.json")
DEFAULT_DATABASE = "setu_corpus_staging"
PM_KISAN_GATE_ID = "scheme.central.pm-kisan"


def _gate_item(
    manifest: dict[str, Any], database_name: str
) -> dict[str, Any]:
    """Return the local or prerequisite PM-KISAN gate for this staging DB."""
    if manifest.get("staging_database") != database_name:
        raise ValueError(
            "Manifest staging_database must exactly match --database-name"
        )
    gate = next(
        (item for item in manifest["items"] if item["stable_id"] == PM_KISAN_GATE_ID),
        None,
    )
    if gate is None:
        prerequisite = manifest.get("prerequisite_manifest")
        if not isinstance(prerequisite, str) or not prerequisite.strip():
            raise ValueError(
                f"Manifest must include {PM_KISAN_GATE_ID} or prerequisite_manifest"
            )
        allowed_root = (Path.cwd() / "corpus" / "manifests").resolve()
        prerequisite_path = (Path.cwd() / prerequisite).resolve()
        if allowed_root not in prerequisite_path.parents:
            raise ValueError("prerequisite_manifest must be under corpus/manifests")
        prerequisite_manifest = load_manifest(prerequisite_path)
        if prerequisite_manifest.get("staging_database") != database_name:
            raise ValueError("Prerequisite gate belongs to a different staging database")
        gate = next(
            (
                item
                for item in prerequisite_manifest["items"]
                if item["stable_id"] == PM_KISAN_GATE_ID
            ),
            None,
        )
    if gate is None:
        raise RuntimeError("The prerequisite manifest has no PM-KISAN gate item")
    return gate


def assess_retrieval_check(
    check: dict[str, Any], results: list[dict[str, Any]], expected_urls: set[str]
) -> dict[str, Any]:
    """Assess both source rank and whether the returned passage is useful."""
    source_result = next(
        (
            (rank, result)
            for rank, result in enumerate(results, start=1)
            if result.get("url") in expected_urls
        ),
        None,
    )
    expected_rank = source_result[0] if source_result else None
    markers = [
        marker.casefold() for marker in check.get("expected_passage_markers", [])
    ]
    useful_result = next(
        (
            (rank, result)
            for rank, result in enumerate(results, start=1)
            if result.get("url") in expected_urls
            and markers
            and all(
                marker in str(result.get("content", "")).casefold()
                for marker in markers
            )
        ),
        None,
    )
    expected_content = (
        str(useful_result[1].get("content", "")) if useful_result else ""
    )
    marker_matches = {
        marker: marker in expected_content.casefold() for marker in markers
    }
    passage_passed = bool(markers) and all(marker_matches.values())
    top_score = float(results[0].get("rerank_score", 0.0)) if results else 0.0
    if check.get("expect_no_supported_item"):
        passed = top_score <= float(check.get("max_top_score", 0.5))
        passage_passed = True
    else:
        passed = (
            useful_result is not None
            and useful_result[0] <= int(check.get("expected_rank_max", 5))
            and passage_passed
        )
    return {
        "passed": passed,
        "expected_rank": expected_rank,
        "useful_passage_rank": useful_result[0] if useful_result else None,
        "top_score": top_score,
        "passage_passed": passage_passed,
        "passage_marker_matches": marker_matches,
        "expected_passage_excerpt": expected_content[:500],
    }


def _selected_items(
    manifest: dict[str, Any], item_ids: Iterable[str] | None
) -> list[dict[str, Any]]:
    if not item_ids:
        return [
            item for item in manifest["items"] if item["processing_status"] != "excluded"
        ]
    requested = set(item_ids)
    selected = [item for item in manifest["items"] if item["stable_id"] in requested]
    missing = requested - {item["stable_id"] for item in selected}
    if missing:
        raise ValueError(f"Unknown item IDs: {sorted(missing)}")
    return selected


def _batch_directory(stage_root: Path, manifest: dict[str, Any]) -> Path:
    return stage_root / manifest["batch_id"]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _path_from_record(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _snapshot_suffix(content_type: str, content: bytes) -> str:
    if content.startswith(b"%PDF-") or content_type == "application/pdf":
        return ".pdf"
    if content_type in {"text/html", "application/xhtml+xml"}:
        return ".html"
    return ".txt"


def collect_batch(
    manifest_path: Path,
    stage_root: Path,
    *,
    item_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    policy = manifest["fetch_policy"]
    fetcher = SafeHttpFetcher(
        policy["allowed_hosts"],
        connect_timeout=float(policy.get("connect_timeout_seconds", 5)),
        read_timeout=float(policy.get("read_timeout_seconds", 30)),
        max_bytes=int(policy.get("max_response_bytes", 12 * 1024 * 1024)),
        max_redirects=int(policy.get("max_redirects", 5)),
        retries=int(policy.get("retries", 2)),
        min_host_interval=float(policy.get("min_host_interval_seconds", 1)),
        max_retry_after=float(policy.get("max_retry_after_seconds", 30)),
    )
    batch_dir = _batch_directory(stage_root, manifest)
    seen_hashes = {
        source["extracted_sha256"]: (item["stable_id"], source["source_id"])
        for item, source in iter_sources(manifest)
        if stage_at_least(source["processing_status"], "deduplicated")
        and source.get("extracted_sha256")
    }

    for item in _selected_items(manifest, item_ids):
        for source in item["sources"]:
            try:
                if source["processing_status"] == "discovered":
                    source["attempt_count"] += 1
                    source["last_attempt_at"] = utc_now()
                    save_manifest(manifest_path, manifest)
                    started = time.perf_counter()
                    fetched = fetcher.fetch(source["official_url"])
                    source["fetch_duration_ms"] = round(
                        (time.perf_counter() - started) * 1000, 2
                    )
                    suffix = _snapshot_suffix(fetched.content_type, fetched.content)
                    snapshot = batch_dir / "snapshots" / f"{source['source_id']}{suffix}"
                    _atomic_write_bytes(snapshot, fetched.content)
                    source.update(
                        {
                            "snapshot_path": _relative(snapshot),
                            "final_url": fetched.final_url,
                            "http_status": fetched.status_code,
                            "content_type": fetched.content_type,
                            "content_bytes": len(fetched.content),
                            "content_sha256": hashlib.sha256(fetched.content).hexdigest(),
                            "etag": fetched.etag,
                            "last_modified": fetched.last_modified,
                            "checked_at": utc_now(),
                        }
                    )
                    advance_stage(source, "fetched")
                    save_manifest(manifest_path, manifest)

                if source["processing_status"] == "fetched":
                    snapshot = _path_from_record(source["snapshot_path"])
                    if not snapshot.is_file():
                        raise FileNotFoundError(
                            f"Checkpoint snapshot is missing: {source['snapshot_path']}"
                        )
                    started = time.perf_counter()
                    extracted = extract_document(
                        snapshot.read_bytes(), source["content_type"]
                    )
                    extracted_path = (
                        batch_dir / "extracted" / f"{source['source_id']}.txt"
                    )
                    _atomic_write_text(extracted_path, extracted.text + "\n")
                    source.update(
                        {
                            "extracted_path": _relative(extracted_path),
                            "extracted_title": extracted.title,
                            "extraction_version": EXTRACTION_VERSION,
                            "extraction_duration_ms": round(
                                (time.perf_counter() - started) * 1000, 2
                            ),
                            "extracted_sha256": hashlib.sha256(
                                extracted.text.encode("utf-8")
                            ).hexdigest(),
                            "extracted_characters": len(extracted.text),
                            "extracted_locations": extracted.location_count,
                            "pdf_pages": extracted.page_count,
                        }
                    )
                    advance_stage(source, "extracted")
                    save_manifest(manifest_path, manifest)

                if source["processing_status"] == "extracted":
                    extracted_text = _path_from_record(source["extracted_path"]).read_text(
                        encoding="utf-8"
                    )
                    extracted = extract_document(
                        extracted_text.encode("utf-8"), "text/plain"
                    )
                    metrics = validate_extraction(
                        extracted,
                        source.get("required_markers", []),
                        min_characters=int(source.get("min_extracted_characters", 500)),
                    )
                    source["validation_metrics"] = metrics
                    advance_stage(source, "validated")
                    save_manifest(manifest_path, manifest)

                if source["processing_status"] == "validated":
                    content_hash = source["extracted_sha256"]
                    duplicate = seen_hashes.get(content_hash)
                    if duplicate and duplicate[0] != item["stable_id"]:
                        source["processing_status"] = "excluded"
                        source["exclusion_reason"] = (
                            f"Exact extracted-content duplicate of {duplicate[1]}"
                        )
                        source["retry_eligible"] = False
                    else:
                        seen_hashes[content_hash] = (
                            item["stable_id"],
                            source["source_id"],
                        )
                        source["deduplication_key"] = content_hash
                        advance_stage(source, "deduplicated")
                    save_manifest(manifest_path, manifest)
            except Exception as exc:  # each official source is an independent checkpoint
                retry = bool(getattr(exc, "retry_eligible", False))
                record_failure(source, exc, retry_eligible=retry)
                logger.error(
                    "source_failed item=%s source=%s stage=%s error=%s",
                    item["stable_id"],
                    source["source_id"],
                    source["processing_status"],
                    exc,
                )
                save_manifest(manifest_path, manifest)
            finally:
                refresh_item_stage(item)
                save_manifest(manifest_path, manifest)
    return manifest


async def index_batch(
    manifest_path: Path,
    stage_root: Path,
    database_name: str,
    model_root: Path,
    *,
    item_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    selected = _selected_items(manifest, item_ids)
    gate = _gate_item(manifest, database_name)
    nongate = [item for item in selected if item["stable_id"] != PM_KISAN_GATE_ID]
    if nongate and not stage_at_least(gate["processing_status"], "retrieval_checked"):
        raise RuntimeError(
            "PM-KISAN must pass isolated indexed retrieval before bulk staging"
        )

    config = LocalDatabaseConfig.from_env_file()
    connection = await connect_staging(config, database_name)
    await connection.close()
    from app.retrieval.openvino_backend import OpenVINOEmbeddingModel

    model = OpenVINOEmbeddingModel(model_root / "bge-m3")
    pool = await get_pool(**config.connection_kwargs(database_name))
    batch_dir = _batch_directory(stage_root, manifest)
    try:
        for item in selected:
            for source in item["sources"]:
                try:
                    if source["processing_status"] == "deduplicated":
                        text = _path_from_record(source["extracted_path"]).read_text(
                            encoding="utf-8"
                        )
                        chunks = chunk_structured_text(text)
                        if not chunks:
                            raise RuntimeError("Structure-aware chunking produced no chunks")
                        chunks_path = batch_dir / "chunks" / f"{source['source_id']}.json"
                        _atomic_write_text(
                            chunks_path,
                            json.dumps(chunks, ensure_ascii=False, indent=2) + "\n",
                        )
                        source.update(
                            {
                                "chunks_path": _relative(chunks_path),
                                "chunking_version": CHUNKING_VERSION,
                                "chunk_count": len(chunks),
                            }
                        )
                        advance_stage(source, "chunked")
                        save_manifest(manifest_path, manifest)

                    if source["processing_status"] == "chunked":
                        chunks = json.loads(
                            _path_from_record(source["chunks_path"]).read_text(
                                encoding="utf-8"
                            )
                        )
                        started = time.perf_counter()
                        vectors = np.asarray(
                            model.encode(chunks, batch_size=4), dtype=np.float32
                        )
                        if vectors.shape != (len(chunks), 1024):
                            raise RuntimeError(
                                f"Unexpected embedding shape {vectors.shape}"
                            )
                        embedding_path = (
                            batch_dir / "embeddings" / f"{source['source_id']}.npy"
                        )
                        embedding_path.parent.mkdir(parents=True, exist_ok=True)
                        temporary = embedding_path.with_suffix(".npy.part")
                        with temporary.open("wb") as handle:
                            np.save(handle, vectors, allow_pickle=False)
                        os.replace(temporary, embedding_path)
                        source.update(
                            {
                                "embedding_path": _relative(embedding_path),
                                "embedding_model": "BAAI/bge-m3 OpenVINO FP32",
                                "embedding_dimension": 1024,
                                "embedding_duration_ms": round(
                                    (time.perf_counter() - started) * 1000, 2
                                ),
                                "embedding_bytes": embedding_path.stat().st_size,
                            }
                        )
                        advance_stage(source, "embedded")
                        save_manifest(manifest_path, manifest)

                    if source["processing_status"] == "embedded":
                        chunks = json.loads(
                            _path_from_record(source["chunks_path"]).read_text(
                                encoding="utf-8"
                            )
                        )
                        vectors = np.load(
                            _path_from_record(source["embedding_path"]),
                            allow_pickle=False,
                        ).tolist()
                        text = _path_from_record(source["extracted_path"]).read_text(
                            encoding="utf-8"
                        )
                        metadata = {
                            "corpus_item_id": item["stable_id"],
                            "corpus_source_id": source["source_id"],
                            "item_type": item["item_type"],
                            "jurisdiction": item["jurisdiction"],
                            "document_title": source["document_title"],
                            "document_identifier": source.get("document_identifier"),
                            "publication_date": source.get("publication_date"),
                            "effective_date": source.get("effective_date"),
                            "coverage_scope": source["coverage_scope"],
                            "source_status": source.get("source_status"),
                            "content_sha256": source["content_sha256"],
                            "extracted_sha256": source["extracted_sha256"],
                            "extraction_version": source["extraction_version"],
                            "chunking_version": source["chunking_version"],
                            "official_application_url": item.get(
                                "official_application_url"
                            ),
                            "official_status_url": item.get("official_status_url"),
                            "official_help_url": item.get("official_help_url"),
                        }
                        started = time.perf_counter()
                        document_id = await write_document(
                            pool,
                            source=item["publisher"],
                            title=item["canonical_title"],
                            language=source["language"],
                            url=source["official_url"],
                            raw_text=text,
                            metadata=metadata,
                            chunk_texts=chunks,
                            chunk_embeddings=vectors,
                        )
                        source.update(
                            {
                                "database_document_id": document_id,
                                "index_duration_ms": round(
                                    (time.perf_counter() - started) * 1000, 2
                                ),
                                "staging_database": database_name,
                            }
                        )
                        advance_stage(source, "indexed")
                        save_manifest(manifest_path, manifest)
                except Exception as exc:
                    record_failure(source, exc, retry_eligible=True)
                    logger.error(
                        "index_failed item=%s source=%s stage=%s error=%s",
                        item["stable_id"],
                        source["source_id"],
                        source["processing_status"],
                        exc,
                    )
                    save_manifest(manifest_path, manifest)
                finally:
                    refresh_item_stage(item)
                    save_manifest(manifest_path, manifest)
    finally:
        await pool.close()
    return manifest


def verified_link_metadata(item: dict[str, Any]) -> dict[str, str]:
    """Return only explicitly verified manifest links suitable for serving."""
    fields = (
        "official_application_url",
        "official_status_url",
        "official_help_url",
    )
    return {
        field: value
        for field in fields
        if isinstance((value := item.get(field)), str) and value.strip()
    }


async def sync_verified_links(
    manifest_path: Path, database_name: str
) -> int:
    """Attach verified service links to already-indexed staging documents."""
    manifest = load_manifest(manifest_path)
    _gate_item(manifest, database_name)
    connection = await connect_staging(
        LocalDatabaseConfig.from_env_file(), database_name
    )
    updated = 0
    try:
        async with connection.transaction():
            for item in manifest["items"]:
                if item.get("processing_status") in {"excluded", "quarantined"}:
                    continue
                links = verified_link_metadata(item)
                if not links:
                    continue
                for source in item["sources"]:
                    if not stage_at_least(source["processing_status"], "indexed"):
                        continue
                    result = await connection.execute(
                        """
                        UPDATE documents
                        SET metadata = metadata || $1::jsonb
                        WHERE url = $2
                          AND metadata->>'corpus_item_id' = $3
                        """,
                        json.dumps(links),
                        source["official_url"],
                        item["stable_id"],
                    )
                    if result != "UPDATE 1":
                        raise RuntimeError(
                            "Expected one indexed staging document for "
                            f"{source['source_id']}, got {result}"
                        )
                    updated += 1
    finally:
        await connection.close()
    return updated


async def verify_retrieval(
    manifest_path: Path,
    database_name: str,
    model_root: Path,
    *,
    item_ids: Iterable[str] | None = None,
    include_batch_checks: bool = False,
    batch_checks_only: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    selected = [] if batch_checks_only else _selected_items(manifest, item_ids)
    not_indexed = [
        item["stable_id"]
        for item in selected
        if not stage_at_least(item["processing_status"], "indexed")
    ]
    if not_indexed:
        raise RuntimeError(f"Items are not indexed: {not_indexed}")

    config = LocalDatabaseConfig.from_env_file()
    connection = await connect_staging(config, database_name)
    await connection.close()

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.config import settings
    from app.retrieval import embeddings as embedding_adapter
    from app.retrieval import rerank as rerank_adapter
    from app.retrieval.pipeline import retrieve

    settings.local_inference_backend = "openvino"
    settings.openvino_model_dir = str(model_root.resolve())
    embedding_adapter._openvino_model = None
    rerank_adapter._reranker = None
    engine = create_async_engine(
        config.sqlalchemy_url(database_name),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )

    async def execute_check(
        session: AsyncSession, check: dict[str, Any], expected_urls: set[str]
    ) -> bool:
        started = time.perf_counter()
        results = await retrieve(
            session,
            check["query"],
            language=None,
            candidate_k=20,
            final_k=5,
        )
        assessment = assess_retrieval_check(check, results, expected_urls)
        passed = assessment.pop("passed")
        check.update(
            {
                "status": "passed" if passed else "failed",
                "checked_at": utc_now(),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                **assessment,
                "results": [
                    {
                        "rank": rank,
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "language": result.get("language"),
                        "rerank_score": float(result.get("rerank_score", 0.0)),
                        "content_excerpt": str(result.get("content", ""))[:300],
                    }
                    for rank, result in enumerate(results, start=1)
                ],
            }
        )
        return passed

    try:
        async with AsyncSession(engine) as session:
            for item in selected:
                expected_urls = {source["official_url"] for source in item["sources"]}
                passed = []
                for check in item.get("retrieval_checks", []):
                    try:
                        passed.append(await execute_check(session, check, expected_urls))
                    except Exception as exc:
                        check.update(
                            {
                                "status": "error",
                                "checked_at": utc_now(),
                                "last_error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                        passed.append(False)
                    save_manifest(manifest_path, manifest)
                if passed and all(passed):
                    for source in item["sources"]:
                        if source["processing_status"] == "indexed":
                            advance_stage(source, "retrieval_checked")
                    refresh_item_stage(item)
                else:
                    item["last_error"] = "One or more retrieval checks did not pass"
                    item["retry_eligible"] = True
                save_manifest(manifest_path, manifest)

            if include_batch_checks:
                all_urls = {
                    item["stable_id"]: {source["official_url"] for source in item["sources"]}
                    for item in manifest["items"]
                }
                for check in manifest.get("batch_retrieval_checks", []):
                    expected_urls = all_urls.get(check.get("expected_item_id"), set())
                    try:
                        await execute_check(session, check, expected_urls)
                    except Exception as exc:
                        check.update(
                            {
                                "status": "error",
                                "checked_at": utc_now(),
                                "last_error": f"{type(exc).__name__}: {exc}",
                            }
                        )
                    save_manifest(manifest_path, manifest)
    finally:
        await engine.dispose()
    return manifest


def document_stage_counts(manifest: dict[str, Any]) -> dict[str, int]:
    sources = [source for _, source in iter_sources(manifest)]
    return {
        stage: sum(stage_at_least(source["processing_status"], stage) for source in sources)
        for stage in PIPELINE_STAGES
    } | {"excluded": sum(source["processing_status"] == "excluded" for source in sources)}


def write_progress(
    path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    database_name: str,
    *,
    operation: str,
    running: bool,
    database_evidence: dict[str, Any] | None = None,
) -> None:
    failures = [
        {
            "item_id": item["stable_id"],
            "source_id": source["source_id"],
            "stage": source["processing_status"],
            "last_error": source.get("last_error"),
            "retry_eligible": source.get("retry_eligible", False),
        }
        for item, source in iter_sources(manifest)
        if source.get("last_error")
    ]
    progress = {
        "updated_at": utc_now(),
        "batch_id": manifest["batch_id"],
        "manifest_path": _relative(manifest_path),
        "staging_database": database_name,
        "application_database_baseline": {
            "documents": 8,
            "chunks": 239,
            "eligibility_criteria": 3,
            "verified_read_only_at": manifest.get("application_baseline_verified_at"),
        },
        "process": {
            "running": running,
            "pid": os.getpid() if running else None,
            "operation": operation,
        },
        "distinct_item_stage_counts": stage_counts(manifest),
        "source_document_stage_counts": document_stage_counts(manifest),
        "completed_item_ids": [
            item["stable_id"]
            for item in manifest["items"]
            if stage_at_least(item["processing_status"], "retrieval_checked")
        ],
        "pending_item_ids": [
            item["stable_id"]
            for item in manifest["items"]
            if not stage_at_least(item["processing_status"], "retrieval_checked")
            and item["processing_status"] != "excluded"
        ],
        "failures": failures,
        "database_evidence": database_evidence,
        "exact_resume_command": _next_command(manifest, manifest_path, database_name),
        "next_action": _next_action(manifest),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(path, json.dumps(progress, ensure_ascii=False, indent=2) + "\n")


def _next_action(manifest: dict[str, Any]) -> str:
    counts = stage_counts(manifest)
    total = sum(
        item["processing_status"] != "excluded" for item in manifest["items"]
    )
    if counts["deduplicated"] < total:
        return "Resume collect for sources not yet deduplicated."
    gate = _gate_item(manifest, manifest["staging_database"])
    if not stage_at_least(gate["processing_status"], "indexed"):
        return "Index only the PM-KISAN gate item in isolated staging."
    if not stage_at_least(gate["processing_status"], "retrieval_checked"):
        return "Run PM-KISAN multilingual retrieval verification."
    if counts["indexed"] < total:
        return "Index the remaining validated batch after the PM-KISAN gate."
    if counts["retrieval_checked"] < total:
        return "Run per-item and batch retrieval checks."
    return "Review batch evidence and prepare the next bounded batch."


def _next_command(
    manifest: dict[str, Any], manifest_path: Path, database_name: str
) -> str:
    prefix = (
        ".\\.venv-ingest\\Scripts\\python.exe -m ingestion.corpus_pipeline "
        f"--manifest {manifest_path.as_posix()} --database-name {database_name}"
    )
    counts = stage_counts(manifest)
    total = sum(
        item["processing_status"] != "excluded" for item in manifest["items"]
    )
    if counts["deduplicated"] < total:
        return f"{prefix} collect"
    gate = _gate_item(manifest, database_name)
    if not stage_at_least(gate["processing_status"], "indexed"):
        return f"{prefix} index --item-id {PM_KISAN_GATE_ID}"
    if not stage_at_least(gate["processing_status"], "retrieval_checked"):
        return f"{prefix} verify --item-id {PM_KISAN_GATE_ID}"
    if counts["indexed"] < total:
        return f"{prefix} index"
    if counts["retrieval_checked"] < total:
        return f"{prefix} verify --include-batch-checks"
    return f"{prefix} status"


async def _database_evidence_if_available(
    database_name: str,
) -> dict[str, Any] | None:
    try:
        return await staging_metrics(LocalDatabaseConfig.from_env_file(), database_name)
    except Exception:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SETU isolated corpus expansion")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--stage-root", type=Path, default=DEFAULT_STAGE_ROOT)
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    parser.add_argument("--database-name", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--model-root", type=Path, default=Path("models/openvino")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("prepare-db")
    subparsers.add_parser("sync-verified-links")
    collect = subparsers.add_parser("collect")
    collect.add_argument("--item-id", action="append", dest="item_ids")
    index = subparsers.add_parser("index")
    index.add_argument("--item-id", action="append", dest="item_ids")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--item-id", action="append", dest="item_ids")
    verify.add_argument("--include-batch-checks", action="store_true")
    verify.add_argument("--batch-checks-only", action="store_true")
    rollback = subparsers.add_parser("rollback-staging")
    rollback.add_argument("--confirm-database-name", required=True)
    return parser


async def async_main(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    write_progress(
        args.progress,
        args.manifest,
        manifest,
        args.database_name,
        operation=args.command,
        running=True,
    )
    database_evidence: dict[str, Any] | None = None
    try:
        if args.command == "prepare-db":
            database_evidence = await prepare_staging_database(
                LocalDatabaseConfig.from_env_file(), args.database_name
            )
        elif args.command == "collect":
            manifest = await asyncio.to_thread(
                collect_batch,
                args.manifest,
                args.stage_root,
                item_ids=args.item_ids,
            )
        elif args.command == "index":
            manifest = await index_batch(
                args.manifest,
                args.stage_root,
                args.database_name,
                args.model_root,
                item_ids=args.item_ids,
            )
        elif args.command == "sync-verified-links":
            updated = await sync_verified_links(
                args.manifest, args.database_name
            )
            logger.info("verified_links_synced documents=%s", updated)
        elif args.command == "verify":
            manifest = await verify_retrieval(
                args.manifest,
                args.database_name,
                args.model_root,
                item_ids=args.item_ids,
                include_batch_checks=(
                    args.include_batch_checks or args.batch_checks_only
                ),
                batch_checks_only=args.batch_checks_only,
            )
        elif args.command == "rollback-staging":
            await drop_staging_database(
                LocalDatabaseConfig.from_env_file(),
                args.database_name,
                confirmation=args.confirm_database_name,
            )
        elif args.command != "status":
            raise ValueError(f"Unsupported command: {args.command}")
        manifest = load_manifest(args.manifest)
        if database_evidence is None:
            database_evidence = await _database_evidence_if_available(args.database_name)
        print(
            json.dumps(
                {
                    "batch_id": manifest["batch_id"],
                    "distinct_items": stage_counts(manifest),
                    "source_documents": document_stage_counts(manifest),
                    "staging": database_evidence,
                    "next_action": _next_action(manifest),
                },
                indent=2,
            )
        )
        return 0
    finally:
        manifest = load_manifest(args.manifest)
        if database_evidence is None:
            database_evidence = await _database_evidence_if_available(args.database_name)
        write_progress(
            args.progress,
            args.manifest,
            manifest,
            args.database_name,
            operation=args.command,
            running=False,
            database_evidence=database_evidence,
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(async_main(args)))
    except (StagingDatabaseError, FetchError, ValueError, RuntimeError) as exc:
        logger.error("corpus_pipeline_failed error=%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
