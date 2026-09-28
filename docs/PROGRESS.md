# SETU progress

The single source of truth for what is done, in progress and blocked. Every
PR updates this file. A new session reads it first and resumes from the first
item that is not done. The plan and its reasoning are in
[FINDINGS.md](FINDINGS.md); the full autonomous brief is kept in the owner's
SETU project as `SETU_AUTOPILOT_PROMPT.md`.

Last updated: 28 Sep 2026.

## Work items

| Item | Status | PR | Result |
|---|---|---|---|
| Phase 0: verify research, findings report | Done | [#1](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/1) | 19 claims graded: 11 verified, 8 partly, 0 wrong |
| Phase 1: jurisdiction- and date-aware retrieval | Done | [#2](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/2) | 6 of 15 temporal cases pass; unfiltered SQL byte-identical |
| A. Phase 1 leftovers: source hash, retrieval time, PIB backfill | Done | [#3](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/3) | Ingestion stores SHA-256 and UTC fetch time; backfill tags PIB as `IN` |
| B. Phase 2: Roadside Mode (offline) | In review, waiting for the owner | this PR | `/roadside` works offline; 12 of 21 rows show a verified amount; 0 accessibility violations. See [research/roadside-mode.md](research/roadside-mode.md) |
| C. Phase 3: False-premise guard | Next | | Target: 15 of 15 temporal cases |
| D. Phase 4: Scam Shield and freshness watch | Planned | | |
| E. Phase 5: Answer to action (rules-as-code, next steps) | Planned | | Eligibility stays quarantined |
| F. Research write-up: Indian traffic-law temporal benchmark | Planned | | After C |

## Waiting for the owner

These need a person. Work continues on everything else.

1. **Delete merged branches on GitHub** (the cloud session is not allowed to):
   `phase1/temporal-retrieval`, `research/findings-2026-09`,
   `research/findings-2026-09-local`. All their commits are in `master`.
   Keep `recovery/codex-2026-09-14`.
2. **Apply migration 0001, then backfill 0001, to any deployed database**
   before a client sends `jurisdiction` or `as_of`. Until then a filtered
   request fails (503) while unfiltered requests work.
3. **Legal review:** how red-light jumping is booked (signal violation vs
   dangerous driving), and whether Karnataka may compound below the central
   fine (helmet Rs 500 vs Rs 1,000).
4. **Delhi:** the current Section 200 compounding notification, so its rows
   can leave UNVERIFIED.
5. **Name:** "Nyaya Setu" is already used twice; choose a distinct public name
   before launch.
6. **Merge Phase 2 yourself.** It is the first public page that shows legal
   amounts, and merging `master` deploys it through Vercel, so it is left for
   your review rather than merged automatically.

## Rules every item follows

Zero spend; no invented values; no confrontational copy; tests and evaluation
first; unfiltered retrieval and the frozen 60-case evaluation unchanged; one
PR per item with green CI before merge.
