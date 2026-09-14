# Multilingual question-flow milestone

Verified on 2026-09-08. This note distinguishes the implemented slice from the
larger source-versioning and ingestion roadmap.

## Implemented

- The workspace has one prominent question composer and no attachment control.
- Its three-dot menu selects English, हिन्दी, or বাংলা. English is the default.
- The language code is stored under `setu-response-language-v1`; question text
  and conversation content are not stored in browser storage.
- Submission sends the exact question string and a snapshot of the selected
  response language. A later menu change affects only a later request.
- The backend uses the selected language only for generation and validation.
  Retrieval continues across all indexed source languages.
- Empty retrieval may run one entity-hint correction. A still-unmatched scheme
  name returns a localized clarification instead of inventing an identity.
- Retrieved text is explicitly treated as untrusted evidence in the answer
  prompt. Citation-ID and numerical-claim validation continue to fail closed.
- Request and complete agent-pipeline durations are logged without question or
  answer content. The UI shows only a real request-pending state; it does not
  invent intermediate retrieval progress.

## Verification boundaries

The deterministic backend suite, frontend component/contract suite, production
frontend build, and desktop/tablet/mobile browser suite run without provider
calls. The multilingual demo responses are fixtures; they do not measure live
model translation quality. The offline retrieval metrics are fixture replay,
not a live PostgreSQL/embedding benchmark.

No live public source was fetched or indexed in this milestone. The existing
sanitized DPI fixture remains the only content shown by default. The historical
database counts in the main README were not re-verified because Docker is not
available in this execution environment.

## Local commands

Frontend demo:

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Backend checks (after installing `requirements-ci.txt` in an isolated virtual
environment):

```bash
python -m unittest discover -s tests
python -m eval.offline_evaluation
python scripts/ci_static_checks.py
```

The existing ingestion entry point remains:

```bash
python -m ingestion.ingest --prids <curated-PIB-PRID>[,<curated-PIB-PRID>...]
```

It is not yet the allowlisted, version-retaining update command required by the
master brief. Do not schedule it as though it were. Any future local scheduler
also requires its host machine to be running.

## Database and rollback

This milestone has no schema migration and performs no database writes. Docker
Compose already uses the named `setu_pgdata` volume. Follow the isolated backup
and restore procedure in `docs/DEPLOYMENT.md`; never test a restore over the
active database.

To roll back only this milestone, revert the files listed in the delivery report
with normal version-control review. No database rollback is necessary. Preserve
unrelated worktree edits and do not reset the repository.

## Next smallest milestone

Add an additive document-version migration plus fixture-driven, idempotent
`check -> validate -> publish` ingestion for an explicitly allowlisted pilot
source. Validate it against an isolated PostgreSQL database before the existing
application database is touched. Live PM-KISAN or legal coverage must not be
claimed until those exact official documents have been fetched, reviewed, and
recorded in coverage metadata.
