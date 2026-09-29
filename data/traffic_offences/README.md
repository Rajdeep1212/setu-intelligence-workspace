# Traffic offence tables

One file per jurisdiction (`WB.json`, `KA.json`, `DL.json`), validated by
`schema.json` and by `tests/test_traffic_offences.py`. The premise guard, the
Roadside Mode bundle and the fine answers read only these files.

Every entry in `sources` records the file that was actually read: its URL,
the SHA-256 of its bytes, and the date it was retrieved. Amounts are
`VERIFIED` only when read from that file; everything else stays `UNVERIFIED`
or `LEGAL_REVIEW`.

## Freshness watch

`.github/workflows/freshness.yml` runs `scripts/freshness_watch.py` every
Monday at 03:17 UTC, and whenever these tables change on `master`. It
downloads each source again and compares the SHA-256 with the pinned value.
Run it locally with:

```bash
python scripts/freshness_watch.py
```

| Result | Meaning | What to do |
|---|---|---|
| unchanged | Same bytes as when the amounts were read | Nothing |
| changed | The file at that URL is different | A person re-reads it. If the amounts are the same, update `sha256` and `retrieved_at`. If they differ, update the rows and cite the new notification. |
| unreachable | Blocked, timed out or missing | One unreachable source is reported but does not fail the run. If every source is unreachable, the run fails, because nothing was checked. |

A new hash does not by itself mean the law changed. A re-scanned or
re-signed PDF also changes the bytes. Source files are never committed; only
their hashes and metadata are.

GitHub pauses scheduled workflows in a repository with no activity for 60
days. A push that touches these tables runs the watch again.
