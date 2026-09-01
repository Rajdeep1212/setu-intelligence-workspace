# SETU Intelligence Workspace

SETU is an evidence-first workspace for exploring India’s digital public
infrastructure and an explicitly quarantined eligibility-experience prototype. It combines a
multilingual retrieval-augmented generation (RAG) backend with a recruiter-ready
Next.js interface that makes claim-to-citation relationships and source context
visible alongside each answer. Model-reported confidence remains uncalibrated
engineering metadata rather than a user-facing correctness score.

This repository is a portfolio case study in building an AI system whose claims
can be inspected. It does not claim production scale, continuous public
availability, or commercial adoption.

## Why SETU

Policy and public-infrastructure information is often distributed across long,
multilingual source documents. A fluent answer alone is not enough: a reader
needs to know which evidence was retrieved, whether citations are real, and
where the system’s confidence should stop.

SETU addresses that problem with:

- hybrid dense and keyword retrieval over a private PostgreSQL/pgvector corpus;
- reranking before answer generation;
- agent routing with personal eligibility requests quarantined before criteria lookup or answer generation;
- multilingual answer controls for English, Hindi, and Bengali;
- claim-specific citation selection, retrieved-ID membership validation, stable ordering, and de-duplication;
- deterministic checks for digit-form claims and a small reviewed multilingual
  number-word/ordinal lexicon;
- a secure Next.js backend-for-frontend (BFF) boundary; and
- explicit abstention and safe error behavior when evidence or configuration is
  insufficient.

## Product experience

The frontend includes four portfolio views:

- **[Workspace](frontend/src/app/workspace/page.tsx)** — a guided intelligence
  surface with sanitized claim-to-citation demonstration data and a non-decision eligibility preview.
- **[Sources](frontend/src/app/sources/page.tsx)** — a bounded evidence explorer
  with search, language, eligibility, pagination, and source-detail states.
- **[System trust](frontend/src/app/system/page.tsx)** — a content-safe view of
  identity, secret, networking, database, and grounding controls.
- **[Case study](frontend/src/app/case-study/page.tsx)** — the engineering journey
  and evidence from one controlled authenticated cloud query.

Demo mode is the default. Its fixtures are sanitized and make no backend,
provider, database, or cloud request.

## Architecture

```mermaid
flowchart LR
    B[Browser] --> N[Next.js application]
    N --> F[Server-only BFF]
    F -. demo mode .-> D[Sanitized fixtures]
    F -. controlled integration .-> I[IAM-authenticated Cloud Run API]
    I --> A[FastAPI + LangGraph]
    A --> R[Hybrid retrieval + reranking]
    R --> Q[(Private Cloud SQL<br/>PostgreSQL + pgvector)]
    A --> L[Structured LLM completion]
    A --> G[Citation membership + numerical checks]
    S[Secret Manager] --> I
    V[Direct VPC path] --> Q
```

The browser sends same-site requests to Next.js API routes. Credentials stay in
the server process; they are never exposed as `NEXT_PUBLIC_` configuration. The
current local adapter accepts only an HTTP loopback origin. The future cloud
adapter is deliberately disabled until a deployed frontend identity can obtain
an audience-bound IAM token server-side.

The deployed backend is private-by-authentication: Cloud Run ingress is
internet-reachable but has no public principal, so IAM authentication is
required before the application API-key check. Cloud SQL has a private address
only and is reached through private networking. See
[Architecture](docs/architecture.md) and [Security](docs/security.md).

## Evidence-linked query workflow

1. Validate request size, schema, origin, authentication, and rate limit.
2. Ask the structured router to select `retrieve_docs` or
   `check_eligibility`.
3. For retrieval, combine pgvector similarity and PostgreSQL full-text search
   with reciprocal-rank fusion, then rerank the candidate set.
4. Generate a schema-constrained answer from the selected evidence.
5. Return typed answer sections with their claimed citation identifiers. Accept
   only identifiers present in the retrieved set; remove duplicate identifiers
   and duplicate evidence. This proves membership, not semantic entailment.
6. Check numeric claims against supporting evidence, including digits,
   currencies, units, and a small reviewed number-word/ordinal lexicon. A
   bounded correction completion is available when this check fails.
7. Return the answer, selected route, model-reported confidence, and citations,
   with a correlation ID in the response header—or a stable, content-safe
   error/abstention response.

Personal eligibility evaluation is quarantined. The current criteria are
illustrative, unverified demonstration data, so neither the frontend nor backend
produces an eligibility determination or sends an eligibility profile to a
provider. Production use requires reviewed, versioned rules with effective dates
and official-source provenance.

### Evidence trust contract

- **Retrieved citation** means the citation ID belongs to the retrieved result set.
- **Citation validated** means membership and deterministic de-duplication passed.
- **Evidence linked** means an answer section carries at least one validated
  retrieved citation ID.
- These automated checks do not prove semantic support. “Claim support reviewed”
  is reserved for separately recorded human or semantic evaluation.
- Provider confidence is self-reported and uncalibrated; it is shown only in the
  engineering details area.

## Technology

| Layer | Stack |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, TanStack Query, Zod, Radix UI |
| BFF | Next.js Route Handlers, same-site checks, bounded payloads, server-only secrets |
| API | Python 3.11, FastAPI, Pydantic, SQLAlchemy async, LangGraph |
| Retrieval | PostgreSQL 16, pgvector, full-text search, BGE-M3, BGE reranker, OpenVINO |
| Providers | Groq primary; Gemini adapter present but not used in the validated cloud query |
| Infrastructure | Docker, Artifact Registry, Cloud Run, Cloud SQL, Secret Manager, Direct VPC networking |
| Quality | unittest/pytest, Vitest, Testing Library, Playwright, ESLint, TypeScript, GitHub Actions |

## Current local and historical evidence baseline

The evidence frozen before publication records:

| Area | Verified result |
|---|---|
| Corpus | 8 documents / 239 chunks / 3 eligibility records |
| Backend regression suite | 112 tests passed in a network-disabled container |
| Frontend unit/integration suite | 25 default tests passed; 1 opt-in local integration test remains intentionally skipped by default |
| Browser suite | 9 Playwright tests passed |
| Offline evaluation | 60/60 deterministic fixture-replay cases passed; 20 each in English, Hindi, and Bengali |
| GitHub Actions | Four read-only `ubuntu-latest` quality jobs; no secrets, cloud credentials, artifacts, or model downloads |
| Frontend production build | Passed with Node.js 22 |
| Frontend dependency audit | 0 known vulnerabilities reported by `npm audit` |
| Cloud backend | 1 service; 1 active-ready revision at 100% traffic; 1 retained historical revision at 0% |
| Cloud health | Authenticated `/health`, `/health/db`, and `/ready` returned 200 |
| Controlled cloud query | Historical HTTP 200; `retrieve_docs`; model-reported confidence 0.9; 3 membership-validated citations; material claims manually reviewed |
| Query preservation | 1 external submission, no manual retry, no database query-log insertion |

The controlled query took approximately 69 seconds end to end. It is evidence
that the path worked once under a strict request budget, not a latency or
availability benchmark. Evaluation methods and boundaries are documented in
[Evaluation](docs/evaluation.md).

## Local development

### Requirements

- Node.js 22.x for the frontend (the validated runtime was Node.js 22)
- Python 3.11 for the backend
- Docker Desktop with Compose for the local PostgreSQL/API stack

### Safe frontend demo

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/workspace`. No environment file is required: demo
mode is the fail-safe default and uses only sanitized local fixtures. See the
[local demo guide](docs/local-demo.md) for routes and controlled adapter modes.

### Local backend

Copy the example file locally and replace every credential placeholder with a
local-only value. `.env` is ignored and must never be committed.

```bash
cp .env.example .env
docker compose up -d --build db api
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/health/db
curl --fail http://127.0.0.1:8000/ready
```

`/ready` is expected to fail closed until database, API authentication, one LLM
provider, and the selected inference backend are correctly configured. Never
put a provider key, application API key, database password, identity token, or
cloud identifier in a tracked file.

The backend health commands do not execute `/query`. A real query invokes a
provider and should be run only with an explicit request budget.

## Validation commands

Backend checks from the repository root:

```bash
python -m compileall -q app ingestion eval tests
python -m unittest discover -s tests -v
python -m eval.offline_evaluation
python scripts/ci_static_checks.py
python -m pip check
docker compose config --quiet
```

Frontend checks:

```bash
cd frontend
npm run typecheck
npm run lint
npm run test:run
npm run build
npm run test:e2e
npm audit
```

Playwright expects the safe local frontend to be running. The opt-in local BFF
test is intentionally excluded from the default suite unless its explicit
environment gate is set; it uses a loopback test transport, not the cloud
backend.

## Repository structure

```text
app/                    FastAPI, agent graph, grounding, security, retrieval
db/                     PostgreSQL/pgvector bootstrap schema
docs/                   Architecture, security, evaluation, demo, deployment
eval/                   Small multilingual regression fixtures and metrics
frontend/               Next.js application, BFF, tests, and demo fixtures
ingestion/              PIB fetch, language-aware chunking, embeddings, writes
scripts/                Isolated OpenVINO export helper
tests/                  Backend regression tests
.github/workflows/      Zero-spend full-stack quality workflow
```

## Security principles

- fail closed when identity, secret, provider, database, or model configuration
  is missing;
- keep browser-safe configuration separate from server-only credentials;
- use IAM plus application authentication, with no public Cloud Run principal;
- give runtime identities only the Cloud SQL and per-secret access they need;
- keep the database private, encrypted, deletion-protected, and free of public
  authorized networks;
- deploy immutable images and preserve failed historical revisions as audit
  evidence;
- return bounded schemas and content-safe diagnostics, never prompts, document
  bodies, credentials, or stack traces; and
- treat citations, numeric validation, and human review as controls—not proof
  that every answer is correct.

## Known limitations

- Production `query_logs` insertion is not implemented. If observability is
  added, structured Cloud Logging is preferred over granting the runtime
  database user write access only to populate that table.
- Exact successful Groq HTTP-attempt telemetry is unavailable, and the
  configured provider HTTP-attempt ceiling is higher than the normal two-step
  logical workflow.
- The historical deployed numeric guard detects digit expressions. This
  repository adds only a small reviewed number-word/ordinal lexicon; broader
  number language, code-mixed input, and transliteration remain limitations.
- The validated query took approximately 69 seconds.
- The deployed OCI image is approximately 3.37 GB and scale-to-zero can produce
  cold starts.
- Backend ingress is internet-reachable but IAM-protected; public principals
  remain absent.
- The current frontend is production-quality locally, but public frontend
  hosting and production session authentication are not complete.
- The alerts-only cloud budget is not a spending cap, and the Cloud SQL trial
  requires timely teardown.
- The evaluation sets are small deterministic regression fixtures, not a live
  retrieval/provider benchmark or statistically robust accuracy study.
- Eligibility is an interaction preview only. Unverified placeholder criteria
  are quarantined and cannot produce a positive or negative determination.
- Citation validation proves retrieved-ID membership and de-duplication, not
  semantic entailment; model-reported confidence is uncalibrated.

## Screenshots

No screenshots are published in this revision because the controlled in-app
capture runtime was unavailable during the publication audit. The interface is
fully reproducible in sanitized demo mode using the [local demo](docs/local-demo.md)
instructions; no image or production result has been invented as a substitute.

## Further reading

- [Architecture](docs/architecture.md)
- [Security model](docs/security.md)
- [Evaluation and validated evidence](docs/evaluation.md)
- [Generated offline evaluation report](docs/offline-evaluation-report.md)
- [Local demo guide](docs/local-demo.md)
- [Citation-grounding design](docs/CITATION_GROUNDING.md)
- [Deployment runbook](docs/DEPLOYMENT.md)
- [Build roadmap](docs/ROADMAP.md)

## Roadmap

The next identified engineering step is privacy-safe query telemetry and stage
timing; it is not implemented here. A later separately authorized frontend
deployment still requires a dedicated service identity, server-side
audience-bound IAM tokens, and production session authentication. No cloud or
provider validation occurred during the evidence-integrity milestone.

## Data and licensing

The ingestion code targets public PIB release pages, but this repository does
not publish the live database, backups, embeddings, or full source-document
bodies. The tracked evaluation fixtures contain short authored queries, labels,
expected facts, and chunk identifiers for regression testing.

No `LICENSE` file is included. Public visibility makes the work reviewable; it
does not grant an open-source reuse license.

## Author

Built and documented by **Rajdeep Mahanty**.
