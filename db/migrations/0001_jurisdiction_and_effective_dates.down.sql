-- Rollback for migration 0001. Removes only what 0001 added.
-- Data in these columns is lost on rollback; take a backup first.

BEGIN;

DROP INDEX IF EXISTS chunks_jurisdiction_effective_idx;
DROP INDEX IF EXISTS documents_jurisdiction_idx;

ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_effective_range_chk;
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_effective_range_chk;

ALTER TABLE chunks DROP COLUMN IF EXISTS effective_to;
ALTER TABLE chunks DROP COLUMN IF EXISTS effective_from;
ALTER TABLE chunks DROP COLUMN IF EXISTS jurisdiction;

ALTER TABLE documents DROP COLUMN IF EXISTS retrieved_at;
ALTER TABLE documents DROP COLUMN IF EXISTS source_hash;
ALTER TABLE documents DROP COLUMN IF EXISTS effective_to;
ALTER TABLE documents DROP COLUMN IF EXISTS effective_from;
ALTER TABLE documents DROP COLUMN IF EXISTS jurisdiction;

COMMIT;
