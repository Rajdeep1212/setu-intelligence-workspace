"""Source provenance helpers (Phase 1), free of scraping dependencies.

A fetched source is identified by the SHA-256 of the exact response bytes and
the UTC time they were retrieved. Storing both lets a later run tell that a
government page changed, and supports the freshness watch planned in
docs/FINDINGS.md (P4).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def source_fingerprint(content: bytes) -> str:
    """Lowercase hex SHA-256 of the exact bytes retrieved."""
    if not isinstance(content, (bytes, bytearray)):
        raise TypeError("source_fingerprint needs the raw response bytes")
    return hashlib.sha256(content).hexdigest()


def retrieved_now() -> datetime:
    """Timezone-aware retrieval time in UTC."""
    return datetime.now(timezone.utc)
