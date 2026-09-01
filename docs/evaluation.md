# Evaluation and evidence

SETU distinguishes deterministic regression evidence from one controlled live
cloud execution. Neither is presented as a production accuracy or performance
study.

## Local regression evidence

The publication baseline records:

| Check | Result |
|---|---:|
| Backend tests | 98 passed |
| Frontend default unit/integration tests | 18 passed |
| Opt-in local BFF integration test | 1 passed separately |
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

## Retrieval and grounding fixtures

`eval/eval_set.jsonl` contains 15 short multilingual query-to-relevant-chunk
records. `eval/grounding_set.jsonl` contains 15 answerability and supporting
chunk annotations: answerable examples plus one unanswerable control for each
of English, Hindi, and Bengali.

The grounding evaluator reports:

- citation precision;
- support coverage;
- unsupported-claim rate;
- citation redundancy;
- citation count; and
- grounded abstention behavior.

These are deterministic metrics over explicit reviewer judgments. Sentence
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
| Confidence | 0.9 |
| Citations | 3 distinct, valid, and resolved |
| Expected supporting citations | 2 of 2 present |
| Query-log count | 0 before and after |
| Manual retries | 0 |
| End-to-end latency | approximately 69 seconds |

The answer connected digital identity, payments, data exchange, interoperable
public rails, open APIs, and the JAM foundation. Manual review found each
material claim supported by the three stored chunks. The word “three” required
manual numeric review because the deployed validator recognizes digit
expressions, not word-form numbers; the review found no unsupported numeric
claim.

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
python -m eval.precision_at_k
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run test:run
npm run build
npm run test:e2e
```

Retrieval evaluation needs a compatible populated local database. It must not
be pointed at the protected cloud database for portfolio validation.

## Limitations and next evaluation work

- add structured Cloud Logging for request/provider attempt observability;
- expand numeric validation to carefully reviewed word-form expressions;
- report larger multilingual retrieval and grounding sets with confidence
  intervals;
- measure warm and cold latency distributions rather than one execution;
- separate retrieval, provider, and infrastructure latency; and
- retain the read-only runtime database role instead of writing observability
  events into `query_logs`.
