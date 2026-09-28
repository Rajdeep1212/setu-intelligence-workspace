# SETU — Clientell two-minute demo script

## Recording status

This package uses **recorded evidence** from previously verified connected
journeys. It does not present a new live query. The connected runs used real
local OpenVINO retrieval and reranking against staging PostgreSQL; route and
answer generation at the external-provider boundary were deterministic. The
performance and latency quality gate remains open.

## Spoken script

<!-- SPOKEN SCRIPT START -->

### 0:00–0:15 — User problem

Government-service information is scattered across portals. SETU is a
multilingual public-information assistant that answers questions from official
evidence and shows where each answer came from.

### 0:15–0:35 — Architecture

A question enters FastAPI and LangGraph. SETU combines pgvector dense search
with PostgreSQL full-text search, reranks selected evidence, calls the chat
model, then validates citations and numbers before returning a bounded response.

### 0:35–1:00 — Grounded working result

This is recorded evidence from a connected local test, not a live query. I
asked, “How do I register for e-Shram and what do I need?” SETU answered that I
need an Aadhaar number and Aadhaar-linked mobile number. The citation maps to
the official e-Shram FAQ passage, while separate controls lead to official
registration and help pages.

### 1:00–1:30 — Real failure and diagnosis

During development, Groq returned a structured-output `tool_use_failed` error.
I traced it to the request format and forced-tool path created by Instructor. I
removed that inappropriate Groq route and used native strict JSON-schema output.
Regression tests now require requests without tools or tool choice, while
grounding checks reject unknown citations and unsupported numbers.

### 1:30–1:50 — Reliability and evaluation

The interface also produced a recorded Hindi PMSBY answer from an official
English passage. Sixty of sixty small deterministic fixtures passed across
English, Hindi, and Bengali, including abstention and numerical checks. These
are regression results, not universal accuracy.

### 1:50–2:00 — Closing statement

Local inference latency is still too high, so the performance gate remains
open. The main engineering problem wasn’t making the model answer. It was
knowing when I could trust that answer and preventing unsupported output from
reaching the user.

<!-- SPOKEN SCRIPT END -->

## Demonstration evidence

| Item | Verified record |
|---|---|
| Primary query | `How do I register for e-Shram and what do I need?` |
| Response language | English |
| Result status | Recorded connected evidence; HTTP 200, `answered` |
| Answered fact | Registration requires an Aadhaar number and an Aadhaar-linked mobile number. |
| Official source | *e-Shram National Database of Unorganised Workers*, Ministry of Labour and Employment, Government of India |
| Useful passage | “What essential documents are required by the worker to register on e-Shram? — Aadhaar Number — Aadhaar linked Mobile number.” |
| Citation mapping | Answer section → chunk `15a9cf41-9e5b-4918-9b25-33c4b5d3f9b4` → official FAQ record |
| Recorded public source | `https://eshram.gov.in/faqs` |
| Recorded public application destination | `https://register.eshram.gov.in/` |
| Recorded public help destination | `https://gms.eshram.gov.in/` |
| Multilingual moment | Recorded Hindi query `PMSBY के लिए कौन पात्र है?`; Hindi answer cites the Department of Financial Services passage stating that all bank-account holders except institutional account holders are eligible to subscribe. |
| Multilingual citation | Chunk `5b38ec36-0a1a-40e8-94b2-e6a8e07049ff`; `https://financialservices.gov.in/pmsby` |

The URLs above are public destinations stored in the verified response record.
Confirm that they still resolve immediately before recording; this package does
not claim a fresh network check.

## Claim verification ledger

| Demo claim | Repository evidence | Boundary |
|---|---|---|
| FastAPI and LangGraph orchestrate the request. | `app/main.py`, `app/agent/graph.py`, `README.md`, and the connected-runtime checkpoint | The connected test used installed LangGraph 1.2.11. |
| Retrieval combines pgvector dense search and PostgreSQL full-text search, then fuses and reranks candidates. | `app/retrieval/pipeline.py`, `app/retrieval/dense.py`, `app/retrieval/keyword.py`, `app/retrieval/fusion.py`, `app/retrieval/rerank.py` | Describes the implemented pipeline; it does not claim corpus-wide coverage. |
| Answers are checked against retrieved citation IDs and numerical evidence. | `app/agent/graph.py`, `app/grounding.py`, `app/numerical_grounding.py`, `docs/CITATION_GROUNDING.md` | Citation membership does not prove semantic entailment. |
| English, Hindi, and Bengali flows are covered. | Saved connected English/Hindi/Bengali records and `docs/offline-evaluation-report.md` | Connected results are recorded; the 60/60 suite is deterministic fixture replay. |
| Insufficient evidence produces abstention. | `app/agent/graph.py`, `tests/test_grounding.py`, and the recorded unsupported-claim journey | This is evidence-based fail-closed behavior, not a general factuality guarantee. |
| Groq’s forced tool route was replaced with native strict JSON-schema output. | Commit `938462867ce213d430ff26832ca6fd2cdf3f3db4`; parent used `instructor.Mode.TOOLS`; current `app/agent/llm.py`; `tests/test_llm_structured_output.py` | The historical failure shape is preserved by a sanitized regression fixture. Exact successful provider-attempt telemetry is unavailable. |
| Docker, Cloud Run, Cloud SQL, and GitHub Actions exist in the project history. | `Dockerfile`, Compose files, `README.md`, `docs/architecture.md`, `docs/DEPLOYMENT.md`, `.github/workflows/ci.yml` | They are omitted from the spoken two-minute story. The frontend is not publicly deployed, and no production-readiness claim is made. |

## Supporting copy

**Video title:** SETU: Building a multilingual public-information assistant that earns trust with evidence.

**Video description:** SETU answers public-service questions from reviewed
official passages, then maps claims to citations and separates source,
application, and help links. This two-minute walkthrough uses recorded connected
evidence and explains a real structured-output failure, its correction, and the
system’s current latency limitation.

**Portfolio summary — 50 words:** SETU is a multilingual public-information
assistant built with FastAPI, LangGraph, PostgreSQL, pgvector, hybrid retrieval,
and reranking. It answers from official evidence, validates citation membership
and numerical claims, exposes trusted action links, and abstains when support is
insufficient. Recorded English, Hindi, and Bengali journeys demonstrate the
workflow while latency remains unresolved.

**Clientell application-field description:** Built SETU, a multilingual
official-evidence assistant, and engineered its retrieval, structured-output,
grounding, citation, abstention, evaluation, and failure-handling controls. The
demo uses recorded verified journeys and states the unresolved local-inference
latency gate explicitly.

## Likely interviewer follow-ups

### What failed?

A Groq structured-output request returned `tool_use_failed` while the Groq
client was wrapped in Instructor’s forced-tools mode. The repository does not
retain unsafe response content or exact successful-attempt telemetry, so the
claim is limited to the recorded error category and request pathway.

### How did you detect it?

The provider failure surfaced as a bounded application error. Investigation
compared the outgoing request shape with the provider’s native structured-output
path. The correction also added stage-aware, sanitized diagnostics that record
error categories without prompts, generated content, authorization headers, or
keys.

### How did you measure correctness?

I used layered checks: strict response schemas, retrieved-ID membership,
claim-specific citations, numerical grounding, language checks, abstention
fixtures, connected journey inspection, and a deterministic 60-case offline
suite. These checks measure defined contracts and regression behavior; they do
not establish universal accuracy or semantic entailment.

## Claims deliberately omitted

- Coverage of all Indian government schemes or traffic rules: the indexed and
  tested corpus does not support either claim.
- Production readiness or a completed quality gate: the current checkpoint
  keeps the gate open because local inference takes several minutes.
- A live demo result: no inference or provider call was made for this package.
- Public frontend deployment: repository evidence says frontend hosting,
  production session authentication, and audience-bound frontend identity are
  unfinished.
- Fresh Cloud Run, Cloud SQL, CI, dependency-audit, or official-link status:
  historical repository evidence exists, but none was rechecked in this task.
- Statistically robust accuracy, live-provider answer quality, calibrated
  confidence, or semantic entailment: the available evaluations do not prove
  these claims.
