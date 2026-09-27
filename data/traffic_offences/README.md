# Traffic offence tables

One JSON file per jurisdiction. Each fine carries the source it came from, so
SETU can say where a number comes from and how far to trust it. The evidence
behind these values is in [docs/FINDINGS.md](../../docs/FINDINGS.md), claims
C1 to C3.

**These tables are not legal advice.** Amounts change by notification. Check
the linked official source before relying on a value.

## Files

| File | Jurisdiction | Source |
|---|---|---|
| `IN.json` | Central Act | Statute text (Section 184) |
| `IN-WB.json` | West Bengal | West Bengal Traffic Police published schedule (Notification 208-WT/3M-128/97 (Pt. III)(D), 24 Jan 2022) |
| `IN-WB-KOL.json` | Kolkata Police area | Kolkata Traffic Police offences list (updated 28 Oct 2024) |
| `IN-KA.json` | Karnataka | None found yet: every row UNVERIFIED |
| `IN-DL.json` | Delhi | None found yet: every row UNVERIFIED |

Jurisdiction codes go from general to specific: `IN`, then a state
(`IN-WB`), then an enforcing authority inside it (`IN-WB-KOL`). A lookup tries
the most specific code first and falls back to broader ones
(`app/traffic_offences.py`, `lookup`).

## Row format

```json
{
  "offence_id": "earphone_use",
  "offence": "Using earphones while driving",
  "sections": ["184"],
  "first_offence": {"min": 5000, "max": 5000},
  "subsequent_offence": {"min": 10000, "max": 10000},
  "status": "OFFICIAL_PUBLISHED_LIST",
  "source": {
    "url": "https://www.kolkatatrafficpolice.gov.in/offences.pdf",
    "title": "Offences list, Kolkata Traffic Police",
    "date_kind": "list_updated",
    "date": "2024-10-28",
    "notification_ref": null,
    "retrieved_on": "2026-09-27"
  },
  "notes": ""
}
```

Amounts are whole rupees. `min` may be null when the law sets only a maximum.

## Status values

| Status | Meaning | Amounts |
|---|---|---|
| `VERIFIED_PRIMARY` | Read from the gazette notification or statute on an official site | Required, official host |
| `OFFICIAL_PUBLISHED_LIST` | Published by the enforcing authority on its official site | Required, official host |
| `SECONDARY` | Statute text reproduced by a legal database | Required; show with a warning |
| `UNVERIFIED` | Not confirmed | Must be null; `notes` says what would settle it |

Official hosts are `*.gov.in`, `*.nic.in` and the named sites listed in
`OFFICIAL_NAMED_HOSTS` in `app/traffic_offences.py`, each with a reason.

## Adding or changing a value

1. Find the current compounding notification (Section 200) or the enforcing
   authority's published list on its official site.
2. Update the row, its `source` block and `retrieved_on`.
3. Run `python -m unittest tests.test_traffic_offences`. The tests fail on any
   amount without a source, any official status on an unofficial host, and any
   UNVERIFIED row that carries an amount.
