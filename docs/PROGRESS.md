# SETU progress

The single source of truth for what is done, in progress and blocked. Every
PR updates this file. A new session reads it first and resumes from the first
item that is not done. The plan and its reasoning are in
[FINDINGS.md](FINDINGS.md); the full autonomous brief is kept in the owner's
SETU project as `SETU_AUTOPILOT_PROMPT.md`.

Last updated: 9 Oct 2026 (security update merged as #13; e-Shram re-pin in review).

## Work items

Design notes and results for each phase are in `docs/research/`.

| Item | Status | PR | Result |
|---|---|---|---|
| Phase 0: verify research, findings report | Done | [#1](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/1) | 19 claims graded: 11 verified, 8 partly, 0 wrong |
| Phase 1: jurisdiction- and date-aware retrieval | Done | [#2](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/2) | 6 of 15 temporal cases pass; unfiltered SQL byte-identical |
| A. Phase 1 leftovers: source hash, retrieval time, PIB backfill | Done | [#3](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/3) | Ingestion stores SHA-256 and UTC fetch time; backfill tags PIB as `IN` |
| B. Phase 2: Roadside Mode (offline) | Done | [#4](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/4) | `/roadside` works offline; 12 of 21 rows show a verified amount; 0 accessibility violations (`roadside-mode.md`) |
| C. Phase 3: False-premise guard | Done | [#5](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/5) | 15 of 15 temporal cases; 0 false premises accepted; 0 over-asks; held-out 10 of 12 before fix (`premise-guard.md`) |
| D1. Phase 4a: Scam Shield | Done | [#6](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/6) | 0 missed scams, 0 false alarms on genuine official messages (44 cases); held-out 10 of 12 before fix; never says "safe" (`scam-shield.md`) |
| D2. Phase 4b: document version history | Done | [#7](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/7) | Migration 0002 archives superseded versions; retrieval unchanged; CI runs migrations on real PostgreSQL (`version-history.md`) |
| D3. Phase 4c: freshness watch | Done | [#8](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/8) | Weekly check of 6 pinned sources; fails on a changed hash or when nothing is reachable (`data/traffic_offences/README.md`) |
| E1. Phase 5 (P6): official next steps | Done | [#9](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/9) | Reviewed table of 6 official services; eligibility answers link the official portal (`next-steps.md`) |
| E2. Phase 5 (P5): eligibility | Decided: hand off to myScheme | [#9](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/9) | Owner chose option A on 29 Sep 2026: eligibility stays switched off; answers link myScheme and the scheme's official portal. No rules-as-code |
| F. Research write-up: Indian traffic-law temporal benchmark | Planned | | After C |
| G. Laptop work recovered from `F:\setu` | Done | [#11](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/11) | 4 fixes carried over with tests (local query timeout, DB connection during rerank, Hindi/Bengali "year", answer language tag and demo label); larger parts planned as M2 below (`recovery-review.md`) |
| H. Security: patched Next.js and dependencies | Done | [#13](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/13) | `next` and `eslint-config-next` 16.3.3 to 16.3.8, the lowest version outside the advisory range (16.4.0 not needed); `sharp` and `source-map-js` patched by `npm audit fix`. Production audit: 0 advisories. 5 dev-only `braces` advisories remain (lint tooling; the only offered fix downgrades `eslint-config-next` to 14) |
| J. e-Shram FAQ re-pin (owner decision, 9 Oct 2026) | In review | [#15](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/15) | Pin moved from the 13 Sep snapshot to the page fetched 9 Oct 2026; the pin ignores the footer "Last Update" date, which moves daily. Local watch: 25 unchanged, 1 changed (PFRDA APY page, see "Waiting for the owner"), 6 unreachable from the laptop (TLS) |

All of #4-#9 were merged on 29 Sep 2026 (master `3ee3d4d`). The first
freshness run on GitHub (started by the #8 merge) passed: no pinned source
had changed.

## Next milestone: M2, real scheme answers

Goal: SETU answers everyday scheme questions from a staged corpus of
official sources, in English, Hindi and Bengali, and asks one question
instead of guessing. Built from the recovered work (`recovery-review.md`),
rebuilt on today's `master`, one PR per item.

| Item | What | Done when |
|---|---|---|
| M2.1 (in review, this PR) | Scheme corpus pipeline: safe fetching, manifests, staging database; 29 schemes and laws (7 West Bengal schemes; 8 central-scheme pages from the West Bengal government), 26 active official sources | Pipeline writes jurisdiction, dates and source hashes (migration 0001), keeps versions (0002); manifest URLs join the freshness watch; tests pass without network |
| M2.2 | Everyday-use evaluation: 12 questions (en, hi, bn) with expected status, sections and evidence | Runs offline in CI from saved retrieval results; baseline recorded before any tuning |
| M2.3 | Scheme clarification (student credit card state, PMJJBY or PMSBY, old-age pension) with follow-up context | Shares `needs_clarification` with the traffic guard; asks at most one question; over-asking measured |
| M2.4 | Local speed: 8-bit models or more Docker memory | Median local answer time measured before and after, on the same questions |
| F | Research write-up: Indian traffic-law temporal benchmark | After M2.2, so it can report both evaluation sets |
| Extractor keeps answer paragraphs on FAQ pages (needs re-pinning every HTML source) | Planned. The extractor stores FAQ questions and lists but drops answer paragraphs; on e-Shram that hides the age range (16 to 59) and the removed income-tax clause | Answer paragraphs are stored; `EXTRACTION_VERSION` raised; every HTML pin recomputed and reviewed in the same PR |

M2.1 result: 29 items (4 excluded, with reasons) and 26 active sources in
three reviewed manifests; see [corpus/README.md](../corpus/README.md).
Manifests hold no run state or local paths. The pipeline writes
jurisdiction, effective dates, source hash and retrieval time; re-indexing
keeps the old version (tested on PostgreSQL in CI). HTML pages are pinned on
their extracted text, because 7 of them differed byte for byte between two
requests seconds apart. The freshness watch now covers 32 sources. First
live run on 29 Sep 2026: 27 unchanged, 1 changed (e-Shram FAQ, restructured
since 13 Sep), 4 unreachable from the laptop (TLS; 2 are traffic PDFs the
GitHub runner reached in #8). Retrieval checks were not re-run: they need
the local models and a staged database.

Handoff (8 Oct 2026, item H): merge the security PR before any public deploy;
`roadside-bundle.json` is now pinned to LF in `.gitattributes`, which fixes the
Windows-only bundle test. Next is M2.2 (everyday-use evaluation). Staging a batch is a local
run (`corpus/README.md`); the e-Shram re-review below should come first.

Handoff (9 Oct 2026, item J): owner decisions of 9 Oct are in `FINDINGS.md`
(Ponytail lite rule, e-Shram re-pin). The e-Shram pin is current; `collect`
will fetch it again and `index` stores it as a new version. Next is M2.2.

## Waiting for the owner

These need a person. Work continues on everything else.

1. **Delete one last merged branch:** `phase1/source-provenance` (PR #3,
   in `master`). The other merged branches were deleted on 29 Sep 2026.
   Keep `recovery/codex-2026-09-14` and
   `recovery/laptop-uncommitted-2026-09-29`.
2. **Apply migration 0001, then backfill 0001, to any deployed database**
   before a client sends `jurisdiction` or `as_of`. Until then a filtered
   request fails (503) while unfiltered requests work.
   Migration 0002 (version history) can follow at any time; it needs 0001.
3. **Legal review:** how red-light jumping is booked (signal violation vs
   dangerous driving), and whether Karnataka may compound below the central
   fine (helmet Rs 500 vs Rs 1,000).
4. **Delhi:** the current Section 200 compounding notification, so its rows
   can leave UNVERIFIED.
5. **Name:** "Nyaya Setu" is already used twice; choose a distinct public name
   before launch.
6. **Re-read the PFRDA Atal Pension Yojana page**
   (`https://pfrda.org.in/web/pfrda/schemes/atal-pension-yojana-apy`). On
   9 Oct 2026 the watch reported it as changed: the address now shows text
   about "NPS Sanchay", not APY. `collect` holds it back. Choose a new
   official APY source or exclude it with a reason
   (`corpus/manifests/batch-001.json`). (The e-Shram re-read that was here
   was decided on 9 Oct 2026: re-pinned.)
7. **Workspace layout.** The recovered work has a conversation-style
   redesign; `master` has added cards to the current layout since. Choose
   one before M2 extends the answer screen (see `recovery-review.md`).

## Rules every item follows

Zero spend; no invented values; no confrontational copy; tests and evaluation
first; unfiltered retrieval and the frozen 60-case evaluation unchanged; one
PR per item with green CI before merge.
