# Review of the recovered laptop work

Date: 29 Sep 2026. Roadmap item G (docs/PROGRESS.md).

## What was reviewed

Branch `recovery/laptop-uncommitted-2026-09-29` holds two commits that were
never in `master`:

| Commit | Date | Size | What it is |
|---|---|---|---|
| `908ad3d` | 14 Sep 2026 | 58 files, about 10,900 lines | A snapshot of that week's work: corpus pipeline, clarification, everyday-use evaluation, network timeout fix, workspace redesign |
| `e7050c0` | pushed 29 Sep 2026 | 35 files, about 1,950 lines | Uncommitted follow-ups found on the laptop's F: drive |

Both branch from `602f1ee`, before the 27 Sep research work. `master` has
changed a lot since then (Phases 1 to 5), so nothing can be merged as is;
each part has to be carried over and checked against today's code.

## Carried over now (this PR)

Each fix was checked against `master` first, and each new test was run
against the old code to confirm it catches the bug.

| Fix | Bug on `master` | Test |
|---|---|---|
| Loopback HTTP client for local queries, 600 s bound, 1 MiB cap (`frontend/src/lib/server/bff.ts`) | The BFF stopped waiting after 90 s (504), and Node's default `fetch` also gives up after about 5 minutes without response headers, while a local answer can take minutes to compute | 4 new tests in `bff.test.ts`, including a 1.1 MB body (new) and redirects |
| Same-site check accepts `localhost` and `127.0.0.1` as the same machine, same protocol and port only | When the browser used `localhost` but the server saw `127.0.0.1` (or the reverse), the site's own requests were rejected with 403 | `bff.test.ts` |
| Database connection is held only during the two searches, not during reranking (`app/retrieval/pipeline.py`) | The connection stayed checked out through the CPU-bound rerank, which can take minutes, so a few slow requests could exhaust the pool | 4 new tests in `test_retrieval_backends.py`; the release test fails on the old code |
| Hindi and Bengali "year" (वर्ष, वर्षों, साल, বছর) match "years" in English evidence (`app/numerical_grounding.py`) | A correct Hindi or Bengali answer citing English evidence ("18 से 70 वर्ष" against "18 to 70 years") was rejected as unsupported, so SETU abstained | `test_numerical_units.py`; 2 of its 3 tests fail on the old code |
| Answers carry a `lang` attribute; demo answers are labelled "Illustrative example: not a retrieved answer" (`workspace-demo.tsx`) | Screen readers read Hindi and Bengali answers with English rules (WCAG 3.1.2); fixed demo answers looked like real retrieved answers | `workspace-demo.test.tsx` |

## Left for the next milestone

These are larger features. They are worth having, but they were written
against the September code and need to be rebuilt on today's `master`.

1. **Scheme corpus pipeline** (`ingestion/safe_fetch.py`, `corpus_manifest.py`,
   `corpus_extract.py`, `corpus_pipeline.py`, `staging_db.py`, 3 manifests).
   29 official sources: PM-KISAN (Department of Agriculture), PMJJBY/PMSBY
   (Department of Financial Services), APY (PFRDA), PMUY (Petroleum),
   PM-JAY (National Health Authority), e-Shram (Labour), and 13 West Bengal
   schemes. It stages into a separate database and gates each batch on a
   manifest. It must be joined to migration 0001 (jurisdiction, dates,
   source hash) and 0002 (version history), and its source URLs should join
   the weekly freshness watch.
2. **Everyday-use evaluation**: 12 questions in English, Hindi and Bengali,
   each with its expected status, required answer sections and evidence.
3. **Scheme clarification**: asks one question instead of guessing (which
   state's student credit card; PMJJBY or PMSBY; which old-age pension).
   It must share the `needs_clarification` status the traffic premise guard
   already uses, and bring the follow-up context field and the 16 KB request
   limit with it.
4. **Local speed**: the two FP32 OpenVINO models total 4.23 GiB while Docker
   had 3.7 GiB, so answers took minutes. Options are 8-bit models or more
   Docker memory; the 600 s bound above is a safety net, not a fix.

## Needs an owner decision

- **Workspace redesign.** `908ad3d` replaced the workspace with a
  conversation layout, a language menu and typed answer sections. `master`
  has since added the premise, scam and next-step cards to the current
  layout. Choose one layout before either is extended further.

## Not carried over

- `docs/demo/` (script, shot list and images for the Clientell demo video).
  Presentation material, not SETU documentation. It stays on the
  recovery branch.
- `docs/everyday-use-journey-checkpoint.md` and `corpus/progress.json`:
  run logs from the laptop, with local folder paths. They stay on the
  recovery branch as history.
- `app/agent/setu.code-workspace`: an editor settings file.
- The darker colours in `globals.css`: `master` already passes the contrast
  checks with its own fix (PR #4).
