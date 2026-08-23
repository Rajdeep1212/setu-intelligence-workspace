CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,              -- e.g. 'PIB', 'myScheme'
    title TEXT,
    language CHAR(2) NOT NULL,         -- 'en', 'hi', 'bn'
    url TEXT UNIQUE,
    raw_text TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    language CHAR(2) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024),            -- dim for bge-m3 / multilingual-e5-large
    tsv tsvector,                      -- full-text search leg of hybrid retrieval
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks(document_id);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);

CREATE OR REPLACE FUNCTION chunks_tsv_trigger() RETURNS trigger AS $$
begin
  new.tsv := to_tsvector('simple', coalesce(new.content, ''));
  return new;
end
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks;
CREATE TRIGGER chunks_tsv_update BEFORE INSERT OR UPDATE
    ON chunks FOR EACH ROW EXECUTE FUNCTION chunks_tsv_trigger();

CREATE TABLE IF NOT EXISTS query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    language CHAR(2),
    route TEXT,                        -- which agent tool was selected
    response_text TEXT,
    citations JSONB,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_log_id UUID REFERENCES query_logs(id) ON DELETE CASCADE,
    rating SMALLINT,                   -- thumbs up/down as 1 / -1
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_name TEXT,
    metric_name TEXT,                  -- 'faithfulness', 'precision_at_5', etc.
    language CHAR(2),
    score FLOAT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eligibility_criteria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_name TEXT UNIQUE NOT NULL,
    criteria JSONB NOT NULL,           -- e.g. {"max_income": 250000, "state": "WB"}
    source_document_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ DEFAULT now()
);
