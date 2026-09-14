# SETU everyday-use journey checkpoint

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
