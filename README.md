# Setu — Multilingual Agentic RAG Assistant (Starter Scaffold)

A runnable skeleton for the Setu project: Postgres + pgvector and a FastAPI app
are wired up and healthy out of the box, with clear extension points for each
week of the build plan in `docs/ROADMAP.md`.

## What's included
- **Docker Compose**: Postgres 16 with the `pgvector` extension + the FastAPI app
- **DB schema** (`db/init.sql`): `documents`, `chunks` (vector column + full-text
  search column), `query_logs`, `feedback`, `eval_runs`, `eligibility_criteria`
- **FastAPI app** with `/health`, `/health/db`, and a stubbed `/query` endpoint
  returning the shape defined in `app/schemas.py`
- **`ingestion/ingest.py`**: the four functions you'll implement in Week 1
- **`docs/ROADMAP.md`**: the full week-by-week plan

## Prerequisites
- Docker + Docker Compose
- Python 3.11 (only needed if you run scripts like ingestion outside Docker)
- A free Groq or Gemini API key — needed from Week 3 onward, not for this scaffold

## Quickstart
```bash
cp .env.example .env
docker compose up --build
```

Then check:
- http://localhost:8000/health → `{"status": "ok"}`
- http://localhost:8000/health/db → `{"db": "ok"}`

If `/health/db` fails on the very first run, give Postgres a few seconds to
finish executing `db/init.sql`, then retry.

## Project layout
```
setu/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt           # API deps — installed inside the Docker image
├── requirements-ingestion.txt # ingestion deps — installed in a local venv, not Docker
├── requirements-later.txt     # reference — add to requirements.txt week by week
├── .env.example
├── app/
│   ├── main.py                 # FastAPI app + routes
│   ├── config.py                # env-based settings
│   ├── db.py                    # async SQLAlchemy engine/session
│   └── schemas.py                # Pydantic request/response models
├── db/
│   └── init.sql                  # schema, run automatically on first container start
├── ingestion/                     # Week 1 — implemented, run locally (see below)
│   ├── scraper.py                  # fetch PIB press releases + language variants
│   ├── chunking.py                  # language-aware sentence-boundary chunking
│   ├── embeddings.py                 # bge-m3 embedding
│   ├── db_writer.py                   # async writes to documents/chunks
│   └── ingest.py                       # CLI entry point, wires the above together
├── app/retrieval/                 # Week 2 — implemented
│   ├── dense.py                    # pgvector cosine search
│   ├── keyword.py                   # Postgres full-text search
│   ├── fusion.py                     # reciprocal rank fusion
│   ├── rerank.py                      # bge-reranker-v2-m3 cross-encoder
│   └── pipeline.py                     # wires the above into retrieve()
├── app/agent/                      # Week 3 — implemented
│   ├── llm.py                       # Groq/Gemini behind one generate_structured() call
│   ├── models.py                     # RouteDecision, GeneratedAnswer (instructor response models)
│   ├── state.py                       # AgentState shared across graph nodes
│   ├── tools.py                        # retrieve_docs / check_eligibility tool functions
│   └── graph.py                         # LangGraph wiring: route -> tool -> generate
├── eval/                          # Week 2 — implemented
│   ├── eval_set.jsonl               # hand-labeled query -> relevant chunks (you fill this in)
│   └── precision_at_k.py             # precision@5, overall + per language
└── docs/
    └── ROADMAP.md                       # full week-by-week build plan
```

## Running Week 1 ingestion
Ingestion runs outside Docker, in its own virtualenv, so the always-on API
container doesn't have to carry `torch`/`sentence-transformers`:

```bash
python3.11 -m venv .venv-ingest
source .venv-ingest/bin/activate
pip install -r requirements-ingestion.txt

# Postgres must already be running (docker compose up -d db)
export INGEST_DATABASE_DSN="postgresql://setu:setu@localhost:5432/setu"

python -m ingestion.ingest --prids 2235812,2224505,2206477
```

Where to get PRIDs: browse pib.gov.in, open a release, and copy the number
from `?PRID=...` in the URL (also shown as "Release ID" at the bottom of the
article). Pick ~20-30 releases across a few ministries to start — see
`docs/ROADMAP.md` (Week 1) for the full rationale, and the docstring at the
top of `ingestion/scraper.py` for a couple of things to double-check against
the live site before a full run (it couldn't be tested against pib.gov.in
from this build environment).

## Trying Week 2 retrieval
Once you've ingested some documents (Week 1) and rebuilt the API image
(`docker compose up --build` — the image is bigger now, see the note in
`requirements.txt`):

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "how do I get a PAN card"}'
```

The `answer` field is still a placeholder (raw concatenated chunks) until
Week 3 adds LLM generation — this endpoint exists to let you sanity-check
retrieval quality end to end before adding the agent layer on top.

Build `eval/eval_set.jsonl` (see `eval/README.md`) and run:
```bash
python -m eval.precision_at_k
```

## Trying Week 3 — the agent
Set `GROQ_API_KEY` (or `GEMINI_API_KEY`) in `.env` — Groq's free tier is the
simpler path (see the note at the top of `app/agent/llm.py` for why). Then
seed a few eligibility rows and rebuild:

```bash
# with the ingestion venv active (has asyncpg):
export INGEST_DATABASE_DSN="postgresql://setu:setu@localhost:5432/setu"
python -m ingestion.seed_eligibility

docker compose up --build
```

Try both routes:
```bash
# should route to retrieve_docs
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
  -d '{"query": "what is Digital Public Infrastructure"}'

# should route to check_eligibility
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
  -d '{"query": "am I eligible for PM Kisan"}'
```

`route` in the response tells you which path the agent took — useful for
building the Week 3 tool-selection-accuracy eval mentioned in
`docs/ROADMAP.md`.

## Where to go next
Open `docs/ROADMAP.md` — it walks through exactly what to build each week,
mapped onto this scaffold, in the same order as the original project plan
(ingestion → hybrid retrieval → agent → API/frontend → eval/MLOps → stretch).
