"""Checks for the Phase 1 data model: migration shape and temporal eval cases.

The migration itself was exercised against PostgreSQL 16 (apply, re-apply,
rollback, re-apply) when it was written; these tests keep it additive and keep
the temporal evaluation set consistent with the offence tables.
"""

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from app.traffic_offences import load_tables, lookup

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "db" / "migrations" / "0001_jurisdiction_and_effective_dates.sql"
ROLLBACK = ROOT / "db" / "migrations" / "0001_jurisdiction_and_effective_dates.down.sql"
TEMPORAL_CASES = ROOT / "eval" / "temporal_cases.jsonl"

EXPECTED_BEHAVIORS = {"reject_premise", "ask_jurisdiction", "abstain_without_versioned_source"}


def _sql_statements(path: Path) -> list[str]:
    body = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--")
    )
    return [statement.strip() for statement in body.split(";") if statement.strip()]


class MigrationShapeTests(unittest.TestCase):
    def test_migration_is_additive_and_transactional(self):
        statements = _sql_statements(MIGRATION)
        self.assertEqual(statements[0].upper(), "BEGIN")
        self.assertEqual(statements[-1].upper(), "COMMIT")
        allowed = (
            r"ALTER TABLE (documents|chunks) ADD COLUMN IF NOT EXISTS \w+ \w+",
            r"ALTER TABLE (documents|chunks) DROP CONSTRAINT IF EXISTS \w+_effective_range_chk",
            r"ALTER TABLE (documents|chunks) ADD CONSTRAINT \w+_effective_range_chk\s+CHECK \(.*\)",
            r"CREATE INDEX IF NOT EXISTS \w+\s+ON (documents|chunks) \(.*\)",
        )
        for statement in statements[1:-1]:
            normalized = " ".join(statement.split())
            self.assertTrue(
                any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in allowed),
                f"unexpected statement in additive migration: {normalized}",
            )

    def test_migration_keeps_url_unique_key(self):
        text = MIGRATION.read_text(encoding="utf-8").upper()
        self.assertNotIn("DOCUMENTS_URL_KEY", text)
        self.assertNotIn("DROP COLUMN", text)
        self.assertNotIn("DROP TABLE", text)

    def test_rollback_removes_every_added_column(self):
        added = set(re.findall(r"ADD COLUMN IF NOT EXISTS (\w+)", MIGRATION.read_text(encoding="utf-8")))
        dropped = set(re.findall(r"DROP COLUMN IF EXISTS (\w+)", ROLLBACK.read_text(encoding="utf-8")))
        self.assertEqual(added, dropped)
        self.assertEqual(added, {"jurisdiction", "effective_from", "effective_to", "source_hash", "retrieved_at"})


class TemporalCaseTests(unittest.TestCase):
    def setUp(self):
        self.cases = [
            json.loads(line) for line in TEMPORAL_CASES.read_text(encoding="utf-8").splitlines() if line.strip()
        ]

    def test_balanced_across_languages(self):
        self.assertEqual(len(self.cases), 15)
        self.assertEqual(Counter(case["language"] for case in self.cases), {"en": 5, "hi": 5, "bn": 5})
        self.assertEqual(len({case["id"] for case in self.cases}), 15)

    def test_cases_are_marked_pending(self):
        # Retrieval does not filter by jurisdiction or date yet (docs/FINDINGS.md, P1 and P2).
        for case in self.cases:
            self.assertEqual(case["status"], "pending_implementation", case["id"])
            self.assertIn(case["expected_behavior"], EXPECTED_BEHAVIORS, case["id"])

    def test_false_premise_answers_match_offence_tables(self):
        tables = load_tables()
        premise_cases = [case for case in self.cases if case["category"] == "false_premise"]
        self.assertEqual(len(premise_cases), 6)
        for case in premise_cases:
            row = lookup(tables, case["jurisdiction"], case["offence_id"])
            self.assertEqual(row["first_offence"], case["expected_amount"], case["id"])
            self.assertNotEqual(case["claimed_amount"], row["first_offence"]["max"], case["id"])

    def test_missing_jurisdiction_cases_have_no_jurisdiction(self):
        for case in self.cases:
            if case["expected_behavior"] == "ask_jurisdiction":
                self.assertIsNone(case["jurisdiction"], case["id"])


if __name__ == "__main__":
    unittest.main()
