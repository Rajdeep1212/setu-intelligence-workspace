# Setu Build Roadmap

This maps the original project plan onto the starter scaffold, one week at a
time. Each week assumes the previous one's tests/checks pass before moving on.

## Week 0 — Environment (half a day)
- [x] Docker Compose skeleton (this repo)
- [ ] Free Postgres+pgvector instance on Supabase or Neon (for later
      deployment — local Docker Postgres is fine for all of dev)
- [ ] A free Groq API key (fast Llama 3.x) or Gemini free-tier key
- [ ] `docker compose up --build`, confirm both `/health` and `/health/db`
      return `ok`

## Week 1 — Ingestion + storage
**Goal:** raw documents → chunked, embedded rows in Postgres.

1. Pull a small seed set: ~20–30 documents per language to start, not the
   full corpus. PIB publishes many releases in English, Hindi, and Bengali
   for the same story — that parallelism is useful for later cross-lingual
   consistency checks. Pull a handful of scheme pages from myScheme.gov.in too.
2. Implement `load_documents()` in `ingestion/ingest.py`.
3. Implement `chunk_text()` — language-aware. Hindi/Bengali sentence
   boundaries (danda `।`) differ from English periods; naive splitting will
   cut chunks mid-sentence.
4. Implement `embed_chunks()` with `sentence-transformers` + `BAAI/bge-m3`.
   Add `sentence-transformers` and `torch` from `requirements-later.txt` to
   `requirements.txt` this week.
5. Implement `write_to_db()` — insert into `documents`, then `chunks`.
6. Sanity check in `psql`:
   ```sql
   SELECT language, count(*) FROM chunks GROUP BY language;
   ```

## Week 2 — Hybrid retrieval + reranking
**Goal:** given a query, return the best 5 chunks, in the right language(s).

1. **Dense leg:** cosine similarity against `chunks.embedding` using
   pgvector's `<=>` operator.
2. **Keyword leg:** Postgres full-text search against `chunks.tsv`.
3. Merge both with reciprocal rank fusion (simple, no extra dependency) to
   get a top-20 candidate set.
4. Rerank top-20 → top-5 with a cross-encoder (`BAAI/bge-reranker-v2-m3`,
   loads via the `FlagEmbedding` package).
5. Wire this into `/query` in `app/main.py`, replacing the placeholder.
6. Build a small hand-labeled eval set (20–30 query → relevant-chunk pairs,
   spread evenly across languages) and compute precision@5 before moving on.
   This set becomes your Week 5 regression baseline — keep it in version
   control.

## Week 3 — Agent + structured output
**Goal:** route between "answer from documents" and "check eligibility."

1. Stand up a `LangGraph` graph: a router node plus two tool nodes —
   `retrieve_docs` (Week 2 pipeline) and `check_eligibility` (SQL lookup
   against `eligibility_criteria`).
2. Populate `eligibility_criteria` by hand for a handful of schemes (income
   caps, state restrictions, age limits) — this doesn't need to be automated.
3. Use `instructor` (or plain function-calling) to force the LLM's final
   answer into the `QueryResponse` shape in `app/schemas.py`, including
   citations.
4. Point the LLM call at Groq or Gemini, whichever key is set in `.env`.

## Week 4 — API hardening + frontend
1. Add SSE streaming to `/query` (`sse-starlette`) for token-by-token
   responses.
2. Add an API-key header check and per-key rate limiting — in-memory is fine
   for a portfolio project; note in the README that Redis would be the
   production choice.
3. Build the Streamlit frontend: language selector, chat box, citations
   panel.
4. Add a minimal admin view: ingestion status, recent queries, thumbs
   up/down feedback.

## Week 5 — Evaluation + MLOps
1. Wire `RAGAS` (faithfulness, answer relevance, context recall) against the
   Week 2 eval set; log results into `eval_runs`.
2. Add `MLflow` tracking around eval runs and retrieval experiments (e.g.
   dense-only vs. hybrid vs. hybrid+rerank) so you have a defensible ablation
   to talk about in interviews.
3. Add `Langfuse` tracing around the agent graph to inspect tool-routing
   decisions.
4. Write a GitHub Actions workflow that runs the eval suite on every PR and
   fails the build below threshold (from the original plan: faithfulness
   ≥0.90, precision@5 ≥0.80, refusal accuracy ≥90%, p95 latency <3.5s, agent
   tool-selection accuracy ≥90%).
5. Break every metric down **per language**, not just in aggregate — this
   is the detail that differentiates the project.

## Week 6 — Stretch: embedding merging
1. Fine-tune or adapt two language-specialized embedding checkpoints from a
   shared base (one Hindi-leaning, one Bengali-leaning).
2. Apply TIES/DARE-TIES merging to combine them into a single multilingual
   embedding model.
3. Re-run the Week 2/5 eval set through the merged model; compare
   precision@5 per language against the un-merged `bge-m3` baseline.
4. This is the single highest-differentiation result in the project —
   budget real time for it, and be ready to explain *why* merging helped (or
   didn't) in an interview.

## Deployment (ongoing, not a single week)
- Postgres+pgvector → Supabase or Neon free tier
- API → Render, Fly.io, or Hugging Face Spaces
- Frontend → Streamlit Community Cloud
- GitHub Actions → build + push on merge to `main`, gated by the Week 5 eval
  checks
