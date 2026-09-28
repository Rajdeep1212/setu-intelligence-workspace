-- Rollback for migration 0001. Drops the provenance columns and any values
-- written to them. Take a verified backup first; this is destructive for
-- data stored in these columns only.

BEGIN;

DROP INDEX IF EXISTS chunks_jurisdiction_effective_idx;
DROP INDEX IF EXISTS documents_jurisdiction_effective_idx;

ALTER TABLE chunks
    DROP CONSTRAINT IF EXISTS chunks_source_hash_format,
    DROP CONSTRAINT IF EXISTS chunks_effective_range,
    DROP CONSTRAINT IF EXISTS chunks_jurisdiction_format,
    DROP COLUMN IF EXISTS retrieved_at,
    DROP COLUMN IF EXISTS source_hash,
    DROP COLUMN IF EXISTS effective_to,
    DROP COLUMN IF EXISTS effective_from,
    DROP COLUMN IF EXISTS jurisdiction;

ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_source_hash_format,
    DROP CONSTRAINT IF EXISTS documents_effective_range,
    DROP CONSTRAINT IF EXISTS documents_jurisdiction_format,
    DROP COLUMN IF EXISTS retrieved_at,
    DROP COLUMN IF EXISTS source_hash,
    DROP COLUMN IF EXISTS effective_to,
    DROP COLUMN IF EXISTS effective_from,
    DROP COLUMN IF EXISTS jurisdiction;

COMMIT;
