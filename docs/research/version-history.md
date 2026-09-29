# Document version history: design note and results

Phase 4b of the SETU roadmap (docs/FINDINGS.md, problem P4). Date: 28 Sep 2026.

## Question

When SETU re-ingests a government page or PDF that has changed, is the text
it answered from yesterday still available? Before this change it was not.
Ingestion upserts on URL, which overwrote `raw_text` and provenance, reset
`created_at` and deleted the old chunks. The only copy of what SETU said a
source contained was gone after the next ingest.

## Design

Migration `db/migrations/0002_document_version_history.up.sql`:

| Part | Role |
|---|---|
| `document_versions` | One row per superseded version: text, metadata, jurisdiction, effective dates, `source_hash`, `retrieved_at`, when it was first seen, when it was superseded, and the hash that replaced it. |
| Trigger `documents_archive_version` | Before a `documents` row is updated, copies the old row into `document_versions` if the source content changed. |
| Guard | The migration refuses to run before migration 0001, and changes nothing if it does. |

Choices, and why:

- **`documents` keeps one row per URL, the current version.** Retrieval
  queries and the frozen evaluation are unchanged, and superseded text can
  never be retrieved by accident. FINDINGS P4 first proposed keeping every
  version in `documents`; that would have meant changing every retrieval
  query and the `url` unique key.
- **A trigger, not an application change.** Every writer is covered,
  including the deployed ingestion code, which does not know about the new
  table. `ingestion/db_writer.py` is unchanged except for its docstring.
- **Two kinds of time are kept apart.** `effective_from`/`effective_to` are
  legal validity: when the rule applies. `first_seen_at`/`superseded_at` are
  record time: when SETU held that text. FINDINGS P4 proposed closing the old
  row with `effective_to`. That would be wrong, because a re-scanned PDF or a
  page redesign changes the record, not the law. This is the standard
  valid-time versus transaction-time split of bitemporal databases.
- **"Changed" means different source bytes.** When both rows have a
  `source_hash`, a different hash is a change. Otherwise, as for rows written
  before provenance existed, a different `raw_text` is a change. Re-ingesting
  unchanged bytes adds nothing.
- **No unique key on `(url, source_hash)`.** A source can change A to B and
  back to A. Both A periods are kept.
- **Chunks and embeddings are not archived.** They are derived data and can
  be rebuilt from the archived `raw_text`.
- **History outlives deletion.** Deleting a document sets
  `document_versions.document_id` to NULL; its archived versions and URL stay.

## What testing found

`created_at` was reset to `now()` on every upsert, including a re-ingest of
unchanged bytes. So the archive would have recorded the time of the last
unchanged re-ingest as "first seen", not the time the text was first
ingested. The real-database test caught it. The trigger now keeps
`created_at` when the content is unchanged, so `documents.created_at` means
"first seen with this content". Nothing in the application reads
`created_at` (searched 28 Sep 2026).

## Evaluation

`tests/test_migrations_postgres.py` runs against PostgreSQL 16 with pgvector,
using the real `ingestion.db_writer.write_document`. Each test gets a fresh
database.

| Test | Result |
|---|---|
| 0002 before 0001 fails and leaves no table | pass |
| Unchanged re-ingest adds no version; A to B to A keeps 2 versions with hashes, first-seen time and jurisdiction | pass |
| Only the current version is in `documents` and `chunks` | pass |
| Writer without provenance: archived by text change | pass |
| Running 0002 twice fails atomically; archive intact | pass |
| Rollback removes trigger, function and table; ingestion still works; re-apply works | pass |
| Deleting a document keeps its history | pass |

These tests were run locally on PostgreSQL 16.13. They also run in CI, in a
new `migrations-postgres` job that uses the `pgvector/pgvector:pg16` service
container. It runs on a standard runner, is free for this public repository,
and needs no secrets. Until now CI checked migration files only as text.

## Limitations

- Nothing reads `document_versions` yet. Answering "what did this source say
  on date X" needs a query path and an API; that belongs with the temporal
  benchmark work (roadmap item F).
- The archive keeps full text, so it grows with every real change. Government
  sources change rarely, so this is small; there is no pruning.
- A re-extraction that changes `raw_text` without changing the source bytes
  is not archived, by design. Improvements to text extraction are not
  source changes.
- Rolling back 0002 deletes the archive. The rollback file shows how to
  export it first.
