"""Jurisdiction and effective-date filters for both retrieval legs — Phase 1.

A rule can depend on where a question is asked and on which date applies
(docs/FINDINGS.md, P1). Migration 0001 adds ``jurisdiction``,
``effective_from`` and ``effective_to`` to ``documents`` and ``chunks``; a
chunk value overrides its document's value.

Semantics, applied before ranking:

- ``jurisdiction``: keep rows whose effective jurisdiction is the requested
  one or ``'IN'`` (central law applies everywhere). Untagged rows are
  excluded, because nothing says they apply to the requested place.
- ``as_of``: keep rows whose half-open range [effective_from, effective_to)
  contains the date. ``effective_from`` must be known: a NULL start means
  "unknown", never "always valid", so undated sources cannot answer a
  date-specific question. A NULL ``effective_to`` means still in force, as
  migration 0001 defines it.

If the filters leave no candidates, retrieval returns nothing and the agent
abstains; it never falls back to unfiltered results.

When neither filter is given, callers must not add any clause, so the SQL is
exactly what it was before this module and still runs on a database where
migration 0001 has not been applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

JURISDICTION_PATTERN = re.compile(r"^IN(-[A-Z]{2})?$")
CENTRAL_JURISDICTION = "IN"

_JURISDICTION_CLAUSE = (
    "\n              AND COALESCE(c.jurisdiction, d.jurisdiction)"
    " IN (CAST(:jurisdiction AS text), 'IN')"
)
_AS_OF_CLAUSE = (
    "\n              AND COALESCE(c.effective_from, d.effective_from) <= CAST(:as_of AS date)"
    "\n              AND (COALESCE(c.effective_to, d.effective_to) IS NULL"
    " OR COALESCE(c.effective_to, d.effective_to) > CAST(:as_of AS date))"
)


@dataclass(frozen=True)
class RetrievalFilters:
    jurisdiction: str | None = None
    as_of: date | None = None

    def __post_init__(self) -> None:
        if self.jurisdiction is not None and not JURISDICTION_PATTERN.fullmatch(self.jurisdiction):
            raise ValueError("jurisdiction must be 'IN' or 'IN-' followed by two capital letters")
        if self.as_of is not None and not isinstance(self.as_of, date):
            raise ValueError("as_of must be a date")

    @property
    def active(self) -> bool:
        return self.jurisdiction is not None or self.as_of is not None

    def sql_clause(self) -> str:
        """Extra WHERE conditions; empty when no filter is set."""
        clause = ""
        if self.jurisdiction is not None:
            clause += _JURISDICTION_CLAUSE
        if self.as_of is not None:
            clause += _AS_OF_CLAUSE
        return clause

    def params(self) -> dict[str, object]:
        """Bound parameters for ``sql_clause``; never formatted into the SQL."""
        values: dict[str, object] = {}
        if self.jurisdiction is not None:
            values["jurisdiction"] = self.jurisdiction
        if self.as_of is not None:
            values["as_of"] = self.as_of
        return values

    def as_kwargs(self) -> dict[str, object]:
        """Keyword arguments to forward to the next layer, only for filters that are set."""
        return self.params()
