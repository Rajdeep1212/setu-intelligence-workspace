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

| Migration | Adds |
|---|---|
| `0001_jurisdiction_and_effective_dates` | `jurisdiction`, `effective_from`, `effective_to`, `source_hash`, `retrieved_at` on `documents` and `chunks`, with format checks and a lookup index |
