"""Validated, resumable manifest primitives for SETU corpus expansion."""

from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


MANIFEST_SCHEMA_VERSION = 1
PIPELINE_STAGES = (
    "discovered",
    "fetched",
    "extracted",
    "validated",
    "deduplicated",
    "chunked",
    "embedded",
    "indexed",
    "retrieval_checked",
)
TERMINAL_STATUSES = {"excluded"}
_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class ManifestError(ValueError):
    """Raised when a corpus manifest is unsafe or internally inconsistent."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read manifest {manifest_path}: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def save_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    """Validate and atomically persist a checkpoint in the same directory."""
    validate_manifest(manifest)
    manifest["updated_at"] = utc_now()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("Manifest root must be an object")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"Unsupported manifest schema_version={manifest.get('schema_version')!r}"
        )
    batch_id = manifest.get("batch_id")
    if not isinstance(batch_id, str) or not _ID_PATTERN.fullmatch(batch_id):
        raise ManifestError("batch_id must be a stable lowercase identifier")

    allowed_hosts = manifest.get("fetch_policy", {}).get("allowed_hosts")
    if not isinstance(allowed_hosts, list) or not allowed_hosts:
        raise ManifestError("fetch_policy.allowed_hosts must be a non-empty list")
    normalized_hosts = []
    for host in allowed_hosts:
        if not isinstance(host, str) or not host or "/" in host or ":" in host:
            raise ManifestError(f"Invalid allowed host: {host!r}")
        normalized_hosts.append(host.casefold().rstrip("."))
    if len(set(normalized_hosts)) != len(normalized_hosts):
        raise ManifestError("fetch_policy.allowed_hosts contains duplicates")

    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ManifestError("items must be a non-empty list")

    item_ids: set[str] = set()
    source_ids: set[str] = set()
    source_urls: set[str] = set()
    for item in items:
        _validate_item(item, item_ids, source_ids, source_urls)

    for check in manifest.get("batch_retrieval_checks", []):
        if not isinstance(check, dict):
            raise ManifestError("batch_retrieval_checks entries must be objects")
        _require_text(check, "check_id", "batch_retrieval_checks")
        _require_text(check, "query", check["check_id"])
        _validate_passage_markers(check, check["check_id"])


def _require_text(record: dict[str, Any], field: str, record_name: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{record_name}.{field} must be non-empty text")
    return value


def _validate_item(
    item: Any,
    item_ids: set[str],
    source_ids: set[str],
    source_urls: set[str],
) -> None:
    if not isinstance(item, dict):
        raise ManifestError("Each item must be an object")
    item_id = _require_text(item, "stable_id", "item")
    if not _ID_PATTERN.fullmatch(item_id):
        raise ManifestError(f"Invalid stable item ID: {item_id}")
    if item_id in item_ids:
        raise ManifestError(f"Duplicate stable item ID: {item_id}")
    item_ids.add(item_id)
    for field in ("canonical_title", "item_type", "jurisdiction", "publisher"):
        _require_text(item, field, item_id)
    for field in (
        "official_application_url",
        "official_status_url",
        "official_help_url",
    ):
        value = item.get(field)
        if value is not None:
            _validate_web_url(value, f"{item_id}.{field}")
    _validate_status(item.get("processing_status"), item_id)

    sources = item.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ManifestError(f"{item_id}.sources must be a non-empty list")
    for source in sources:
        if not isinstance(source, dict):
            raise ManifestError(f"{item_id}.sources entries must be objects")
        source_id = _require_text(source, "source_id", item_id)
        if not _ID_PATTERN.fullmatch(source_id):
            raise ManifestError(f"Invalid source ID: {source_id}")
        if source_id in source_ids:
            raise ManifestError(f"Duplicate source ID: {source_id}")
        source_ids.add(source_id)
        url = _require_text(source, "official_url", source_id)
        _validate_web_url(url, f"{source_id}.official_url")
        if url in source_urls:
            raise ManifestError(f"Duplicate source URL: {url}")
        source_urls.add(url)
        for field in ("document_title", "source_type", "language", "coverage_scope"):
            _require_text(source, field, source_id)
        _validate_status(source.get("processing_status"), source_id)
        attempts = source.get("attempt_count")
        if not isinstance(attempts, int) or attempts < 0:
            raise ManifestError(f"{source_id}.attempt_count must be a non-negative int")
        markers = source.get("required_markers", [])
        if not isinstance(markers, list) or not all(
            isinstance(marker, str) and marker.strip() for marker in markers
        ):
            raise ManifestError(f"{source_id}.required_markers must be text values")

    checks = item.get("retrieval_checks", [])
    if not isinstance(checks, list):
        raise ManifestError(f"{item_id}.retrieval_checks must be a list")
    for check in checks:
        if not isinstance(check, dict):
            raise ManifestError(f"{item_id}.retrieval_checks entries must be objects")
        _require_text(check, "check_id", item_id)
        _require_text(check, "query", item_id)
        _validate_passage_markers(check, check["check_id"])

def _validate_passage_markers(check: dict[str, Any], record_name: str) -> None:
    markers = check.get("expected_passage_markers", [])
    if not isinstance(markers, list) or not all(
        isinstance(marker, str) and marker.strip() for marker in markers
    ):
        raise ManifestError(
            f"{record_name}.expected_passage_markers must be text values"
        )


def _validate_web_url(value: Any, record_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{record_name} must be non-empty text or null")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ManifestError(f"{record_name} must be an absolute HTTP(S) URL")


def _validate_status(status: Any, record_id: str) -> None:
    if status not in PIPELINE_STAGES and status not in TERMINAL_STATUSES:
        raise ManifestError(f"{record_id} has invalid processing_status={status!r}")


def iter_sources(
    manifest: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    for item in manifest["items"]:
        for source in item["sources"]:
            yield item, source


def stage_at_least(status: str, target: str) -> bool:
    if status in TERMINAL_STATUSES:
        return False
    return PIPELINE_STAGES.index(status) >= PIPELINE_STAGES.index(target)


def advance_stage(record: dict[str, Any], target: str) -> None:
    """Advance monotonically; interrupted resumes never move evidence backward."""
    if target not in PIPELINE_STAGES:
        raise ManifestError(f"Unknown target stage: {target}")
    current = record["processing_status"]
    if current in TERMINAL_STATUSES:
        raise ManifestError(f"Cannot advance terminal record from {current}")
    if PIPELINE_STAGES.index(target) < PIPELINE_STAGES.index(current):
        raise ManifestError(f"Cannot move stage backward from {current} to {target}")
    record["processing_status"] = target
    record[f"{target}_at"] = utc_now()
    record["last_error"] = None
    record["retry_eligible"] = False


def record_failure(
    record: dict[str, Any], exc: BaseException, *, retry_eligible: bool
) -> None:
    record["last_error"] = f"{type(exc).__name__}: {exc}"
    record["retry_eligible"] = retry_eligible


def refresh_item_stage(item: dict[str, Any]) -> None:
    statuses = [source["processing_status"] for source in item["sources"]]
    if any(status in TERMINAL_STATUSES for status in statuses):
        item["processing_status"] = "excluded"
        return
    item["processing_status"] = min(statuses, key=PIPELINE_STAGES.index)


def stage_counts(manifest: dict[str, Any]) -> dict[str, int]:
    """Return cumulative distinct-item counts, never source-document counts."""
    counts: dict[str, int] = {}
    for stage in PIPELINE_STAGES:
        counts[stage] = sum(
            stage_at_least(item["processing_status"], stage)
            for item in manifest["items"]
        )
    counts["excluded"] = sum(
        item["processing_status"] == "excluded" for item in manifest["items"]
    )
    return counts
