# SETU — Clientell demo evidence manifest

## Package boundary

This manifest supports a manually edited two-minute interview recording. It
does not claim that a video has been recorded or published. Connected-result
frames are **recorded application evidence**, not live queries. Their retrieval,
reranking, PostgreSQL reads, grounding, response serialization, BFF, and browser
rendering were real; route and answer generation at the external-provider
boundary were deterministic. The performance and latency quality gate remains
open.

## Frame manifest

| ID | Repository filename or recording source | What appears on screen | Exact supported claim | Evidence source and class | Limitation or caveat | Crop or redact? |
|---|---|---|---|---|---|---|
| EV-01 | `docs/demo/assets/setu-title-frame.png` | SETU landing frame and product heading | SETU presents a workspace for asking questions about public information represented in its sources. | Exact copy of the saved browser-gate screenshot; **recorded application evidence** | Deterministic demo UI, not a new connected request | Safe as copied. Crop only for composition. |
| EV-02 | `docs/demo/assets/setu-architecture.svg` | Question → FastAPI → LangGraph → hybrid PostgreSQL/pgvector retrieval → RRF/reranking → LLM structured generation → grounding validation → cited response | This is the implemented request architecture at a recording-friendly level of abstraction. | `app/main.py`, `app/agent/graph.py`, `app/retrieval/pipeline.py`, retrieval modules, grounding modules; **live repository evidence** | Simplifies error handling, clarification, eligibility quarantine, and correction loops. It is not a deployment topology. | Safe. Do not add cloud claims to this frame. |
| EV-03 | `docs/demo/assets/e-shram-recorded-result.png` | Exact English e-Shram question, grounded answer, citation marker, and official-link labels | A previously verified connected local journey returned an English answer citing official e-Shram evidence. | Exact copy of `F:\setu\.tools\ux-complete-20260918\connected-final\after-english-application-desktop.png`; **recorded application evidence** | Took 482.715 seconds. Do not present it as live or fast. The help link is partially below the visible fold. | Safe. Keep “Recorded connected evidence” overlay visible. |
| EV-04 | `docs/demo/assets/e-shram-evidence-card.svg` | Answer fact, exact official FAQ passage, citation chunk ID, and separate source/application/help destinations | The answer’s Aadhaar requirements map to chunk `15a9cf41-9e5b-4918-9b25-33c4b5d3f9b4`; source, application, and help URLs are distinct fields in the saved response. | `connected-final/connected.json`; **recorded application evidence** | URL freshness was not checked during package preparation. Verify all three immediately before recording. | Safe sanitized substitute for raw JSON. |
| EV-05 | `docs/demo/assets/pmsby-hindi-recorded-result.png` | Exact Hindi PMSBY question and answer with citation and official source | A previously verified connected local journey produced a Hindi answer from cited official evidence. | Exact copy of `F:\setu\.tools\ux-complete-20260918\connected-hindi\after-hindi-eligibility-recovery-desktop.png`; **recorded application evidence** | Took 246.527 seconds. The saved response contains no application or help destination. | Safe. Keep “Recorded connected evidence” overlay visible. |
| EV-06 | `docs/demo/assets/pmsby-evidence-card.svg` | Hindi answer beside the English Department of Financial Services passage and citation ID | The Hindi eligibility statement maps to official English chunk `5b38ec36-0a1a-40e8-94b2-e6a8e07049ff`. | `connected-hindi/connected.json`; **recorded application evidence** | Shows language transfer for one recorded case, not general translation accuracy. Verify the public source URL before recording. | Safe sanitized substitute for raw JSON. |
| EV-07 | `docs/demo/assets/groq-structured-output-fix.svg` | Before/after: `instructor.Mode.TOOLS` and `tool_use_failed` → native parsed schema; regression protections | A historical Groq structured-output failure was traced to the forced tool pathway; commit `9384628` removed that Groq wrapper, used the native schema path, and added regressions. | Parent and diff of `938462867ce213d430ff26832ca6fd2cdf3f3db4`, current `app/agent/llm.py`, and `tests/test_llm_structured_output.py`; **historical Git evidence** | Fixes this request-format path. It does not prove universal provider reliability; exact successful-attempt telemetry is unavailable. | Safe sanitized substitute. **DO NOT RECORD** the full raw Git diff. |
| EV-08 | `docs/demo/assets/deterministic-evaluation-card.svg` | 60/60 result, 20 cases per supported language, checked dimensions, and interpretation boundary | Offline evaluation version `4C-2.1` passed all 60 deterministic fixture-replay cases. | `docs/offline-evaluation-report.md`; **deterministic evaluation evidence** | Not live retrieval accuracy, provider quality, semantic entailment, calibrated confidence, or a statistically robust study. | Safe. Keep the interpretation boundary visible. |
| EV-09 | `README.md` plus the `docs/demo/` file tree | Repository title, implementation documentation, and prepared demo files | The demo artifacts and supporting implementation are present in the current repository. | Current working tree; **live repository evidence** | Existing changes are uncommitted. Do not imply the demo package is published, merged, or production-ready. CI figures in README are a frozen historical baseline. | Record a clean editor/Markdown view only. Hide terminal history, user profile, full local path, and unrelated files. |

Every planned shot has a traceable evidence source. EV-04, EV-06, EV-07, and
EV-08 are deliberately sanitized recording cards so the editor does not need to
show raw JSON, a terminal, or unrelated code.

## Recording privacy and safety audit

**Result: PASS with manual pre-record checks.** The repository assets contain no
API keys, passwords, bearer/OAuth tokens, Secret Manager values, private Cloud
Run URL, database connection string, private Cloud SQL identifier, or personal
browser content. The public government URLs are intentional evidence fields.

| Source or screen | Decision | Reason and safe substitute |
|---|---|---|
| `docs/demo/assets/*` | RECORD | Purpose-built, visually inspected, and sanitized. |
| Raw connected JSON under `F:\setu\.tools\ux-complete-20260918` | **DO NOT RECORD** | It adds internal request IDs and local-path clutter. Use EV-04 and EV-06. |
| Full `git show 9384628` or its parent | **DO NOT RECORD** | It includes unrelated code and commit metadata. Use EV-07. |
| `.env`, shell history, process environment, cloud console, secret manager, database client | **DO NOT RECORD** | These can expose credentials or private infrastructure. No substitute is needed. |
| Saved system/cloud screenshot | **DO NOT RECORD for current-state claims** | It is explicitly historical and cloud state was not revalidated. Use EV-02 for architecture and qualify any historical deployment discussion verbally. |
| Live browser tabs or bookmarks bar | **DO NOT RECORD** | They may contain personal or private information. Use full-screen local assets. |
| `README.md` closing frame | RECORD AFTER CLEANUP | Use a distraction-free Markdown preview and hide local path, editor account, notifications, and unrelated file names. |

## Claim audit

| Demo claim | Evidence | Safe to say? | Qualification |
|---|---|---:|---|
| SETU supports recorded English, Hindi, and Bengali behavior. | Connected records in the current checkpoint; deterministic evaluation language rows | Yes | Say “recorded journeys” and “supported languages,” not universal multilingual accuracy. |
| Retrieval is hybrid. | `app/retrieval/pipeline.py` | Yes | It combines dense and keyword result lists before reranking. |
| Dense retrieval uses PostgreSQL/pgvector. | `app/retrieval/dense.py`, schema and README | Yes | Describe implementation, not current hosted availability. |
| Keyword retrieval uses PostgreSQL full-text search. | `app/retrieval/keyword.py` | Yes | Same implementation boundary. |
| Reciprocal-rank fusion combines retrieval lists. | `app/retrieval/fusion.py`, `app/retrieval/pipeline.py` | Yes | Use “RRF” only after saying “reciprocal-rank fusion” once if the audience is nontechnical. |
| A BGE cross-encoder reranks fused candidates. | `app/retrieval/rerank.py` | Yes | Do not imply reranking is fast; local latency remains unacceptable. |
| LangGraph orchestrates routing, retrieval, generation, and terminal response state. | `app/agent/graph.py` and connected runtime evidence | Yes | Clarification and eligibility guards are simplified out of the diagram. |
| Groq uses native strict structured output in the current implementation. | `app/agent/llm.py`, request-shape regression tests | Yes | Current code claim, not a fresh provider call. |
| Citation IDs are checked against retrieved chunks. | `app/agent/graph.py`, `app/grounding.py`, grounding tests | Yes | Membership validation does not prove semantic entailment. |
| Numerical grounding rejects unsupported number/unit claims. | `app/numerical_grounding.py`, numerical tests | Yes | Coverage is a bounded reviewed implementation, not general numerical reasoning. |
| SETU abstains when useful evidence is insufficient. | `app/agent/graph.py`, grounding tests, recorded unsupported-claim journey | Yes | Describe fail-closed behavior within tested cases. |
| Offline evaluation passed 60/60 multilingual fixtures. | `docs/offline-evaluation-report.md` | Yes | Always say deterministic fixture replay; do not call it live accuracy. |
| The repository has automated backend, frontend, browser, and publication checks. | `.github/workflows/ci.yml` | Yes | Say the workflow is defined. README counts are historical unless rerun. |
| SETU is currently available on Cloud Run and Cloud SQL. | Historical README/architecture records only | No | Omit present-tense availability. Historical private-backend evidence may be discussed only as historical and was not revalidated here. |
| The system is production-ready. | Current checkpoint explicitly keeps the quality gate open | No | State that connected functionality passed but local inference latency remains several minutes. |
| Confidence is calibrated or citations prove entailment. | Repository limitations explicitly deny both | No | Omit. Model confidence is uncalibrated; citation checks prove membership and de-duplication. |
| SETU covers all schemes or traffic law. | No supporting corpus evidence | No | Omit. |

## Official-link checklist

These public URLs come from saved connected response evidence. Network freshness
was not checked while preparing this package. Rajdeep must open each in a clean
browser immediately before recording and omit any destination that fails,
redirects unexpectedly, or no longer represents the recorded purpose.

| Role | Scheme | Public URL | Manual check immediately before recording |
|---|---|---|---|
| Official information source | e-Shram | `https://eshram.gov.in/faqs` | Confirm the official FAQ loads and still contains the Aadhaar-number and Aadhaar-linked-mobile requirement. |
| Official application destination | e-Shram | `https://register.eshram.gov.in/` | Confirm it remains the official worker-registration destination. |
| Official help/contact destination | e-Shram | `https://gms.eshram.gov.in/` | Confirm it remains the official grievance/help destination. |
| Official information source | PMSBY | `https://financialservices.gov.in/pmsby` | Confirm the Department of Financial Services page loads and still contains the cited bank-account eligibility passage. |

The recorded PMSBY response contains no application or help link. Do not add
one from memory or a third-party site.

## Package provenance

- Branch at preparation: `recovery/codex-2026-09-14`
- HEAD at preparation: `908ad3db0ee1cd0040da0d27cb956e56e4888574`
- Groq correction commit: `938462867ce213d430ff26832ca6fd2cdf3f3db4`
- Connected English evidence: saved under
  `F:\setu\.tools\ux-complete-20260918\connected-final`
- Connected Hindi evidence: saved under
  `F:\setu\.tools\ux-complete-20260918\connected-hindi`
- Evaluation source: `docs/offline-evaluation-report.md`, version `4C-2.1`

