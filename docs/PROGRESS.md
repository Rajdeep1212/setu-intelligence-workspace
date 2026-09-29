# SETU progress

The single source of truth for what is done, in progress and blocked. Every
PR updates this file. A new session reads it first and resumes from the first
item that is not done. The plan and its reasoning are in
[FINDINGS.md](FINDINGS.md); the full autonomous brief is kept in the owner's
SETU project as `SETU_AUTOPILOT_PROMPT.md`.

Last updated: 29 Sep 2026 (after item G).

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
| G. Laptop work recovered from `F:\setu` | In review | this PR | 4 fixes carried over with tests (local query timeout, DB connection during rerank, Hindi/Bengali "year", answer language tag and demo label); larger parts planned as M2 below (`recovery-review.md`) |

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
| M2.1 | Scheme corpus pipeline: safe fetching, manifests, staging database; 29 official sources (central schemes and 13 West Bengal schemes) | Pipeline writes jurisdiction, dates and source hashes (migration 0001), keeps versions (0002); manifest URLs join the freshness watch; tests pass without network |
| M2.2 | Everyday-use evaluation: 12 questions (en, hi, bn) with expected status, sections and evidence | Runs offline in CI from saved retrieval results; baseline recorded before any tuning |
| M2.3 | Scheme clarification (student credit card state, PMJJBY or PMSBY, old-age pension) with follow-up context | Shares `needs_clarification` with the traffic guard; asks at most one question; over-asking measured |
| M2.4 | Local speed: 8-bit models or more Docker memory | Median local answer time measured before and after, on the same questions |
| F | Research write-up: Indian traffic-law temporal benchmark | After M2.2, so it can report both evaluation sets |

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
6. **Workspace layout.** The recovered work has a conversation-style
   redesign; `master` has added cards to the current layout since. Choose
   one before M2 extends the answer screen (see `recovery-review.md`).

## Rules every item follows

Zero spend; no invented values; no confrontational copy; tests and evaluation
first; unfiltered retrieval and the frozen 60-case evaluation unchanged; one
PR per item with green CI before merge.
