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

## Optional OpenVINO local inference

PyTorch is the default and rollback-safe local retrieval backend:

```dotenv
LOCAL_INFERENCE_BACKEND=pytorch
```

For Intel CPU deployments, generate the validated FP32 OpenVINO artifacts
once in the isolated exporter environment. The named Hugging Face cache is
shared with the API service and reused across container recreations and
exporter runs; generated multi-gigabyte IR files remain under the Git-ignored
`models/openvino/` directory and are mounted read-only into the API container.

```bash
docker compose --profile openvino-export build openvino-export
docker compose --profile openvino-export run --rm openvino-export
```

After both artifact directories exist, opt in and rebuild the API:

```dotenv
LOCAL_INFERENCE_BACKEND=openvino
OPENVINO_MODEL_DIR=/models/openvino
```

```bash
docker compose up -d --build api
```

OpenVINO uses the same BGE-M3 and BGE reranker checkpoints, FP32 weights,
tokenization, CLS pooling, normalization, and ranking semantics. It uses more
memory than PyTorch in the validated CPU experiment. Missing, incomplete, or
non-FP32 artifacts fail explicitly on first retrieval initialization; there
is no silent fallback. To roll back immediately, set
`LOCAL_INFERENCE_BACKEND=pytorch` and recreate the API container.

## Operations and reliability

SETU exposes three probe surfaces with deliberately different semantics:

- `GET /health` is a liveness check. It returns `status` and the configured
  inference backend without touching the database or loading model weights.
- `GET /health/db` checks PostgreSQL and returns HTTP 503 with a safe error
  envelope when the database is unavailable.
- `GET /ready` checks PostgreSQL, LLM configuration, and local inference
  configuration. OpenVINO readiness verifies the required files but does not
  compile or run the multi-gigabyte models. It returns HTTP 503 with safe
  issue codes when the service should not receive query traffic.

Every response includes an `X-Request-ID` header. Application logs include
the same ID, selected backend, major initialization events, request duration,
and classified failures. Keys, full prompts, and document bodies are not
logged. Query errors use a stable `error.code`, `error.message`, and
`error.request_id` envelope; internal stack traces are not returned.

Operational configuration:

| Variable | Requirement |
|---|---|
| `DATABASE_URL` | Must be a `postgresql+asyncpg` URL with host and database. Compose supplies it. |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | At least one is required for readiness and queries; Groq takes precedence. |
| `LOCAL_INFERENCE_BACKEND` | `pytorch` (default) or `openvino`. Other values fail validation. |
| `OPENVINO_MODEL_DIR` | Container path containing both exported model directories. |

The two validated FP32 OpenVINO artifacts occupy about 4.28 GiB in total.
Milestone 3K observed approximately 2.70 GiB API memory use for a real
OpenVINO query within a 3.70 GiB Docker limit. This is validation evidence,
not a production-capacity claim. Do not run loaded PyTorch and OpenVINO API
workers concurrently under that limit.

Keep the PostgreSQL volume, `setu_hf_cache`, current API/database images, and
`models/openvino/` artifacts. When host disk space is low, inspect with
`docker system df` and remove only resources proven obsolete. Never use a
broad volume prune. The isolated exporter image can be removed after exports
are verified and rebuilt later from its pinned Dockerfile if needed.

Rollback to PyTorch by setting `LOCAL_INFERENCE_BACKEND=pytorch` and
recreating only the API service:

```bash
docker compose up -d --no-deps --no-build --force-recreate api
```

## Where to go next
Open `docs/ROADMAP.md` — it walks through exactly what to build each week,
mapped onto this scaffold, in the same order as the original project plan
(ingestion → hybrid retrieval → agent → API/frontend → eval/MLOps → stretch).
