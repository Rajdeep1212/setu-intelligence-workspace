# Database migrations

`db/init.sql` bootstraps a brand-new volume and is never edited to change an
existing schema ([deployment runbook](../../docs/DEPLOYMENT.md)). Schema
changes are numbered, reviewed files in this directory:

| File | Purpose |
|---|---|
| `NNNN_name.up.sql` | Forward change, wrapped in one transaction |
| `NNNN_name.down.sql` | Rollback of the same change |

Rules:

- Apply in numeric order, manually, after a verified backup. Nothing in
  Compose, the API, or CI runs these files; the local database container
  mounts only `db/init.sql`.
- Every migration must be forward-compatible with the code already deployed:
  add nullable columns first, backfill later, tighten constraints last.
- `tests/test_migrations.py` checks structure offline. It does not execute SQL.
- `tests/test_migrations_postgres.py` applies `db/init.sql` and every
  migration to a disposable PostgreSQL with pgvector, runs ingestion against
  it, and tests each rollback. CI runs it in the `migrations-postgres` job;
  locally set `SETU_TEST_ADMIN_DSN` to a throwaway server.

| Migration | Adds |
|---|---|
| `0001_jurisdiction_and_effective_dates` | `jurisdiction`, `effective_from`, `effective_to`, `source_hash`, `retrieved_at` on `documents` and `chunks`, with format checks and a lookup index |
| `0002_document_version_history` | `document_versions` table and a trigger that archives the previous row whenever a re-ingest changes a document's source content. Requires 0001. Rollback drops the archive |
