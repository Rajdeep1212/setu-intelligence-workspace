-- Rollback for migration 0002. Stops archiving and DROPS every archived
-- version. The current documents rows are not touched. Export the table first
-- if the history is needed:
--
--   psql "$DATABASE_URL" -c "\copy document_versions TO 'document_versions.csv' CSV HEADER"

BEGIN;

DROP TRIGGER IF EXISTS documents_archive_version ON documents;
DROP FUNCTION IF EXISTS documents_archive_version();
DROP TABLE IF EXISTS document_versions;

COMMIT;
