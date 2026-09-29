"""Reviewed source lists for the scheme corpus (M2.1), schema version 2.

A manifest in corpus/manifests records what a person reviewed: each scheme
(an "item"), its official sources, where they apply, and a pin of the exact
content that was read. It holds no run state. The pipeline keeps its progress
in corpus/staging/<batch>/state.json, which is not tracked, so running the
pipeline never rewrites a reviewed file and never puts local paths in Git.

Rules enforced here, standard library only (the freshness watch imports it):

- ``jurisdiction`` is a migration 0001 code: ``IN`` or ``IN-`` plus two
  capital letters. A source published by a state government is tagged with
  that state even when the scheme is central, because it describes that
  state's process.
- Source URLs are HTTPS on a host listed exactly in
  ``fetch_policy.allowed_hosts``. Links shown to people (apply, status, help)
  are HTTPS on an allowlisted host or a ``.gov.in`` / ``.nic.in`` host.
- Dates are ISO ``YYYY-MM-DD``. ``effective_from`` is left empty unless the
  source states when it applies; it is never guessed from a publication date.
- Every source that is not excluded has a pin: the SHA-256 of the bytes that
  were reviewed and when they were retrieved. PDFs are watched on those bytes.
  HTML pages change on every request (tokens, counters), so they are watched
  on ``text_sha256``, the hash of the extracted text made by
  ``text_version`` of the extractor, minus ``ignore_lines``.
- Unknown fields are rejected, so run state cannot creep back in.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from ingestion.corpus_extract import EXTRACTION_VERSION

SCHEMA_VERSION = 2
JURISDICTION_PATTERN = re.compile(r"^IN(-[A-Z]{2})?$")
_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LANGUAGE = re.compile(r"^[a-z]{2}$")
_OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")

_MANIFEST_REQUIRED = {"schema_version", "batch_id", "title", "reviewed_on", "fetch_policy", "items"}
_MANIFEST_OPTIONAL = {"batch_retrieval_checks", "notes"}
_POLICY_OPTIONAL = {
    "connect_timeout_seconds",
    "read_timeout_seconds",
    "retries",
    "max_redirects",
    "max_response_bytes",
    "min_host_interval_seconds",
    "max_retry_after_seconds",
}
_ITEM_REQUIRED = {
    "stable_id",
    "canonical_title",
    "item_type",
    "category",
    "jurisdiction",
    "publisher",
    "current_status",
    "status_as_of",
    "sources",
}
_ITEM_OPTIONAL = {
    "official_application_url",
    "official_status_url",
    "official_help_url",
    "practical_coverage",
    "retrieval_checks",
    "excluded",
}
SERVICE_LINK_FIELDS = ("official_application_url", "official_status_url", "official_help_url")
_SOURCE_REQUIRED = {
    "source_id",
    "document_title",
    "source_type",
    "official_url",
    "publisher",
    "language",
    "jurisdiction",
    "source_status",
    "coverage_scope",
    "pin",
}
_SOURCE_OPTIONAL = {
    "document_identifier",
    "publication_date",
    "updated_date",
    "effective_from",
    "effective_to",
    "required_markers",
    "min_extracted_characters",
    "excluded",
}
_PIN_REQUIRED = {"sha256", "retrieved_at", "watch"}
_TEXT_PIN_FIELDS = {"text_sha256", "text_version", "ignore_lines"}
_CHECK_REQUIRED = {"check_id", "query", "query_language", "expected_rank_max"}
_CHECK_OPTIONAL = {"expected_passage_markers", "expected_item_id", "expect_no_supported_item", "max_top_score"}


class ManifestError(ValueError):
    """A manifest is unsafe, incomplete or internally inconsistent."""


def manifest_paths(directory: str | Path) -> list[Path]:
    return sorted(Path(directory).glob("batch-*.json"))


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read manifest {manifest_path.name}: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def iter_active_sources(manifest: dict[str, Any]) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Sources that are collected, indexed and watched: none that are excluded."""
    for item in manifest["items"]:
        if item.get("excluded"):
            continue
        for source in item["sources"]:
            if not source.get("excluded"):
                yield item, source


def parse_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def validate_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("Manifest root must be an object")
    _check_fields(manifest, _MANIFEST_REQUIRED, _MANIFEST_OPTIONAL, "manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ManifestError(f"Unsupported schema_version={manifest['schema_version']!r}; expected {SCHEMA_VERSION}")
    if not isinstance(manifest["batch_id"], str) or not _ID.fullmatch(manifest["batch_id"]):
        raise ManifestError("batch_id must be a stable lowercase identifier")
    _require_text(manifest, "title", "manifest")
    _check_date(manifest, "reviewed_on", "manifest", required=True)

    policy = manifest["fetch_policy"]
    if not isinstance(policy, dict):
        raise ManifestError("fetch_policy must be an object")
    _check_fields(policy, {"allowed_hosts"}, _POLICY_OPTIONAL, "fetch_policy")
    hosts = policy["allowed_hosts"]
    if not isinstance(hosts, list) or not hosts:
        raise ManifestError("fetch_policy.allowed_hosts must be a non-empty list")
    for host in hosts:
        if not isinstance(host, str) or not re.fullmatch(r"[a-z0-9.-]+", host) or host.startswith("."):
            raise ManifestError(f"Invalid allowed host: {host!r}")
    if len(set(hosts)) != len(hosts):
        raise ManifestError("fetch_policy.allowed_hosts contains duplicates")
    for field in _POLICY_OPTIONAL & policy.keys():
        if not isinstance(policy[field], (int, float)) or isinstance(policy[field], bool) or policy[field] < 0:
            raise ManifestError(f"fetch_policy.{field} must be a non-negative number")
    allowed = set(hosts)

    items = manifest["items"]
    if not isinstance(items, list) or not items:
        raise ManifestError("items must be a non-empty list")
    seen: dict[str, set[str]] = {"item": set(), "source": set(), "url": set(), "check": set()}
    for item in items:
        _validate_item(item, allowed, seen)
    for check in manifest.get("batch_retrieval_checks", []):
        _validate_check(check, "batch_retrieval_checks", seen)
        expected = check.get("expected_item_id")
        if expected is not None and expected not in seen["item"]:
            raise ManifestError(f"{check['check_id']}.expected_item_id names an unknown item: {expected}")


def _validate_item(item: Any, allowed: set[str], seen: dict[str, set[str]]) -> None:
    if not isinstance(item, dict):
        raise ManifestError("Each item must be an object")
    item_id = item.get("stable_id")
    name = item_id if isinstance(item_id, str) else "item"
    _check_fields(item, _ITEM_REQUIRED, _ITEM_OPTIONAL, name)
    _check_id(item_id, "item", seen["item"])
    for field in ("canonical_title", "item_type", "category", "publisher", "current_status"):
        _require_text(item, field, name)
    _check_jurisdiction(item["jurisdiction"], name)
    _check_date(item, "status_as_of", name, required=True)
    if "excluded" in item:
        _require_text(item, "excluded", name)
    for field in SERVICE_LINK_FIELDS:
        if item.get(field) is not None:
            _check_official_link(item[field], allowed, f"{name}.{field}")

    sources = item["sources"]
    if not isinstance(sources, list) or not sources:
        raise ManifestError(f"{name}.sources must be a non-empty list")
    for source in sources:
        _validate_source(source, allowed, seen, item_excluded=bool(item.get("excluded")))
    checks = item.get("retrieval_checks", [])
    if not isinstance(checks, list):
        raise ManifestError(f"{name}.retrieval_checks must be a list")
    for check in checks:
        _validate_check(check, name, seen)


def _validate_source(source: Any, allowed: set[str], seen: dict[str, set[str]], *, item_excluded: bool) -> None:
    if not isinstance(source, dict):
        raise ManifestError("Each source must be an object")
    source_id = source.get("source_id")
    name = source_id if isinstance(source_id, str) else "source"
    _check_fields(source, _SOURCE_REQUIRED, _SOURCE_OPTIONAL, name)
    _check_id(source_id, "source", seen["source"])
    for field in ("document_title", "source_type", "publisher", "source_status", "coverage_scope"):
        _require_text(source, field, name)
    if source.get("document_identifier") is not None:
        _require_text(source, "document_identifier", name)
    url = source["official_url"]
    _check_https(url, f"{name}.official_url")
    host = urlsplit(url).hostname or ""
    if host not in allowed:
        raise ManifestError(f"{name}.official_url host {host} is not in fetch_policy.allowed_hosts")
    if url in seen["url"]:
        raise ManifestError(f"Duplicate source URL: {url}")
    seen["url"].add(url)
    if not isinstance(source["language"], str) or not _LANGUAGE.fullmatch(source["language"]):
        raise ManifestError(f"{name}.language must be a two-letter lowercase code")
    _check_jurisdiction(source["jurisdiction"], name)
    for field in ("publication_date", "updated_date", "effective_from", "effective_to"):
        _check_date(source, field, name, required=False)
    start, end = source.get("effective_from"), source.get("effective_to")
    if start and end and end <= start:
        raise ManifestError(f"{name}.effective_to must be after effective_from (the range is half-open)")
    markers = source.get("required_markers", [])
    if not isinstance(markers, list) or not all(isinstance(m, str) and m.strip() for m in markers):
        raise ManifestError(f"{name}.required_markers must be a list of text values")
    minimum = source.get("min_extracted_characters", 500)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise ManifestError(f"{name}.min_extracted_characters must be a positive integer")
    if "excluded" in source:
        _require_text(source, "excluded", name)

    pin = source["pin"]
    if pin is None:
        if not (item_excluded or source.get("excluded")):
            raise ManifestError(f"{name} is not excluded, so it needs a pin of the reviewed content")
        return
    _validate_pin(pin, f"{name}.pin")


def _validate_pin(pin: Any, name: str) -> None:
    if not isinstance(pin, dict):
        raise ManifestError(f"{name} must be an object or null")
    _check_fields(pin, _PIN_REQUIRED, _TEXT_PIN_FIELDS, name)
    if not isinstance(pin["sha256"], str) or not _SHA256.fullmatch(pin["sha256"]):
        raise ManifestError(f"{name}.sha256 must be 64 lowercase hexadecimal characters")
    retrieved = pin["retrieved_at"]
    if not isinstance(retrieved, str) or not retrieved.endswith("Z"):
        raise ManifestError(f"{name}.retrieved_at must be a UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError(f"{name}.retrieved_at is not an ISO timestamp") from exc
    watch = pin["watch"]
    if watch == "bytes":
        extra = _TEXT_PIN_FIELDS & pin.keys()
        if extra:
            raise ManifestError(f"{name}: {', '.join(sorted(extra))} only apply when watch is 'text'")
        return
    if watch != "text":
        raise ManifestError(f"{name}.watch must be 'bytes' or 'text'")
    text_hash = pin.get("text_sha256")
    if not isinstance(text_hash, str) or not _SHA256.fullmatch(text_hash):
        raise ManifestError(f"{name}.text_sha256 must be 64 lowercase hexadecimal characters")
    if pin.get("text_version") != EXTRACTION_VERSION:
        raise ManifestError(
            f"{name}.text_version is {pin.get('text_version')!r} but the extractor is {EXTRACTION_VERSION!r}; re-pin"
        )
    ignore = pin.get("ignore_lines", [])
    if not isinstance(ignore, list):
        raise ManifestError(f"{name}.ignore_lines must be a list of regular expressions")
    for pattern in ignore:
        try:
            if not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
                raise re.error("must be anchored with ^ and $")
            re.compile(pattern)
        except re.error as exc:
            raise ManifestError(f"{name}.ignore_lines has an invalid pattern {pattern!r}: {exc}") from exc


def _validate_check(check: Any, owner: str, seen: dict[str, set[str]]) -> None:
    if not isinstance(check, dict):
        raise ManifestError(f"{owner} retrieval checks must be objects")
    _check_fields(check, _CHECK_REQUIRED, _CHECK_OPTIONAL, f"{owner}.check")
    check_id = check["check_id"]
    if not isinstance(check_id, str) or not _ID.fullmatch(check_id):
        raise ManifestError(f"{owner}: invalid check_id {check_id!r}")
    if check_id in seen["check"]:
        raise ManifestError(f"Duplicate check_id: {check_id}")
    seen["check"].add(check_id)
    _require_text(check, "query", check_id)
    if not isinstance(check["query_language"], str) or not _LANGUAGE.fullmatch(check["query_language"]):
        raise ManifestError(f"{check_id}.query_language must be a two-letter lowercase code")
    if not isinstance(check["expected_rank_max"], int) or check["expected_rank_max"] < 1:
        raise ManifestError(f"{check_id}.expected_rank_max must be a positive integer")
    markers = check.get("expected_passage_markers", [])
    if not isinstance(markers, list) or not all(isinstance(m, str) and m.strip() for m in markers):
        raise ManifestError(f"{check_id}.expected_passage_markers must be text values")


def _check_fields(record: dict[str, Any], required: set[str], optional: set[str], name: str) -> None:
    missing = required - record.keys()
    if missing:
        raise ManifestError(f"{name} is missing required fields: {sorted(missing)}")
    unknown = record.keys() - required - optional
    if unknown:
        raise ManifestError(f"{name} has unknown field(s) {sorted(unknown)}; run state belongs in corpus/staging")


def _check_id(value: Any, kind: str, seen: set[str]) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ManifestError(f"Invalid {kind} id: {value!r}")
    if value in seen:
        raise ManifestError(f"Duplicate {kind} id: {value}")
    seen.add(value)


def _require_text(record: dict[str, Any], field: str, name: str) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{name}.{field} must be non-empty text")


def _check_jurisdiction(value: Any, name: str) -> None:
    if not isinstance(value, str) or not JURISDICTION_PATTERN.fullmatch(value):
        raise ManifestError(f"{name}.jurisdiction must be 'IN' or 'IN-' followed by two capital letters, got {value!r}")


def _check_date(record: dict[str, Any], field: str, name: str, *, required: bool) -> None:
    value = record.get(field)
    if value is None and not required:
        return
    try:
        if not isinstance(value, str) or not _DATE.fullmatch(value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        raise ManifestError(f"{name}.{field} must be an ISO date (YYYY-MM-DD), got {value!r}") from None


def _check_https(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise ManifestError(f"{name} must be text")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ManifestError(f"{name} must be a plain https URL, got {value!r}")


def _check_official_link(value: Any, allowed: set[str], name: str) -> None:
    try:
        _check_https(value, name)
    except ManifestError:
        raise ManifestError(f"{name} must be an official https link, got {value!r}") from None
    host = urlsplit(value).hostname or ""
    if host not in allowed and not host.endswith(_OFFICIAL_SUFFIXES):
        raise ManifestError(f"{name} must be an official link (.gov.in, .nic.in or an allowlisted host), got {host}")
