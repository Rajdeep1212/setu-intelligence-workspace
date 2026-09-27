-- Migration 0001: jurisdiction, effective dates, and source provenance.
--
-- Applies to an existing database created from db/init.sql. db/init.sql is a
-- bootstrap file and is deliberately left unchanged (docs/DEPLOYMENT.md,
-- "Database change policy"). Operators apply this file manually, after a
-- verified backup, with a role that owns the tables:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/0001_jurisdiction_and_effective_dates.up.sql
--
-- Forward compatibility: every column is nullable and has no default, so the
-- current application (which neither reads nor writes these columns) keeps
-- working unchanged. Rollback: 0001_jurisdiction_and_effective_dates.down.sql.
-- Running this file twice fails at the first ADD CONSTRAINT and the whole
-- transaction rolls back, leaving the schema as it was.
--
-- Semantics
--   jurisdiction    'IN' for central law, or an ISO 3166-2:IN subdivision code
--                   such as 'IN-WB', 'IN-KA', 'IN-DL'. NULL = not yet tagged.
--   effective_from  first date (inclusive) on which the text applies.
--   effective_to    first date (exclusive) on which the text no longer applies;
--                   NULL = still in force as far as the source shows.
--   source_hash     lowercase hex SHA-256 of the exact bytes retrieved.
--   retrieved_at    when those bytes were retrieved.
-- A chunk value, when present, overrides its document's value; retrieval
-- should read COALESCE(chunks.x, documents.x).

BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS jurisdiction TEXT,
    ADD COLUMN IF NOT EXISTS effective_from DATE,
    ADD COLUMN IF NOT EXISTS effective_to DATE,
    ADD COLUMN IF NOT EXISTS source_hash TEXT,
    ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ;

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS jurisdiction TEXT,
    ADD COLUMN IF NOT EXISTS effective_from DATE,
    ADD COLUMN IF NOT EXISTS effective_to DATE,
    ADD COLUMN IF NOT EXISTS source_hash TEXT,
    ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ;

ALTER TABLE documents
    ADD CONSTRAINT documents_jurisdiction_format
        CHECK (jurisdiction IS NULL OR jurisdiction ~ '^IN(-[A-Z]{2})?$'),
    ADD CONSTRAINT documents_effective_range
        CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from),
    ADD CONSTRAINT documents_source_hash_format
        CHECK (source_hash IS NULL OR source_hash ~ '^[0-9a-f]{64}$');

ALTER TABLE chunks
    ADD CONSTRAINT chunks_jurisdiction_format
        CHECK (jurisdiction IS NULL OR jurisdiction ~ '^IN(-[A-Z]{2})?$'),
    ADD CONSTRAINT chunks_effective_range
        CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from),
    ADD CONSTRAINT chunks_source_hash_format
        CHECK (source_hash IS NULL OR source_hash ~ '^[0-9a-f]{64}$');

-- Supports "filter by state and date before ranking" (docs/FINDINGS.md, P1).
CREATE INDEX IF NOT EXISTS documents_jurisdiction_effective_idx
    ON documents (jurisdiction, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS chunks_jurisdiction_effective_idx
    ON chunks (jurisdiction, effective_from, effective_to);

COMMIT;
