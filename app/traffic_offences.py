"""Traffic offence tables: loading and validation.

The tables in ``data/traffic_offences/`` hold fines per jurisdiction with the
source each value came from. The validator enforces one rule above all others:
no amount may appear without an official source, a source date and a status
that says how it was confirmed. Values that could not be confirmed stay null
with status ``UNVERIFIED``.

See ``data/traffic_offences/README.md`` for the file format and
``docs/FINDINGS.md`` (claims C1 to C3) for the evidence behind each value.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_TABLE_DIR = Path(__file__).resolve().parent.parent / "data" / "traffic_offences"

SCHEMA_VERSION = "setu.traffic-offences/v1"

# How a value was confirmed, strongest first.
#   VERIFIED_PRIMARY        read from the gazette notification or statute on an official site
#   OFFICIAL_PUBLISHED_LIST published by the enforcing authority on its official site
#   SECONDARY               statute text reproduced by a legal database; confirm on India Code
#   UNVERIFIED              not confirmed; amounts must be null
STATUSES = ("VERIFIED_PRIMARY", "OFFICIAL_PUBLISHED_LIST", "SECONDARY", "UNVERIFIED")
OFFICIAL_STATUSES = ("VERIFIED_PRIMARY", "OFFICIAL_PUBLISHED_LIST")
SOURCE_DATE_KINDS = ("notification_date", "list_updated", "effective_date", "act_date")

# Official hosts. Government domains by suffix, plus named official sites that
# do not use a government domain (each with its reason).
OFFICIAL_DOMAIN_SUFFIXES = (".gov.in", ".nic.in")
OFFICIAL_NAMED_HOSTS = {
    # West Bengal Traffic Police's own site; it publishes the state schedule.
    "www.wbtrafficpolice.com": "West Bengal Traffic Police",
}

JURISDICTION_PATTERN = re.compile(r"^IN(-[A-Z]{2}(-[A-Z]{3})?)?$")
REQUIRED_ROW_KEYS = (
    "offence_id",
    "offence",
    "sections",
    "first_offence",
    "subsequent_offence",
    "status",
    "source",
    "notes",
)


def is_official_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host in OFFICIAL_NAMED_HOSTS or any(host.endswith(s) for s in OFFICIAL_DOMAIN_SUFFIXES)


def _check_amount(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        return [f"{label}: must be null or an object with exactly 'min' and 'max'"]
    low, high = value["min"], value["max"]
    errors = []
    for name, number in (("min", low), ("max", high)):
        if number is not None and (not isinstance(number, int) or isinstance(number, bool) or number <= 0):
            errors.append(f"{label}.{name}: must be null or a positive whole number of rupees")
    if high is None:
        errors.append(f"{label}.max: required when an amount is given")
    if isinstance(low, int) and isinstance(high, int) and low > high:
        errors.append(f"{label}: min is greater than max")
    return errors


def _check_source(source: Any, status: str, label: str) -> list[str]:
    if status == "UNVERIFIED":
        if source is not None and not isinstance(source, dict):
            return [f"{label}: must be null or an object"]
        return []
    if not isinstance(source, dict):
        return [f"{label}: required for status {status}"]
    errors = []
    url = source.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        errors.append(f"{label}.url: an https URL is required")
    elif status in OFFICIAL_STATUSES and not is_official_url(url):
        errors.append(f"{label}.url: status {status} needs an official host, got {urlparse(url).hostname}")
    if not source.get("title"):
        errors.append(f"{label}.title: required")
    kind = source.get("date_kind")
    if kind not in SOURCE_DATE_KINDS:
        errors.append(f"{label}.date_kind: must be one of {', '.join(SOURCE_DATE_KINDS)}")
    try:
        date.fromisoformat(str(source.get("date")))
    except ValueError:
        errors.append(f"{label}.date: must be an ISO date (YYYY-MM-DD)")
    if kind == "notification_date" and not source.get("notification_ref"):
        errors.append(f"{label}.notification_ref: required when date_kind is notification_date")
    try:
        date.fromisoformat(str(source.get("retrieved_on")))
    except ValueError:
        errors.append(f"{label}.retrieved_on: must be an ISO date (YYYY-MM-DD)")
    return errors


def validate_table(table: dict[str, Any], expected_jurisdiction: str | None = None) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid."""
    errors: list[str] = []
    if table.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema: expected {SCHEMA_VERSION}")
    jurisdiction = table.get("jurisdiction")
    if not isinstance(jurisdiction, str) or not JURISDICTION_PATTERN.match(jurisdiction):
        errors.append("jurisdiction: must look like IN, IN-WB or IN-WB-KOL")
    elif expected_jurisdiction and jurisdiction != expected_jurisdiction:
        errors.append(f"jurisdiction: {jurisdiction} does not match file name {expected_jurisdiction}")
    if not table.get("authority"):
        errors.append("authority: required")
    rows = table.get("offences")
    if not isinstance(rows, list) or not rows:
        return errors + ["offences: must be a non-empty list"]

    seen: set[str] = set()
    for index, row in enumerate(rows):
        label = f"offences[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = [key for key in REQUIRED_ROW_KEYS if key not in row]
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
            continue
        label = f"{label} ({row['offence_id']})"
        if row["offence_id"] in seen:
            errors.append(f"{label}: duplicate offence_id")
        seen.add(row["offence_id"])
        if not isinstance(row["sections"], list) or not row["sections"]:
            errors.append(f"{label}.sections: list at least one MV Act section")
        status = row["status"]
        if status not in STATUSES:
            errors.append(f"{label}.status: must be one of {', '.join(STATUSES)}")
            continue
        errors += _check_amount(row["first_offence"], f"{label}.first_offence")
        errors += _check_amount(row["subsequent_offence"], f"{label}.subsequent_offence")
        has_amount = row["first_offence"] is not None or row["subsequent_offence"] is not None
        if status == "UNVERIFIED" and has_amount:
            errors.append(f"{label}: UNVERIFIED rows must not carry amounts")
        if status != "UNVERIFIED" and not has_amount:
            errors.append(f"{label}: status {status} needs at least one amount")
        errors += _check_source(row["source"], status, f"{label}.source")
        if status == "UNVERIFIED" and not row["notes"]:
            errors.append(f"{label}.notes: say what source would settle this value")
    return errors


def load_tables(directory: Path = DEFAULT_TABLE_DIR) -> dict[str, dict[str, Any]]:
    """Load every ``IN*.json`` table, keyed by jurisdiction. Raises on invalid data."""
    tables: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("IN*.json")):
        table = json.loads(path.read_text(encoding="utf-8"))
        problems = validate_table(table, expected_jurisdiction=path.stem)
        if problems:
            raise ValueError(f"{path.name}: " + "; ".join(problems))
        tables[table["jurisdiction"]] = table
    return tables


def jurisdiction_chain(jurisdiction: str) -> list[str]:
    """Most specific first: IN-WB-KOL -> [IN-WB-KOL, IN-WB, IN]."""
    parts = jurisdiction.split("-")
    return ["-".join(parts[:size]) for size in range(len(parts), 0, -1)]


def lookup(
    tables: dict[str, dict[str, Any]], jurisdiction: str, offence_id: str
) -> dict[str, Any] | None:
    """Return the most specific row with a confirmed amount, else the most specific row.

    The returned dict adds ``jurisdiction`` so callers can say where the value
    came from. Returns None when no table lists the offence.
    """
    fallback = None
    for code in jurisdiction_chain(jurisdiction):
        for row in tables.get(code, {}).get("offences", []):
            if row["offence_id"] != offence_id:
                continue
            found = {**row, "jurisdiction": code}
            if row["status"] != "UNVERIFIED":
                return found
            fallback = fallback or found
    return fallback
