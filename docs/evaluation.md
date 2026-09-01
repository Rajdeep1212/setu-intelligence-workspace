# Evaluation and evidence

SETU distinguishes deterministic regression evidence from one controlled live
cloud execution. Neither is presented as a production accuracy or performance
study.

## Local regression evidence

The publication baseline records:

| Check | Result |
|---|---:|
| Backend tests | 112 passed |
| Frontend default unit/integration tests | 25 passed; 1 opt-in integration case skipped by default |
| Playwright browser tests | 9 passed |
| TypeScript | Passed |
| ESLint | Passed with zero warnings |
| Next.js production build | Passed on Node.js 22 |
| `npm audit` | 0 known vulnerabilities reported |

Backend tests cover configuration, authentication, rate limiting, language
selection, retrieval backends, structured LLM handling, citation grounding,
numeric validation, source endpoints, safe errors, and operational probes.

Frontend tests cover schema adapters, BFF fail-closed behavior, sanitized demo
workflows, eligibility interactions, source exploration, accessibility, and
responsive routes. The default suite cannot make a live backend request. The
local integration case is guarded by an explicit opt-in and a loopback-only
origin policy.

## Versioned offline evaluation

Evaluation `4C-2.1` adds 60 unique deterministic cases, balanced at 20 each
for English, Hindi, and Bengali:

| Category | Cases | Provenance |
|---|---:|---|
| Retrieval-label replay | 15 | Corpus-linked labels |
| Grounding contract replay | 15 | Mock/synthetic |
| Numerical grounding | 15 | Mock/synthetic |
| Routing guard | 9 | Mock/synthetic |
| Adversarial configured behavior | 6 | Mock/synthetic |

The answerability split is 27 answerable, 3 unanswerable, and 30 cases where
answerability is not applicable. The provenance split is 15 corpus-linked and
45 mock/synthetic. The generated [offline report](offline-evaluation-report.md)
records 60/60 passing cases and the exact fixture-replay metrics.

The numerical cases cover ASCII and Unicode digits, the reviewed words one to
three and first to third in the three supported languages, lakh/crore, dates,
percentages, INR/USD identity, ranges, ordinals, and units. This is a small
lexical extension, not general number-language understanding. Code-mixed and
transliterated input remains a labeled limitation.

The routing score measures only the deterministic personal-eligibility
quarantine guard. Research and ambiguous routes are explicitly recorded as
provider-deferred and are not assigned a mocked provider decision. The prompt
hierarchy case proves configured separation and fail-closed behavior, not
universal prompt-injection resistance.

## Retrieval and grounding source fixtures

`eval/eval_set.jsonl` contains 15 short multilingual query-to-relevant-chunk
records. `eval/grounding_set.jsonl` contains 15 answerability and supporting
chunk annotations: answerable examples plus one unanswerable control for each
of English, Hindi, and Bengali.

The standalone grounding evaluator reports:

- citation precision;
- support coverage;
- unsupported-claim rate;
- citation redundancy;
- citation count; and
- grounded abstention behavior.

These are deterministic metrics over explicit reviewer judgments. Citation-ID
membership is not semantic entailment. Sentence
splitting is a review aid, not semantic entailment, and the small fixtures are
regression cases rather than a statistically representative benchmark.

## Frozen corpus

The validated database baseline contains:

- **8 documents**
- **239 chunks**
- **3 eligibility records**
- **0 production query-log rows**

The public repository does not contain the database, backups, embeddings, or
full stored corpus. Tracked fixtures contain only bounded authored examples,
labels, and identifiers needed to test the software.

## Controlled cloud validation

One previously authorized English `en-2` request exercised the deployed path
end to end:

| Evidence | Result |
|---|---|
| External submissions | 1 |
| Application `/query` executions | 1 |
| HTTP status | 200 |
| Route | `retrieve_docs` |
| Confidence | 0.9, model-reported and uncalibrated |
| Citations | 3 distinct, membership-validated, and resolved |
| Expected supporting citations | 2 of 2 present |
| Query-log count | 0 before and after |
| Manual retries | 0 |
| End-to-end latency | approximately 69 seconds |

The answer connected digital identity, payments, data exchange, interoperable
public rails, open APIs, and the JAM foundation. Manual review found each
material claim supported by the three stored chunks. The word “three” required
manual numeric review because the deployed revision's validator recognized
digit expressions, not word-form numbers; the review found no unsupported
numeric claim. The repository now has a small typed and tested number-word
extension, but the historical deployed image was not changed.

This historical manual review is why the case study may say those particular
claims were reviewed. The runtime validator alone proves retrieved-ID membership
and de-duplication, not semantic entailment. No new provider or cloud execution
occurred during the later evidence-integrity milestone.

## Provider accounting

The controlled execution used one route-selection completion and one
answer-generation completion. No correction completion, Gemini invocation,
fallback, or observable retry/error event occurred. The minimum proven Groq
HTTP-attempt count is therefore two.

The exact successful-attempt count is unavailable because attempt-level success
telemetry is not emitted. With up to two configured SDK retries for each of the
normal completions plus one conditional correction completion, the theoretical
HTTP-attempt ceiling is nine. That ceiling is capacity accounting, not evidence
that nine attempts occurred.

## Health evidence

Historical authenticated validation returned 200 for `/health`, `/health/db`,
and `/ready`. The initial liveness request included an approximately 13-second
cold start; the database and readiness checks were then approximately 72 ms and
65 ms. An unauthenticated health request was rejected with 403 in approximately
553 ms.

These are single validation observations. They are not percentiles or an SLA.
No endpoint or provider was called during repository publication.

## Reproducing deterministic checks

```bash
python -m unittest discover -s tests -v
python -m eval.offline_evaluation
python scripts/ci_static_checks.py
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run test:run
npm run build
npm run test:e2e
```

The offline evaluation is provider-free, network-free, and database-free. Live
retrieval evaluation (`python -m eval.precision_at_k`) remains a separately
authorized local release check requiring a compatible populated local database;
it must not target the protected cloud database.

GitHub Actions runs four `ubuntu-latest` jobs: backend quality, frontend
quality, browser smoke/accessibility, and lightweight publication safety. The
workflow has `contents: read`, references no repository secret or cloud
credential, builds no image, uploads no artifact, and pins every action to a
reviewed full commit SHA. The publication scan is deliberately described as
lightweight rather than a comprehensive security audit.

## Limitations and next evaluation work

- add structured Cloud Logging for request/provider attempt observability;
- expand beyond the current small reviewed number-word lexicon only with new
  labeled tests;
- report larger multilingual retrieval and grounding sets with confidence
  intervals;
- measure warm and cold latency distributions rather than one execution;
- separate retrieval, provider, and infrastructure latency; and
- retain the read-only runtime database role instead of writing observability
  events into `query_logs`.
