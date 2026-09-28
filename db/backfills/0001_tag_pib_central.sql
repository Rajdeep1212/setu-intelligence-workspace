-- Backfill 0001: tag existing PIB press releases as central ('IN').
--
-- Why: retrieval with a jurisdiction filter keeps only rows tagged with the
-- requested state or 'IN' (app/retrieval/filters.py). Documents ingested
-- before migration 0001 have no jurisdiction, so filtered searches exclude
-- them. PIB publishes releases of the Government of India, so its documents
-- are tagged 'IN' (docs/FINDINGS.md, P1).
--
-- Scope and safety:
--   * Requires migration 0001. Operator-run only, after a verified backup;
--     nothing in Compose, the API or CI runs this file.
--   * Touches only rows with source = 'PIB' whose jurisdiction is still NULL,
--     so it is idempotent and never overwrites a value someone set.
--   * Does not set effective dates. PIB releases rarely state when a rule
--     takes effect, and an unknown start date must stay unknown, so these
--     documents stay out of date-specific searches.
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/backfills/0001_tag_pib_central.sql

BEGIN;

UPDATE documents
SET jurisdiction = 'IN'
WHERE source = 'PIB'
  AND jurisdiction IS NULL;

UPDATE chunks AS c
SET jurisdiction = 'IN'
FROM documents AS d
WHERE c.document_id = d.id
  AND d.source = 'PIB'
  AND d.jurisdiction = 'IN'
  AND c.jurisdiction IS NULL;

COMMIT;
