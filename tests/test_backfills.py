"""Offline structural checks for data backfills in db/backfills/.

These tests read SQL as text. The backfill was also executed against
PostgreSQL 16 with migration 0001 applied (twice, to confirm it is
idempotent) when it was written.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKFILLS = ROOT / "db" / "backfills"


def _statements(path: Path) -> list[str]:
    body = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--")
    )
    return [" ".join(statement.split()) for statement in body.split(";") if statement.strip()]


class BackfillStructureTests(unittest.TestCase):
    def test_backfills_are_numbered_and_documented(self):
        files = sorted(BACKFILLS.glob("*.sql"))
        self.assertTrue(files)
        readme = (BACKFILLS / "README.md").read_text(encoding="utf-8")
        for index, path in enumerate(files, start=1):
            self.assertRegex(path.name, rf"^{index:04d}_[a-z0-9_]+\.sql$")
            self.assertIn(path.name, readme)

    def test_each_backfill_is_one_transaction_of_updates_only(self):
        for path in BACKFILLS.glob("*.sql"):
            statements = _statements(path)
            self.assertEqual(statements[0].upper(), "BEGIN", path.name)
            self.assertEqual(statements[-1].upper(), "COMMIT", path.name)
            for statement in statements[1:-1]:
                self.assertTrue(statement.upper().startswith("UPDATE "), f"{path.name}: {statement}")
                for forbidden in ("DELETE", "DROP", "ALTER", "TRUNCATE", "INSERT"):
                    self.assertNotIn(forbidden, statement.upper(), path.name)

    def test_every_update_only_fills_nulls(self):
        for path in BACKFILLS.glob("*.sql"):
            for statement in _statements(path)[1:-1]:
                assigned = re.search(r"SET (\w+) =", statement).group(1)
                self.assertRegex(statement, rf"(\w+\.)?{assigned} IS NULL", f"{path.name}: {statement}")

    def test_pib_backfill_is_scoped_and_sets_no_dates(self):
        statements = _statements(BACKFILLS / "0001_tag_pib_central.sql")[1:-1]
        self.assertEqual(len(statements), 2)
        for statement in statements:
            self.assertIn("source = 'PIB'", statement)
            self.assertIn("SET jurisdiction = 'IN'", statement)
            self.assertNotIn("effective_", statement.split("WHERE")[0])


if __name__ == "__main__":
    unittest.main()
