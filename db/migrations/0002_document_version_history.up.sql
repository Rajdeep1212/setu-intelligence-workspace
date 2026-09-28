-- Migration 0002: keep every earlier version of a source document.
--
-- Requires migration 0001 (it copies the provenance columns). Apply manually,
-- after a verified backup, with a role that owns the tables:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/0002_document_version_history.up.sql
--
-- Problem (docs/FINDINGS.md, P4): ingestion upserts on URL. A re-ingest
-- overwrote raw_text and provenance and reset created_at, so the text SETU
-- answered from last month was lost.
--
-- Design
--   * documents keeps exactly one row per URL: the current version. Retrieval
--     and every existing query are unchanged, and superseded text can never
--     be retrieved by accident.
--   * Before a documents row is updated with different source content, a
--     trigger copies the old row into document_versions. No application change
--     is needed, and every writer is covered, including one that does not
--     know about this table.
--   * "Different content" means a different source_hash when both hashes are
--     known (the source bytes changed), otherwise a different raw_text.
--     Re-ingesting unchanged bytes adds nothing.
--   * Two kinds of time are kept apart. effective_from/effective_to are legal
--     validity (when the rule applies). first_seen_at/superseded_at are
--     record time (when SETU held that text). A re-scanned PDF changes record
--     time only; it does not end the law.
--   * documents.created_at now means "first seen with this content": an
--     unchanged re-ingest keeps it instead of resetting it to now(). Nothing
--     in the application reads created_at (checked 28 Sep 2026).
--   * Chunks and embeddings are derived data and are not archived; they can
--     be rebuilt from raw_text.
--   * There is no unique key on (url, source_hash): a source can change A -> B
--     -> A, and both A periods are kept.
--
-- Forward compatibility: new table and trigger only; no existing column,
-- constraint or index changes. Rollback: 0002_document_version_history.down.sql.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'documents'
          AND column_name = 'source_hash'
    ) THEN
        RAISE EXCEPTION 'migration 0002 requires migration 0001 (documents.source_hash is missing)';
    END IF;
END
$$;

CREATE TABLE document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    url TEXT,
    source TEXT NOT NULL,
    title TEXT,
    language CHAR(2) NOT NULL,
    raw_text TEXT,
    metadata JSONB,
    jurisdiction TEXT,
    effective_from DATE,
    effective_to DATE,
    source_hash TEXT,
    retrieved_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ,
    superseded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by_hash TEXT,
    CONSTRAINT document_versions_source_hash_format
        CHECK (source_hash IS NULL OR source_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT document_versions_superseded_by_hash_format
        CHECK (superseded_by_hash IS NULL OR superseded_by_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX document_versions_document_idx
    ON document_versions (document_id, superseded_at DESC);
CREATE INDEX document_versions_url_idx
    ON document_versions (url, superseded_at DESC);

CREATE FUNCTION documents_archive_version() RETURNS trigger AS $$
DECLARE
    content_changed BOOLEAN;
BEGIN
    IF OLD.source_hash IS NOT NULL AND NEW.source_hash IS NOT NULL THEN
        content_changed := OLD.source_hash <> NEW.source_hash;
    ELSE
        content_changed := OLD.raw_text IS DISTINCT FROM NEW.raw_text;
    END IF;
    IF content_changed THEN
        INSERT INTO document_versions (
            document_id, url, source, title, language, raw_text, metadata,
            jurisdiction, effective_from, effective_to, source_hash, retrieved_at,
            first_seen_at, superseded_by_hash
        )
        VALUES (
            OLD.id, OLD.url, OLD.source, OLD.title, OLD.language, OLD.raw_text, OLD.metadata,
            OLD.jurisdiction, OLD.effective_from, OLD.effective_to, OLD.source_hash, OLD.retrieved_at,
            OLD.created_at, NEW.source_hash
        );
    ELSE
        -- Same content: keep when it was first seen. The writer sets
        -- created_at = now() on every upsert, which would otherwise hide it.
        NEW.created_at := OLD.created_at;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_archive_version
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_archive_version();

COMMIT;
