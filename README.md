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

## Security baseline

`POST /query` is fail-closed and requires the API key configured through
`SETU_API_KEY`. Send it in the `X-API-Key` header; never place it in a URL,
commit it, or log it:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SETU_API_KEY" \
  -d '{"query": "what is Digital Public Infrastructure"}'
```

`/health`, `/health/db`, and `/ready` remain public probe endpoints. They
expose only coarse service state, never credentials, connection strings, or
stack traces. Readiness returns `api_auth_not_configured` until
`SETU_API_KEY` is set.

Query traffic is limited in memory using `QUERY_RATE_LIMIT` requests per
`QUERY_RATE_WINDOW_SECONDS` (defaults: 10 per 60 seconds). The limiter is
global to one API process: it is neither shared across workers/replicas nor
durable across restarts. Replace it with a distributed gateway or Redis-backed
limit before horizontal scaling.

Request safety and browser access are controlled by:

| Variable | Default | Purpose |
|---|---:|---|
| `MAX_REQUEST_BODY_BYTES` | `16384` | Reject oversized `/query` request bodies with HTTP 413. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated exact browser origins; `*` is rejected. |

CORS allows only GET, POST, and OPTIONS with `Content-Type` and `X-API-Key`;
credentials are disabled. Responses include `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control:
no-store`, and the existing `X-Request-ID`. A Content Security Policy is not
set because SETU is a JSON API and the built-in interactive API documentation
loads its own browser assets.

GitHub Actions runs Python 3.11 compilation, all mocked unit tests, `pip
check`, and Compose configuration validation on pushes and pull requests. CI
does not require `.env`, PostgreSQL, provider/API keys, model artifacts,
Docker builds, external LLM calls, or BGE downloads. Dependency installation
does include the production Python packages; model weights are never fetched.

## Container and supply-chain hardening

The API Dockerfile uses a multi-stage build. Compilers and development headers
remain in the builder stage; the final stage contains the installed virtual
environment, the runtime `libgomp1` library, and only `app/` plus `ingestion/`.
It runs as the dedicated `setu` user with stable UID/GID `10001:10001`.
Python is fixed at the currently validated `3.11.16` patch release, and the
formerly floating direct application requirements are fixed to the versions
already installed in the validated image. Transitive dependencies are not yet
hash-locked; the generated SBOM records what CI actually resolved.

Default Compose ports bind only to `127.0.0.1`, and application source mounts
are read-only. The Hugging Face cache remains writable in the local-development
configuration so a missing PyTorch model can be acquired deliberately. An
existing cache created by the former root container may need a one-time
ownership migration after the hardened image is built:

```bash
docker compose run --rm --no-deps --user 0 api \
  sh -c 'chown -R 10001:10001 /cache/huggingface'
```

Review the target volume before running that command. It changes ownership
only; it must never be replaced with broad permission changes such as
`chmod 777`.

For a deployment-oriented configuration, combine the base file with the
production overlay:

```bash
docker compose -f docker-compose.yml -f compose.production.yml config
docker compose -f docker-compose.yml -f compose.production.yml up -d
```

The overlay removes host-published ports (the API remains reachable as
`api:8000` on the private Compose network), removes development source mounts,
makes the root filesystem and cached models read-only, provides a constrained
64 MiB `/tmp`, drops all Linux capabilities, and enables
`no-new-privileges`. Model downloads are disabled in that configuration, so
the selected backend's artifacts must already exist. Cloud ingress should
publish only the API through TLS; PostgreSQL should remain private.

Dependency auditing and SBOM generation use tools isolated in
`requirements-security.txt`; they do not modify application versions:

```bash
python -m pip install -r requirements.txt -r requirements-security.txt
python -m pip_audit --local --progress-spinner off \
  --format json --output pip-audit.json
cyclonedx-py environment --output-format JSON \
  --output-file setu-sbom.cdx.json
```

The CycloneDX document covers packages installed in that Python environment.
CI runs both commands and retains the JSON audit and CycloneDX JSON SBOM as a
30-day `supply-chain-reports` artifact. Vulnerability results are visibility,
not proof of security: CI records a failing audit step and preserves its report
without automatically upgrading the deliberately pinned ML/runtime stack.
Generated reports are CI artifacts and should not be committed.

## Where to go next
Open `docs/ROADMAP.md` — it walks through exactly what to build each week,
mapped onto this scaffold, in the same order as the original project plan
(ingestion → hybrid retrieval → agent → API/frontend → eval/MLOps → stretch).
