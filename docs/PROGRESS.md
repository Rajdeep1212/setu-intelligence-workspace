# SETU progress

The single source of truth for what is done, in progress and blocked. Every
PR updates this file. A new session reads it first and resumes from the first
item that is not done. The plan and its reasoning are in
[FINDINGS.md](FINDINGS.md); the full autonomous brief is kept in the owner's
SETU project as `SETU_AUTOPILOT_PROMPT.md`.

Last updated: 29 Sep 2026.

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
| E2. Phase 5 (P5): rules-as-code for 3 schemes | Blocked, needs the owner | | See item 6 below |
| F. Research write-up: Indian traffic-law temporal benchmark | Planned | | After C |
| G. Laptop work recovered from `F:\setu` | To review | | 35 files pushed to branch `recovery/laptop-uncommitted-2026-09-29` (commit `e7050c0`, on top of `908ad3d`); port the useful parts into `master` |

All of #4-#9 were merged on 29 Sep 2026 (master `3ee3d4d`). The first
freshness run on GitHub (started by the #8 merge) passed: no pinned source
had changed.

**Next up:** G (review the recovered laptop work), then F (temporal
benchmark write-up). E2 waits for the owner's decision below.

## Waiting for the owner

These need a person. Work continues on everything else.

1. **Delete merged branches on GitHub** (the cloud session is not allowed to):
   `phase1/temporal-retrieval`, `research/findings-2026-09`,
   `research/findings-2026-09-local`, `phase2/roadside-mode`,
   `phase3/premise-guard`, `phase4/scam-shield`, `phase4/version-history`,
   `phase4/freshness-watch`, `phase5/next-steps`. All their commits are in
   `master`. Keep `recovery/codex-2026-09-14` and
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
6. **Eligibility scope (P5).** The PM-KISAN operational guidelines on
   pmkisan.gov.in could not be read from the cloud session (the fetch needs
   your approval), so no scheme rule was encoded; SETU does not invent
   criteria. The government already runs an eligibility engine at
   `rules.myscheme.gov.in`. Choose one:
   (a) hand off to myScheme and keep eligibility quarantined (cheapest; P6
   already links myScheme);
   (b) rules-as-code for 3 schemes from the official guideline PDFs, each
   with a named reviewer's sign-off before its quarantine lifts (about 8
   days).
   For (b), approve fetching pmkisan.gov.in or attach the guideline PDFs.

## Rules every item follows

Zero spend; no invented values; no confrontational copy; tests and evaluation
first; unfiltered retrieval and the frozen 60-case evaluation unchanged; one
PR per item with green CI before merge.
