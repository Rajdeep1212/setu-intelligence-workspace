"""Offline structural checks for numbered schema migrations.

These tests read SQL as text. They do not connect to a database;
tests/test_migrations_postgres.py runs the same files against PostgreSQL.
"""

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
PROVENANCE_COLUMNS = ("jurisdiction", "effective_from", "effective_to", "source_hash", "retrieved_at")
# SHA-256 of db/init.sql with LF line endings at the reviewed revision. A
# schema change belongs in db/migrations/, not in the bootstrap file.
INIT_SQL_SHA256 = "e1e3d6049dc13af451845c89d2457484bc11f33f4252864dd11857cfd9b90ed3"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _alter_table_block(sql: str, table: str, verb: str) -> str:
    match = re.search(rf"ALTER TABLE {table}\s+({verb} COLUMN.*?);", sql, re.S)
    return match.group(1) if match else ""


class MigrationStructureTests(unittest.TestCase):
    def test_bootstrap_schema_is_unchanged(self):
        content = (ROOT / "db" / "init.sql").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(
            hashlib.sha256(content).hexdigest(),
            INIT_SQL_SHA256,
            "db/init.sql changed; add a numbered migration instead (docs/DEPLOYMENT.md)",
        )

    def test_migrations_are_numbered_pairs(self):
        ups = sorted(MIGRATIONS.glob("*.up.sql"))
        self.assertTrue(ups)
        for index, up in enumerate(ups, start=1):
            self.assertRegex(up.name, rf"^{index:04d}_[a-z0-9_]+\.up\.sql$")
            self.assertTrue(up.with_name(up.name.replace(".up.sql", ".down.sql")).exists(), up.name)

    def test_each_migration_is_one_transaction(self):
        for path in MIGRATIONS.glob("*.sql"):
            statements = [line for line in _read(path).splitlines() if line.strip() and not line.lstrip().startswith("--")]
            self.assertEqual(statements[0].strip(), "BEGIN;", path.name)
            self.assertEqual(statements[-1].strip(), "COMMIT;", path.name)

    def test_0001_adds_nullable_provenance_columns_to_documents_and_chunks(self):
        sql = _read(MIGRATIONS / "0001_jurisdiction_and_effective_dates.up.sql")
        for table in ("documents", "chunks"):
            block = _alter_table_block(sql, table, "ADD")
            for column in PROVENANCE_COLUMNS:
                with self.subTest(table=table, column=column):
                    self.assertRegex(block, rf"ADD COLUMN IF NOT EXISTS {column} \w+")
            # Forward compatibility: the running code never writes these columns.
            self.assertNotIn("NOT NULL", block)
            self.assertNotIn("DEFAULT", block)

    def test_0001_rollback_drops_every_added_column(self):
        sql = _read(MIGRATIONS / "0001_jurisdiction_and_effective_dates.down.sql")
        for table in ("documents", "chunks"):
            block = sql.split(f"ALTER TABLE {table}", 1)[1].split(";", 1)[0]
            for column in PROVENANCE_COLUMNS:
                with self.subTest(table=table, column=column):
                    self.assertIn(f"DROP COLUMN IF EXISTS {column}", block)

    def test_0002_only_adds_objects_and_never_alters_existing_tables(self):
        sql = _read(MIGRATIONS / "0002_document_version_history.up.sql")
        code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        self.assertNotRegex(code, r"(?i)\bALTER\s+TABLE\b")
        self.assertNotRegex(code, r"(?i)\bDROP\b")
        self.assertIn("CREATE TABLE document_versions", code)
        self.assertIn("BEFORE UPDATE ON documents", code)
        # It must refuse to run before 0001.
        self.assertIn("requires migration 0001", code)

    def test_0002_rollback_removes_trigger_function_and_table(self):
        sql = _read(MIGRATIONS / "0002_document_version_history.down.sql")
        for statement in (
            "DROP TRIGGER IF EXISTS documents_archive_version ON documents;",
            "DROP FUNCTION IF EXISTS documents_archive_version();",
            "DROP TABLE IF EXISTS document_versions;",
        ):
            self.assertIn(statement, sql)
        self.assertNotIn("ALTER TABLE", sql)

    def test_every_migration_is_listed_in_the_readme(self):
        readme = _read(MIGRATIONS / "README.md")
        for up in MIGRATIONS.glob("*.up.sql"):
            self.assertIn(f"`{up.name.removesuffix('.up.sql')}`", readme)

    def test_bootstrap_schema_does_not_contain_migrated_columns(self):
        init_sql = _read(ROOT / "db" / "init.sql")
        for column in PROVENANCE_COLUMNS:
            self.assertNotIn(column, init_sql)


if __name__ == "__main__":
    unittest.main()
