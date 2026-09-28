# Data backfills

Backfills change existing **rows**, not the schema. Schema changes belong in
[`db/migrations/`](../migrations/README.md).

Rules:

- Apply manually, in numeric order, after a verified backup and after the
  migrations they depend on. Nothing in Compose, the API or CI runs these files.
- Each file is one transaction, only fills values that are still NULL, and is
  safe to run twice.
- Never invent a date or amount: a backfill may only set values that follow
  from the source itself.

| Backfill | Requires | Effect |
|---|---|---|
| `0001_tag_pib_central.sql` | Migration 0001 | Tags documents with `source = 'PIB'` and their chunks as `jurisdiction = 'IN'` (central). Leaves effective dates unknown. |
