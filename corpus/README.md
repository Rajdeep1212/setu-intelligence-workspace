# Scheme corpus (M2.1)

Official sources for SETU's scheme answers, and the pipeline that stages them
into a separate local database. Nothing here decides eligibility: the corpus
holds official text, and eligibility answers stay switched off (the owner
chose to link myScheme, `docs/PROGRESS.md` item E2).

## What is tracked

`corpus/manifests/batch-00N.json` are reviewed source lists (schema 2,
validated by `ingestion/corpus_manifest.py`). They hold inputs only, never
run state, so running the pipeline does not change them.

| Batch | Items | Excluded | Active sources | Reviewed |
|---|---|---|---|---|
| batch-001 | 10 (PM-KISAN, PMJDY, APY, PMUY, AB-PMJAY, Sukanya Samriddhi, Kanyashree, NFSA 2013, Consumer Protection Act 2019, Senior Citizens Act 2007) | 0 | 11 | 9 Sep 2026 |
| batch-002 | 14 (e-Shram, PMSBY, PMJJBY, PM-SVANidhi, PM-Vishwakarma, PMEGP and West Bengal schemes) | 4 | 10 | 13 Sep 2026 |
| batch-003 | 5 (SBM-G toilets, DDU-GKY, NAPS, NATS, Udyam registration) | 0 | 5 | 13 Sep 2026 |

29 items, 26 active sources. Four items are excluded with the reason
recorded in the manifest: MGNREGA (the portal served only an app shell),
PM-SYM (HTTP 403 to the collector), Lakshmir Bhandar (the host needs unsafe
legacy TLS) and Sishu Sathi (only navigation text). PM-SYM's application link
on `maandhan.in` was dropped because it is not a `.gov.in` / `.nic.in` host.

Per item and source:

- `jurisdiction` is a migration 0001 code. A page published by the West
  Bengal government (`*.wb.gov.in`) is `IN-WB` even for a central scheme,
  because it describes West Bengal's process; everything else is `IN`.
- `effective_from` is set only where the source states it. It is never
  derived from a publication date, so undated sources cannot answer a
  date-specific (`as_of`) question.
- `pin` is what a person reviewed: the SHA-256 of the exact bytes and when
  they were retrieved. PDFs are watched on those bytes. HTML pages differ on
  every request, so they are watched on `text_sha256`, the hash of the text
  extracted by extractor `text_version`, minus narrow `ignore_lines` (two
  pages have a visitor counter).
- `current_status`, `status_as_of` and `practical_coverage` are the
  September reviewer's notes. They are not served to users and were not
  re-verified in M2.1.

The manifests were converted from the recovered laptop run (commit `908ad3d`,
14 Sep 2026). Every pin was recomputed from the snapshot staged in September,
and each snapshot matched the SHA-256 recorded at the time.

## Running the pipeline

Local only, zero spend. Use the ingestion venv (`requirements-ingestion.txt`)
and the local Docker Compose PostgreSQL.

```
python -m ingestion.corpus_pipeline prepare-db
python -m ingestion.corpus_pipeline --manifest corpus/manifests/batch-001.json collect
python -m ingestion.corpus_pipeline --manifest corpus/manifests/batch-001.json index
python -m ingestion.corpus_pipeline --manifest corpus/manifests/batch-001.json verify
python -m ingestion.corpus_pipeline --manifest corpus/manifests/batch-001.json status
```

- `prepare-db` creates `setu_corpus_staging` on 127.0.0.1 and applies
  `db/init.sql`, migration 0001 and migration 0002, each only if missing.
  Every command refuses a database not named `setu_corpus_staging[_suffix]`
  and any non-loopback host, so the application database is never written.
- `collect` fetches with `ingestion/safe_fetch.py` (HTTPS, exact host
  allowlist, public addresses only, redirects re-checked, 12 MB cap, one
  request per host per second), saves the bytes and the extracted text under
  `corpus/staging/<batch>/` (not tracked), and compares them with the pin.
  A source that no longer matches is held as `changed` and is never indexed.
- `index` chunks and embeds validated sources with the app's embedding
  backend, then writes them through `ingestion/db_writer.write_document` with
  jurisdiction, effective dates, source hash and retrieval time. Re-indexing
  a URL with new content archives the old version (migration 0002).
- `verify` runs the manifest's retrieval checks against the staging database
  and writes `corpus/staging/<batch>/retrieval.json`.
- `rollback-staging --confirm-database-name setu_corpus_staging` drops the
  staging database. It needs the exact name.

Run state is `corpus/staging/<batch>/state.json`; commands resume from it.

## When a source changes

The weekly freshness watch (`scripts/freshness_watch.py`) checks every active
source here as well as the traffic fine tables. A `changed` result, or a
`changed` hold in `collect`, means a person must read the new content. If it
is still right to use, update that source's `pin` (new `sha256`,
`retrieved_at`, and for HTML `text_sha256`); the next `collect` fetches it
again and `index` stores it as a new version.

Recompute a text pin with:

```
python -c "import sys; from ingestion.corpus_extract import extract_html, text_fingerprint; print(text_fingerprint(extract_html(open(sys.argv[1], 'rb').read()).text, sys.argv[2:]))" corpus/staging/<batch>/snapshots/<source>.html
```

Changing the extractor (`EXTRACTION_VERSION`) makes every HTML pin
incomparable; the manifest checks then fail until the pins are recomputed.
