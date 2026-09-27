-- Migration 0001: jurisdiction and effective dates (additive only).
--
-- Purpose: let retrieval filter by the enforcing authority and by the date a
-- rule applied (docs/FINDINGS.md, problem P1). Every change adds a nullable
-- column, a check constraint or an index, so the current application code and
-- existing rows keep working unchanged.
--
-- Not included on purpose: replacing UNIQUE (url) on documents with
-- UNIQUE (url, source_hash). ingestion/db_writer.py relies on
-- ON CONFLICT (url), so that change ships later together with the writer.
--
-- Apply only as an operator action, after a verified backup, following
-- docs/DEPLOYMENT.md. Roll back with 0001_jurisdiction_and_effective_dates.down.sql.

BEGIN;

-- Jurisdiction codes: 'IN' for central law, 'IN-WB' for a state,
-- 'IN-WB-KOL' for an enforcing authority inside a state (Kolkata Police).
ALTER TABLE documents ADD COLUMN IF NOT EXISTS jurisdiction TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_from DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_to DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_hash TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ;

-- Copied from the parent document at ingest time so retrieval can filter
-- chunks without an extra join condition in both legs.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS jurisdiction TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS effective_from DATE;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS effective_to DATE;

ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_effective_range_chk;
ALTER TABLE documents ADD CONSTRAINT documents_effective_range_chk
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from);

ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_effective_range_chk;
ALTER TABLE chunks ADD CONSTRAINT chunks_effective_range_chk
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from);

CREATE INDEX IF NOT EXISTS documents_jurisdiction_idx ON documents (jurisdiction);
CREATE INDEX IF NOT EXISTS chunks_jurisdiction_effective_idx
    ON chunks (jurisdiction, effective_from, effective_to);

COMMIT;
