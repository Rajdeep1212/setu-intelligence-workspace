# SETU: working rules for Claude

SETU answers questions about Indian traffic rules and government schemes
from official sources only. Accuracy matters more than coverage: a wrong
fine or eligibility answer can cost a real person money.

## Start of every session

1. `git fetch`, then work from an up-to-date `master` (or the branch the
   task names).
2. Read `docs/PROGRESS.md` first. It is the source of truth for what is
   done, what is next, and what waits for the owner. Resume from the first
   item that is not done.
3. Read only the files the task needs. Plans and evidence are in
   `docs/FINDINGS.md` and `docs/research/`.

## Hard rules

- **Zero spend.** No paid services, accounts, API keys or cloud resources.
- **Official sources only.** Every amount, date, rule or link comes from a
  `.gov.in` / `.nic.in` page or an official notification, with its date. If
  it cannot be verified, mark it `UNVERIFIED`; never invent or estimate.
- **Keep these as they are unless the owner says otherwise:** Delhi fine rows
  `UNVERIFIED`; red-light `LEGAL_REVIEW`; eligibility switched off (the owner
  chose to link myScheme, not encode rules); earphones not named in s.184.
- **Tone:** calm and practical. Never tell a user to argue with an officer
  or refuse to pay.
- **Privacy:** no secrets, `.env` values or local folder paths in the repo.
- SETU and the career-agent project are separate. Never mix them.

## How to do an item

- One PR per item, branched from `master`, never merged by Claude.
- Tests first. For an evaluation, write held-out cases before any fix and
  report the pre-fix score honestly.
- Carry over recovered work (`recovery/laptop-uncommitted-2026-09-29`) by
  rebuilding it on today's code, not by merging old commits.
- Update `docs/PROGRESS.md` in the same PR.

## Checks before a PR

```
python -m unittest discover -s tests
python scripts/ci_static_checks.py
python -m eval.offline_evaluation --markdown-out /tmp/e.md   # must equal docs/offline-evaluation-report.md
cd frontend && npm run typecheck && npm run lint && npm run test:run && npm run build
```
Browser tests: build, `npm run start -- --hostname 127.0.0.1 --port 3000`
with `SETU_DATA_MODE=demo`, then `npm run test:e2e`.
Read `frontend/AGENTS.md` before frontend work (Next.js 16 differs from
older versions).

## Stop and ask the owner before

A new legal amount or eligibility claim, anything that costs money,
deleting data or branches, changing the answer-screen layout, or any item
under "Waiting for the owner" in `docs/PROGRESS.md`.

## Keep usage low

Run tests quietly and show only failures or the last lines. Do not print
large files or re-read unchanged ones. After each PR, write a short handoff
into `docs/PROGRESS.md` and end the session; start the next item fresh.
