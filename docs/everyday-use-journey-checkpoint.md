# SETU everyday-use journey checkpoint

## Local inference latency milestone — 2026-09-20

**NO OPTIMIZATION RETAINED; QUALITY GATE REMAINS OPEN.**

Branch `recovery/codex-2026-09-14` remains at
`908ad3db0ee1cd0040da0d27cb956e56e4888574`. This milestone used the
established isolated staging runtime, real PostgreSQL retrieval, real local
OpenVINO embedding and reranking, grounding, response serialization, the real
Next.js BFF, and browser rendering. Only route selection and answer generation
at the external-provider boundary were deterministic. HTTP clients were patched
to fail closed for outbound calls, and the evidence endpoint recorded zero live
provider calls before the experiment.

### Measured cause

The installed OpenVINO 2026.3.1 runtime compiled the existing FP32 `bge-m3`
embedding model and FP32 `bge-reranker-v2-m3` reranker once per server. The
reranker used the `LATENCY` performance hint, one stream, four inference
threads, and disabled hyperthreading. Repeated initialization was ruled out.

The two OpenVINO weight files are 2,266,886,288 and 2,271,088,788 bytes, or
about 4.23 GiB together, while the Docker VM exposes 3.699 GiB. Observed process
memory reached 2.737 GiB, and embedding and reranking times varied by minutes.
The supported diagnosis is model/page pressure from keeping both FP32 models in
the constrained VM. SQL, grounding, and serialization are much smaller. This
also explains why a reranker-only result did not transfer to the complete
runtime.

The prior five warm browser observations were 482.715, 246.527, 251.037,
597.492, and 371.618 seconds; their median is 371.618 seconds. No p95 is claimed.
The representative English baseline broke down as follows:

| Stage | Baseline | Rejected batch-4 candidate |
|---|---:|---:|
| Cold load/compile | 389.389 s | 218.270 s; variable startup, not credited as an optimization |
| Query embedding | 200.119 s | 233.047 s |
| Dense SQL | 8.409 s | 5.381 s |
| Keyword SQL | 0.076 s | 0.078 s |
| Reranking | 264.938 s | Did not finish before the 600 s BFF limit |
| Retrieval | 473.921 s | Did not finish before the 600 s BFF limit |
| Grounding | Included in total and small | 1.159 s after late retrieval completion |
| Serialization | Included in total and small | 0.548 s after late retrieval completion |
| Backend total | 481.947 s | 886.706 s after the timed-out request continued; the tail was affected by the subsequently started, then cancelled, path |
| Browser total | 482.715 s, HTTP 200 | 602.006 s, HTTP 504 |

There was no observed inference queue or model lock, and each model initialized
once. The meaningful wait was CPU inference under memory pressure. The rejected
browser result was already 24.7% slower than baseline at timeout and at least
542 seconds beyond the provisional 60-second practical target.

### Controlled experiments and quality

The screen used the frozen English e-Shram query, the same 20 candidate pairs,
the same 16 unique passages, and expected official chunk
`15a9cf41-9e5b-4918-9b25-33c4b5d3f9b4`. It ran sequentially in a
network-disabled, reranker-only container.

| Experiment | Reranker time | Change from batch 20 | Quality result | Decision |
|---|---:|---:|---|---|
| Existing single batch of 20 | 97.082 s | baseline | Expected chunk rank 1 | Reference |
| Microbatch 4 | 28.258 s | 70.9% lower | Same top five and rank 1; max score delta `4.13e-9` | Advanced to full-runtime check, then rejected |
| Microbatch 1 | 29.135 s | 70.0% lower | Same top five and rank 1; max score delta `2.98e-7` | Rejected; slower than batch 4 |

The batch-4 candidate then ran through the complete isolated runtime. The first
representative English request returned the BFF's unchanged 504 at 602.006
seconds instead of the baseline HTTP 200 at 482.715 seconds. It had spent
233.047 seconds in embedding and still had not completed reranking. The
experiment was stopped, its production changes were reverted, and the
multilingual repetition was not run. Consequently there is no valid optimized
multilingual median. The integration response also failed the quality gate even
though the isolated reranker scores and ranks matched.

A third setting experiment was not justified: the bounded screen had already
shown that changing reranker batching cannot overcome the measured two-model
memory constraint. Precision changes, model conversion/replacement, downloads,
and additional dependencies were outside this milestone and were not attempted.

### Verification, retained files, and next action

The experiment changed no candidate selection, truncation, retrieval logic,
grounding, citation mapping, trusted links, language selection, clarification
state, or database data. All batch-size application edits and their temporary
benchmark script/tests were removed. The only retained test-harness addition is
the deterministic runtime evidence endpoint: it records source hashes, startup
time, installed LangGraph version, inference properties, provider calls,
database observations, and pool state while blocking outbound HTTP.

Experiment evidence is under
`F:\setu\.tools\latency-optimization-20260920`. The pre-existing application
and database services were not restarted. Audit-owned port 3201 and 18001
listeners were stopped. The affected regression results and final read-only
database/service checks are recorded below after verification.

Performance remains unacceptable and the overall quality gate stays **NO**.
The exact next action is a separately authorized resource experiment: run the
same FP32 artifacts and frozen connected query with at least 8 GiB assigned to
Docker, after an authorized Docker Desktop restart, and compare stage timings.
If that cannot meet the gate, scope a separate model conversion/replacement
milestone with the complete multilingual quality matrix. Do not mask the issue
with a longer timeout.

## Complete UX audit delta — 2026-09-20

**FUNCTIONAL CONNECTED GATE COMPLETE; ORDINARY-USE QUALITY GATE BLOCKED BY
LATENCY. DO NOT CLAIM PRODUCTION READINESS.**

Branch `recovery/codex-2026-09-14` remains at
`908ad3db0ee1cd0040da0d27cb956e56e4888574`. The connected runtime loaded and
hash-matched all eight audited working-tree source files, used FastAPI, installed
LangGraph 1.2.11, staging PostgreSQL, real OpenVINO embedding/reranking,
grounding, response serialization, the real Next.js BFF, and browser rendering.
Only route/answer generation at the external provider boundary was
deterministic. Outbound provider access was blocked; live-provider calls were
zero.

### Confirmed defects and focused corrections

| User-visible or integrity problem | Evidence | Smallest correction | Verification |
|---|---|---|---|
| A clarification reply could lose the original question, repeat the clarification, or misclassify clear comparison and Hindi/Bengali questions. | Focused request and browser regressions reproduced the state loss and loop. | Preserve explicit clarification context, resolve the combined question, and extend the reviewed multilingual intent markers. | Clarification-focused backend tests pass; the connected state/UT clarification continued to a cited WBSCC answer. |
| Hindi age answers could be rejected even when an English citation used the equivalent unit “years.” | Numerical-grounding regression failed for `साल`/`वर्ष` against `year(s)`. | Add reviewed Hindi/Bengali year aliases while retaining number, unit, and evidence matching. | All 22 affected numerical-grounding tests pass, including wrong-number and wrong-unit rejection. |
| A failed request could replace the prior successful question/answer; late responses, duplicate submit and IME composition could corrupt state. | Component and browser regressions exercised each transition. | Snapshot question/language at submit, preserve prior result on failure, abort superseded requests, block duplicate submit, and ignore composing Enter. | Frontend Vitest 39 passed/1 skipped; connected controlled failure returned sanitized 503 in 2.01 s and preserved the prior answer/input. |
| The deterministic PMSBY fixture demanded only an age passage although retrieval returned a useful official bank-account eligibility passage. | The first Hindi run retrieved the official passage, then the test fixture raised an assertion. | Accept either reviewed eligibility passage and emit only the claim supported by the selected passage. | Harness regression passes; corrected connected Hindi journey returns HTTP 200 with cited chunk `5b38ec36-0a1a-40e8-94b2-e6a8e07049ff`. |
| The Bengali browser assertion searched text outside the API’s deliberately truncated citation snippet. | The rendered answer and source were correct while the test timed out. | Assert the readable source title and exact citation URL. | Connected Bengali journey passes by inspected response and screenshots. |

An apparent mobile official-link overlap in stitched full-page screenshots was
investigated rather than treated as a product defect. A viewport-geometry
regression proves the official-links block ends above the composer; the focused
mobile quality gate passes. No CSS change was made for the screenshot artifact.

### Connected journey evidence

Evidence is under
`F:\setu\.tools\ux-complete-20260918\connected-final`,
`connected-remaining`, and `connected-hindi`.

| Path | Result | Evidence and links | Browser time |
|---|---|---|---:|
| English e-Shram application | HTTP 200, answered | Cited official e-Shram FAQ chunk `15a9cf41-9e5b-4918-9b25-33c4b5d3f9b4`; distinct registration and grievance links | 482.715 s |
| Hindi PMSBY eligibility | HTTP 200, answered in Hindi | Cited official Department of Financial Services bank-account eligibility chunk; no invented application link | 246.527 s |
| Bengali WBSCC over English evidence | HTTP 200, answered in Bengali | Cited WBSCC English evidence with readable source, application, and help destinations | 251.037 s |
| Ambiguous student credit card → West Bengal | HTTP 200 clarification, then HTTP 200 answer | Original question retained in `clarification_context`; cited WBSCC evidence with application/help links | 6.363 s + 597.492 s |
| Unsupported e-Shram ₹3,000 claim | HTTP 200, abstained in Hindi | No citations, claims, or links were invented | 371.618 s |
| Controlled provider failure/recovery | HTTP 503, sanitized | Previous answer/question preserved and exact failed input retained | 2.01 s |

Desktop and 393×851 mobile screenshots were inspected for the completed Hindi,
Bengali, clarification, abstention, and failure states. Text is readable, the
question is preserved exactly, citation/source controls are labelled, link kinds
remain distinct, and the document has no horizontal overflow.

### Performance and database integrity

Cold startup took 389.389 s. Warm connected retrieval remained far too slow for
ordinary use. Representative profiles were:

- e-Shram: embedding 200,119 ms, dense SQL 8,409 ms, keyword SQL 76 ms,
  reranking 264,938 ms, retrieval 473,921 ms, total request 481,947 ms;
- WBSCC clarification reply: embedding 129,260 ms, reranking 458,836 ms,
  retrieval 594,508 ms, total request 597,507 ms;
- Hindi PMSBY: embedding 96,280 ms, reranking 143,662 ms, retrieval
  241,660 ms, total request 245,131 ms.

The BFF timeout was not increased and no timeout result is presented as a speed
improvement. Model or batch changes need a separate optimization milestone with
the same retrieval-quality evidence.

Read-only before/after counts are unchanged: application 8 documents / 239
chunks / 3 eligibility rows / 0 query logs; staging 26 / 331 / 0 / 0. Both
databases have zero duplicate document URLs, duplicate chunk positions, or
noncontiguous chunk sets. Staging’s sole repeated title is PM-KISAN represented
by two distinct official records: its landing page and operational-guidelines
PDF. All eight application and two help URLs are unique within their link kind,
no URL is used across link kinds, and none replaces a source-document URL.
Connected evidence reports zero checked-out pool connections after completion.
No database data was modified.

### Final verification used for this delta

- Backend: 141 passed / 1 intentional opt-in skip from the current-source API
  image; affected numerical suite 22 passed; clarification focus 6 passed;
  deterministic runtime-harness regression passed.
- Corpus/host: 53 passed.
- Frontend: Vitest 39 passed / 1 skipped; TypeScript passed; ESLint passed;
  production build passed on the current frontend source snapshot. Later edits
  were test-only, so the build was not rerun.
- Browser: responsive four-size gate passed; focused mobile geometry gate
  passed; remaining connected paths 1 passed in 16.6 minutes; corrected Hindi
  path 1 passed in 4.3 minutes.

Functional acceptance is complete, but the quality gate remains **NO** because
246–597 second warm requests are not acceptable for ordinary users. The one
next action is a separate local-inference optimization milestone that preserves
the cited passages and reruns a bounded representative latency/quality gate.

Cleanup is complete. Audit-owned frontend PID 32192 was stopped only after its
saved executable and start time matched; audit-owned container
`setu-ux-complete-20260918` was stopped. Ports 3201 and 18001 have no
listeners. The pre-existing `setu-api` and `setu-db` containers remain
healthy, and both application health endpoints return HTTP 200.

## Recovery validation checkpoint — 2026-09-17

**VALIDATION INCOMPLETE — DO NOT MERGE.** This section supersedes the gate
status below for the recovered branch. The September 14 record is retained as
historical evidence, not as fresh validation of recovery HEAD.

Starting/current branch: `recovery/codex-2026-09-14`. Starting/current HEAD:
`908ad3db0ee1cd0040da0d27cb956e56e4888574`. Cached `origin/master` remains
`602f1ee4f74d5ab590ed3d10d15b9c334f165c8d`. Read-only `git ls-remote` could
not connect to GitHub; current remote refs and the historical push are unverified.
Initially no tracked differences or nonignored untracked files were reported;
`.pytest_cache/` could not be enumerated because access was denied. No branch,
commit, dependency, permanent environment file, or ignore-rule change was made.

Docker recovery follow-up completed later on 2026-09-17. Docker Desktop
4.91.0 (239619), Client/Server 29.8.0 and the `desktop-linux` context are
healthy. The existing `setu-api` and `setu-db` containers remained running and
healthy; neither was rebuilt, recreated or restarted by validation. `/health`,
`/health/db` and `/ready` each returned HTTP 200. Read-only counts match the
checkpoint exactly: application 8 documents / 239 chunks / 3 eligibility rows,
staging 26 documents / 331 chunks / 0 eligibility rows, with zero query-log rows
in both databases. Docker's configured WSL data location remains
`E:\DOCKER DATA\DockerDesktopWSL`.

### Evidence matrix

| Requirement | Implementation/evidence | Date and revision | Current status | Missing proof |
|---|---|---|---|---|
| Corpus extraction, manifest, safe fetching and staging isolation | Existing corpus module, existing `.venv-ingest` | September 17, recovery HEAD | 17 tests passed | Python 3.11 compatibility |
| Configuration, clarification rules, source queries and inference adapter contracts | Five host component modules | September 17, recovery HEAD | 34 tests passed before correction | Full API/graph runtime |
| Preserve caller-owned writes during retrieval | Ownership-scoped transaction replaces unconditional rollback; real SQLAlchemy session regression | September 17, working tree after recovery HEAD | Reproduced failure before fix; 11 retrieval tests pass after fix | PostgreSQL pool behavior and readiness under inference |
| Balanced everyday-use evidence | Existing 12-case audit reads saved passages and retrieval checkpoints | September 17, recovery HEAD | 12/12 passage and 12/12 saved-checkpoint checks pass; zero external activity | Fresh retrieval and generated-answer quality |
| Offline 60-case evaluator | Existing API image, Python 3.11.16 and real LangGraph 1.2.11 | September 17, current working tree | 60/60 passed; generated Markdown SHA-256 equals frozen report | Live retrieval/provider quality remains separate |
| Exact text, submission-time language, safe BFF, failure-state preservation | Existing TypeScript/Vitest and ordinary browser tests | September 17; frontend unchanged from recovery HEAD | Typecheck/lint/build pass; Vitest 35 passed/1 skipped; Playwright 12 passed/3 connected skips | Connected backend journey and clarification continuation |
| Full backend runtime | Existing API image, Python 3.11.16, real LangGraph 1.2.11; corpus module in `.venv-ingest` | September 17, current working tree | 137 passed/1 intentional staging skip (138 total) plus 17 corpus tests passed | Opt-in staging journey |
| Real staging journey and database safety | Healthy existing containers/endpoints and read-only database audit | September 17, current working tree | Counts and query logs confirmed; no discrepancies | Focused connected journey and duplicate audit |
| Inference latency | Saved embedding/reranker profiles | September 14, `F:\setu\.tools\latency-baseline` | Slow historical measurements retained; no performance change claimed | Comparable controlled runtime measurements |
| Publication and source integrity | Existing static checker, Python 3.11 compileall, dependency consistency and diff review | September 17, working tree | Passed | Hosted CI remains unverified |

### Correction and regression review

Recovery HEAD **does contain** the connection-release attempt:
`app/retrieval/pipeline.py` unconditionally called `session.rollback()` after
the two SQL reads. A new test with a real SQLAlchemy `AsyncSession` and a pending
ORM object failed because the object was removed from `session.new`. SQL reads
and inference were mocked; no database or model was invoked.

Retrieval now opens a transaction only when the caller has none, materializes
both search results as dictionaries, and ends its own transaction before
reranking. Existing caller transactions, including pending writes, remain under
caller control. Failure/cancellation ends a retrieval-owned transaction without
ending a caller-owned one. A diagnostic boolean distinguishes transaction
ownership in timing logs. The existing API session factory uses
`expire_on_commit=False`; no ORM objects are returned by either retrieval leg.

The final 11-test retrieval module includes pending-write preservation, explicit
caller transaction preservation, ending the owned transaction before reranking,
and 20 failure/cancellation subcases across embedding, SQL and reranking.
These are transaction-lifecycle/component tests, **not a real connection-pool or
readiness measurement**. Cancellation of `asyncio.to_thread` also does not prove
that an already running native inference call has stopped. No inference batch,
candidate count, model, timeout, response schema or provider behavior changed.

The final diff was reviewed for scope and error propagation. Frontend checks
remain applicable because no frontend source changed. Previously passing host
modules were not needlessly rerun after the retrieval-only correction.

### Environments, commands and results

Evidence directory: `F:\setu\.tools\recovery-validation-20260917`.
Logs and the new Playwright output are outside the repository; the earlier
`frontend/test-results` trace and failure context were preserved.
Docker-recovery evaluation artifacts are in
`F:\setu\.tools\backend-resume-20260917`.

Commands below use these exact existing executables, with the repository as
the working directory unless marked frontend:

```powershell
$Python = 'F:\setu\setu-project\setu\.venv-ingest\Scripts\python.exe'
$Node = 'F:\setu\.tools\node-v22.14.0\node-v22.14.0-win-x64\node.exe'
```

Python is 3.13.5, SQLAlchemy 2.0.35, asyncpg 0.30.0, BeautifulSoup 4.12.3,
lxml 5.3.0, Pydantic 2.9.2 and NumPy 2.5.3. This is host evidence, not the
documented Python 3.11 CI/API environment. Node is 22.14.0; system Node 16.16.0
was not used. Next is 16.3.3; Vitest is 4.1.11. `.venv-ci` remains incomplete
(only pip); no environment was created or repaired.

| Exact command (after executable variables above) | Exit/result | Log |
|---|---|---|
| `& $Python -B -m unittest discover -s tests -p test_corpus_pipeline.py -v` | 0; 17 passed | `corpus-tests.log` |
| `& $Python -B -m unittest tests.test_config tests.test_clarification tests.test_everyday_use_evaluation tests.test_retrieval_backends tests.test_sources_queries -v` | 0; 34 passed at starting HEAD | `host-components-baseline.log` |
| `& $Python -B -m unittest tests.test_retrieval_backends.BackendSelectionTests.test_retrieval_preserves_caller_pending_writes -v` | 1; demonstrated regression before correction | `transaction-regression-before.log` |
| `& $Python -B -m unittest tests.test_retrieval_backends -v` | 0; final 11 passed | `retrieval-final.log` |
| `& $Python -B -m eval.everyday_use_evaluation` | 0; 12/12 and 12/12 | `everyday-audit.log` |
| `& $Python -B -m eval.offline_evaluation` | 1; missing `langgraph`, before evaluation | `offline-evaluation-blocked.log` |
| `& $Python -B -m pip check` | 0; no broken requirements | `pip-check.log` |
| `& $Python -B scripts/ci_static_checks.py` | 0; publication checks pass | `static-checks.log` |
| Frontend: `& $Node node_modules/typescript/bin/tsc --noEmit --incremental false` | 0 | `typecheck.log` |
| Frontend: `& $Node node_modules/vitest/vitest.mjs run --pool=threads --maxWorkers=1` | 0; 35 passed, 1 skipped | `vitest.log` |
| Frontend: `& $Node node_modules/eslint/bin/eslint.js . --max-warnings=0` | 0 | `eslint.log` |
| Frontend: `& $Node node_modules/next/dist/bin/next build --webpack` | 0 | `build.log` |
| Frontend: `& $Node node_modules/@playwright/test/cli.js test --workers=1 --output=F:/setu/.tools/recovery-validation-20260917/playwright-results` | 0; 12 passed, 3 skipped, 35 seconds | `playwright.log` |
| `git --no-optional-locks diff --check` | 0; informational LF/CRLF notices | Terminal record |
| API image: 15 backend modules excluding the separately run corpus module | 0; 137 passed, 1 intentional staging skip (138 total) | Terminal record |
| API image: `python -m eval.offline_evaluation` | 0; 60/60; frozen Markdown exact match | `backend-resume-20260917/offline-current.*` |
| API image: `python -m compileall ...` and `python -m pip check` | 0; compile passed, no broken requirements | Terminal record |

Node's directory was prepended to the child process PATH. Build/server used
`SETU_DATA_MODE=demo`, `NEXT_TELEMETRY_DISABLED=1`; Playwright used
`SETU_CONNECTED_INTEGRATION=0`. No automatic install or browser download ran.
The production demo server command was
`& $Node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000`.
It ran hidden as task-owned PID 33572 and was stopped after checking its saved
executable and start time against `server-ownership.json`.

Browser evidence covers exact question whitespace preservation, primary route
rendering without console warnings/errors, empty source results, source details,
language menu, keyboard navigation, theme, demonstration eligibility and serious/
critical accessibility violations at desktop/tablet/mobile sizes. Vitest also
covers changing language during a pending request and preserving the prior
answer/input on failure. This does not establish live backend answers.

All 69 Python files under `app`, `ingestion`, `eval`, `tests` and `scripts` were
compiled in memory using `compile(path.read_bytes(), str(path), 'exec')` under
`$Python -B -`; exit 0, no bytecode written. A transient new-test harness error
(unretained SQLAlchemy async transaction proxy) was corrected before the final
run; intermediate logs remain available and are not counted as passing evidence.

### Backend module accounting and blockers

Docker recovery made the existing Python 3.11.16 API image available with real
LangGraph 1.2.11, FastAPI 0.115.0, SQLAlchemy 2.0.35 and OpenAI 2.54.0. Fifteen
API/graph test modules ran in a disposable, network-disabled, read-only container
against the current worktree: 137 passed and the opt-in real-staging module was
the one intentional skip. The first run exposed one stale `HealthySession` test
double without the new `AsyncSession` transaction methods. After updating only
that test double, `test_operations` passed 14/14 and the full 138-test run completed
with 137 passes and one intentional skip.
The separately intended corpus environment remains 17/17 passed.

The standalone evaluator then passed 60/60 with real LangGraph imports. Its
generated Markdown SHA-256
`126075A0EFE29E66BEDA195F810F606629F3E89D7060D3A907974DA6A7BF86A8`
exactly matches `docs/offline-evaluation-report.md`. Python `compileall` and
`pip check` also passed in the API image. No external network or provider call
was possible because every validation container used `--network none`.

This completes the previously blocked backend and offline validation. It does
not convert the intentional staging skip into a pass. Current database counts
and query logs are confirmed, but the duplicate audit and connected staging
journey remain unfinished.

CI currently installs `requirements-ci.txt` then discovers every test module;
the file does not directly declare corpus scraping dependencies. The smallest
proposed dependency correction, **not applied or installed**, is to append
`requests==2.32.3`, `beautifulsoup4==4.12.3`, `lxml==5.3.0` to that file and
validate the complete suite in its intended Python 3.11 environment. The valid
17-test corpus run resolves the host missing-bs4 result; it does not repair CI.

### Historical evidence and deferred acceptance

The saved September 14 browser failure at 11:18 predates the 14:16 recovery
commit. It waited 600 seconds for the English answer. Read-only ZIP inspection
finds a `/api/query` network record with status/time `-1`, not a saved successful
browser response. A separate frontend server log reports HTTP 200 in 5.9 minutes;
that log alone cannot prove this browser received/rendered the answer. Root cause
and execution SHA remain unverified; the trace was preserved.

Saved latency profiles show roughly 35–37 seconds embedding inference and
86–126 seconds reranker inference, versus roughly 1–2 seconds SQL and negligible
deterministic-provider/serialization time in those samples. These support an
inference bottleneck hypothesis without establishing present performance, cold/
warm behavior or improvement. No smaller batch was reintroduced; no expensive
inference benchmark was repeated. Earlier connected passes and 60/60 fixture
results remain historical context only.

This milestone completes host/frontend/backend/offline validation and one demonstrated
transaction correction. Full recovery acceptance is blocked. Clarification
continuation, expanded multilingual/unknown/legal answer behavior, measured
performance work and full real-runtime user acceptance are subsequent milestones.
Live-provider quality remains unauthorized and unverified.

Later +25→+50→+100 corpus milestones must target practical coverage gaps, with
provenance, jurisdiction, source date/version, useful-passage extraction checks,
reviewed links, deduplication, update handling and rollback. Collection and
promotion remain separate gates. No ingestion or promotion occurred here.

The saved cloud architecture remains IAM-private Cloud Run, private Cloud SQL,
runtime identity and individually scoped secrets in `setu-private-rm-2026`.
Current cloud health, deployed revision, data freshness and zero-cost/trial
capacity are unverified. A later deployment gate must check current costs,
code/schema differences, backup/promotion/rollback, private frontend authentication,
server-only secrets, readiness/latency, small separately authorized live-answer
evaluation and explicit acceptance/rollback conditions. No cloud action occurred.

**Exact first unfinished command:** the opt-in
`tests.test_real_runtime_staging_integration` gate with
`SETU_REAL_STAGING_INTEGRATION=1` in the existing API runtime. Do not run it as
part of backend/offline validation: it invokes the expensive real retriever and
requires separate authorization for the connected path. The recommended next
milestone is one focused deterministic-provider staging journey plus the duplicate
audit, without repeating the completed backend, offline or frontend suites.

Files changed: `app/retrieval/pipeline.py`, `tests/test_retrieval_backends.py`,
`tests/test_operations.py`, this checkpoint, and `corpus/progress.json`. Existing ignored environments,
staging/model files and traces remain; new evidence is in the directory above.
No commit, push, merge, deployment, external model call or paid resource was used.

---

Updated: 2026-09-14 (Asia/Calcutta)

Branch: `master`  
HEAD: `602f1ee4f74d5ab590ed3d10d15b9c334f165c8d`

## Gate status

The everyday-use runtime integration gate is **complete**. One connected
Playwright journey passed through the frontend, BFF, real FastAPI, installed
LangGraph 1.2.11, real PostgreSQL staging retrieval/reranking, grounding, and
browser rendering. Only the two outbound provider stages were replaced by a
guarded deterministic double; no live provider call was made. Live answer
quality remains unverified and is a separate authorization gate.

## Runtime integration completion evidence

- **User problem:** a person must be able to ask a practical scheme question,
  clarify ambiguity, receive a supported answer in the selected language, and
  open the correct official destination without the request disappearing at a
  frontend/backend boundary.
- **Acceptance criteria:** exact question text survives the browser and backend
  boundaries; English and Bengali real-retrieval answers render cited evidence
  and reviewed links; a missing state produces one clarification without a
  provider call; a controlled provider failure preserves the question and the
  previous answer; application and staging data remain unchanged.
- **Implementation:** retained the existing API, graph, retrieval, grounding,
  and response components. Added a fail-closed staging harness and loopback-only
  connected server; corrected equivalent loopback-origin handling; used a
  bounded local Node HTTP transport for long local queries; and corrected only
  demonstrated Playwright hydration/selector defects.
- **Verification:** the connected desktop test passed in 13.0 minutes. The
  e-Shram request returned HTTP 200 through Next after 6.4 minutes, the
  controlled provider failure was sanitized, the missing-state clarification
  returned in about 1.1 seconds, and the Bengali WBSCC request returned HTTP 200
  after 5.8 minutes. Source, application, and help links were rendered from
  cited staging metadata.
- **Outcome:** the connected behavior is complete under deterministic provider
  boundaries. Local retrieval latency is not acceptable for ordinary use and
  remains a performance issue; the 600-second local-only timeout is an
  integration accommodation, not a performance fix.

The provider-guard mismatch was caused by the original browser diagnostic
interacting before React hydration, allowing the controlled textarea to revert
to its server fixture. A cheap browser test now records only lengths, equality,
and SHA-256 fingerprints and proves equality at fixture, hydrated composer, and
request body. A backend diagnostic independently proves equality at FastAPI
validation, the graph routing prompt's extracted question, and the provider
answer parser. No normalization or relaxed provider guard was added.

## Task 1 — finish and preserve the +25 corpus checkpoint

- **User problem:** people need official passages that answer practical scheme
  questions, not merely a catalogue entry.
- **Acceptance criteria:** 25 distinct additional items are retrieval-checked
  at passage level in an isolated staging database; failed candidates are not
  counted; application data is unchanged.
- **Implementation:** reused the existing collect/extract/chunk/embed/index
  pipeline, added prerequisite-gate support for later manifests, required useful
  passage markers, and kept four unusable candidates excluded.
- **Verification:** batches 1–3 contain 10 + 10 + 5 completed items, 26 source
  documents, and 331 chunks. The current 18-test ingestion/evaluation unittest run
  passes. Read-only database audit confirms application 8/239/3 and staging
  26/331/0.
- **Outcome:** complete in staging. No promotion, deployment, commit, push, paid
  call, or batch 4 work occurred.

## Task 2 — everyday-use evaluation set

- **User problem:** a code or document count does not show whether people can
  resolve real tasks.
- **Acceptance criteria:** 12 pre-declared cases, balanced 4 English / 4 Hindi /
  4 Bengali, cover application, eligibility, missing state, similar schemes,
  unsupported amount, and inconclusive legal questions; evidence checks inspect
  passages.
- **Implementation:** added `eval/everyday_use_cases.jsonl` and an offline audit
  that resolves each expected source passage and its saved staging retrieval
  checkpoint.
- **Verification:** 12/12 passage checks and 12/12 saved retrieval checkpoints
  pass; provider, database, and external request counts are all zero for that
  audit.
- **Outcome:** evaluation definition and evidence audit complete. This is not a
  live LLM answer-quality score.

## Task 3 — answer, clarification, and official-link flow

- **User problem:** a person needs a short, supported answer, the next useful
  action, and the correct official destination without exposing sensitive data.
- **Acceptance criteria:** clear questions proceed; ambiguous questions receive
  one focused clarification; only cited evidence can produce typed sections;
  application/status/help URLs come from reviewed metadata and stay distinct
  from source URLs.
- **Implementation order:**
  1. `ingestion.corpus_manifest._validate_web_url` accepts only absolute HTTP(S)
     official/service links.
  2. `ingestion.corpus_pipeline.index_batch` stores verified link metadata and
     `sync_verified_links` enriches already-indexed staging documents without
     adding documents or chunks.
  3. dense and keyword retrieval return `document_metadata` with each chunk.
  4. `app.clarification.focused_clarification` handles only the reviewed missing
     state, similar insurance, and generic pension distinctions.
  5. `app.agent.graph.generate_node` keeps numerical/language validation, gates
     uniformly low-scored retrieval, omits uncited claims, preserves source
     scope, and derives no URLs from model output.
  6. `app.grounding.select_official_links` accepts links only from a cited corpus
     document and de-duplicates by link kind and URL.
  7. backend and frontend schemas carry optional typed sections and separate
     `official_links`.
- **Verification:** the production API image passes 134 tests with its installed
  LangGraph and one intentional default skip for the separately invoked staging
  gate. The five-case real-runtime staging suite passed with deterministic
  provider boundaries. The connected browser run exercises a Bengali answer
  over English evidence and returns only its cited chunk plus WBSCC
  application/help links.
  The real exact e-Shram staging probe retrieved chunk
  `15a9cf41-9e5b-4918-9b25-33c4b5d3f9b4` at rank 1 with score 0.8915 and the
  required-document passage. Its database metadata supplied
  `https://register.eshram.gov.in/` and `https://gms.eshram.gov.in/`; the model
  was not called.
- **Outcome:** component behavior passes. Real LangGraph integration and a
  connected API request remain unverified on this host.

## Task 4 — language and frontend behavior

- **User problem:** users need to keep their question unchanged while choosing
  the answer language without persistent homepage/composer clutter.
- **Acceptance criteria:** English defaults; English, हिन्दी, and বাংলা exist
  only inside the three-dot menu; explicit preference persists locally; typed
  text is unchanged; source and service links are readable and distinct; no
  upload control appears.
- **Implementation:** reused the existing local preference and request contract,
  removed visible language labels, added relevant section headings, and rendered
  source/application/help actions directly beneath answers.
- **Verification:** TypeScript passes; 35 frontend tests pass with 1 intentionally
  skipped; ESLint passes; Next.js 16.3.3 production build passes; 12 Playwright
  tests pass serially on desktop/tablet/mobile with 3 connected cases skipped by
  default. The connected desktop gate separately passes with all browser traffic
  restricted to loopback.
- **Outcome:** frontend gate complete using the existing local Node 22.14.0
  runtime. System Node 16.16.0 is incompatible and was not upgraded.

## User-behavior evidence matrix

“Saved retrieval” means a real staging retrieval checkpoint already recorded in
the manifest. “Mocked node” means provider output was supplied by a test; it is
not live answer-quality evidence.

| Exact question / selected language | Expected behavior | Evidence and citation result | Sections / links | Verification mode |
|---|---|---|---|---|
| How do I register for e-Shram and what do I need? / en | Answer from supported registration-document evidence | e-Shram FAQ useful passage retrieved and cited by real staging retrieval | Direct supported answer and Documents section; source + application + help present | Connected browser + real FastAPI/LangGraph/retrieval; deterministic provider only |
| Who can join PMSBY? / en | General conditions, not a personal decision | PMSBY official FAQ; marker “18 to 70 years”; saved check `pmsby.en.eligibility` | Expected direct answer, conditions, next steps, limitation; source only | Saved real staging retrieval + contract expectation |
| Where do I apply for the student credit card scheme? / en | Ask which state/UT | No retrieval by design | One focused English clarification; no links | Deterministic current test |
| Can a senior citizen automatically evict an adult child under the Maintenance and Welfare of Parents and Senior Citizens Act? / en | No case-specific legal conclusion | Ministry overview; saved check `senior-act.en.property` | Expected limitation + source; answer not generated | Saved real staging retrieval + contract expectation |
| प्रधानमंत्री उज्ज्वला योजना के लिए आवेदन कैसे करूँ और कौन से दस्तावेज़ चाहिए? / hi | Hindi application/documents answer, no invented deadline | PMUY official page; “Documents Required” / “Know Your Customer”; saved check `pmuy.en.eligibility` | Expected direct answer, how to apply, documents, limitation; source only; answer not generated | Saved real staging retrieval + contract expectation |
| मुझे प्रधानमंत्री वाली बीमा योजना चाहिए—PMJJBY या PMSBY? / hi | Ask life insurance or accident insurance | No retrieval by design | One focused Hindi clarification; no links | Deterministic current test |
| ई-श्रम कार्ड बनते ही ₹3,000 मिलते हैं ना? / hi | Do not confirm unsupported amount | e-Shram cash-benefit FAQ checkpoint `batch-002.eshram.unsupported-cash-amount.hi` | Expected correction + limitation + source; answer not generated | Saved real staging retrieval + contract expectation |
| पीएम विश्वकर्मा योजना के लिए कौन से कारीगर पात्र हैं? / hi | Supported trade conditions only | PM Vishwakarma official overview; saved check `pm-vishwakarma.bn.eligibility` | Expected direct answer, conditions, limitation; source + application; answer not generated | Saved real staging retrieval + contract expectation |
| পশ্চিমবঙ্গ স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব? / bn | Bengali application answer | English WBSCC evidence passage retrieved and cited by real staging retrieval | Produced Bengali answer and How to apply section; source + application + help | Connected browser + real FastAPI/LangGraph/retrieval; deterministic provider only |
| তপশিলি বন্ধু পেনশনের জন্য কারা যোগ্য? / bn | State/age conditions, no personal verdict | West Bengal overview; saved check `wb.taposili-bandhu.bn.eligibility` | Expected direct answer, conditions, next steps, limitation; source only; answer not generated | Saved real staging retrieval + contract expectation |
| বয়স্ক পেনশনের জন্য কোথায় আবেদন করব? / bn | Ask state/UT and scheme | No retrieval by design | One focused Bengali clarification; no links | Deterministic current test |
| রেশন না পেলে NFSA অনুযায়ী আমি কি সরাসরি আদালতে মামলা করতে পারি? / bn | State grievance evidence; no court-strategy conclusion | NFSA official PDF; grievance markers; saved check `nfsa.en.grievance` | Expected grievance route, limitation, source; answer not generated | Saved real staging retrieval + contract expectation |
| What is Andhan Nirudhana? / en | Coverage-limited abstention, not an existence claim | Uniformly low-scored unrelated retrieval fixture is rejected at 0.20 gate | No factual sections or links | Deterministic/mocked backend test |

## Database safety and idempotence

- Application: 8 documents / 239 chunks / 3 eligibility rows; zero corpus-tagged
  documents; 0 query-log rows.
- Staging: 26 documents / 331 chunks / 0 eligibility rows; 26 corpus-tagged
  documents, 10 verified service-link values, zero invalid links, and 0
  query-log rows.
- Duplicate document URLs: 0. Duplicate `(document_id, chunk_index)` positions:
  0.
- A second three-manifest link synchronization returned the same counts and the
  same 14,343,191-byte staging database size. It created no document or chunk.

## Test record

- Python compile of changed backend/ingestion/evaluation files: pass.
- Ingestion/evaluation unittest in `.venv-ingest`: 18 passed; `pip check` reports
  no broken requirements.
- Offline everyday-use audit: 12/12 passages and 12/12 saved retrieval checks.
- Backend in the production API image with installed LangGraph 1.2.11: 134
  passed / 1 intentional default skip. `test_corpus_pipeline` is the only module
  run separately because its scraping dependencies are intentionally absent from
  the API image.
- Opt-in real-runtime staging suite: 5 passed, including English, Hindi, Bengali,
  missing-state clarification, and unsupported-amount abstention behavior.
- Frontend: TypeScript pass; Vitest 35 passed / 1 skipped; ESLint pass; production
  build pass; ordinary Playwright 12 passed / 3 connected skips; connected
  desktop Playwright 1 passed in 13.0 minutes.
- `git diff --check`: pass apart from informational LF→CRLF notices.

## Fixed defects

1. Restored the displaced return in `deterministic_route_guard` found during
   interrupted-edit review.
2. Rejected `javascript:` and other non-web service links at manifest load.
3. Removed provider claims without a valid cited chunk instead of displaying
   them unbadged.
4. Added a low-score retrieval gate so unknown names do not automatically reach
   answer generation with uniformly unrelated evidence.
5. Added document metadata to both retrieval legs and restricted application/
   help links to cited corpus documents.
6. Removed persistent visible language labels and repaired the related unit/E2E
   expectations.
7. Proved the earlier provider-guard rejection was a pre-hydration browser-test
   race; the product preserves the exact question at every inspected boundary.
8. Accepted only equivalent loopback aliases for same-protocol, same-port BFF
   origin checks while retaining cross-site, port, and protocol rejection.
9. Replaced the local query's default fetch transport with a bounded built-in
   loopback HTTP client after logs proved fetch returned 503 before FastAPI's
   eventual 200; demo, cloud, source, and injected-test transports are unchanged.
10. Scoped connected assertions to the product's Documents heading and inline
    error alert instead of matching nonexistent copy or Next's route announcer.

## Remaining warnings and next separately authorized operation

- The local Transformers tokenizer continues to warn that
  `fix_mistral_regex=True` may be needed for the two XLM-R-compatible tokenizer
  artifacts. No compatibility change was made without model-specific evidence.
- OpenVINO could not create its telemetry client-ID directory and stated that no
  data would be sent.
- The reranker also reports a fast-tokenizer/padding efficiency warning.
- Real retrieval/reranking is extremely slow on this host: the passing connected
  run took 6.4 minutes for e-Shram and 5.8 minutes for WBSCC after model preload.
- Four parallel Edge workers caused unrelated 30-second UI/navigation timeouts;
  the unchanged 12-test browser matrix passed with one worker.

The next operation is a separate, explicitly authorized live-provider
answer-quality milestone. It must remain small and budget-bounded. No live
provider call, staging promotion, deployment, commit, push, or batch 4 corpus
work was performed in this gate.
