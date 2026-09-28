# Official next steps: design note and results

Phase 5, first part (docs/FINDINGS.md, problem P6). Date: 28 Sep 2026.

## Question

SETU answered and stopped. A Karnataka study found that agents made people
aware of welfare schemes, but applications and benefits did not rise (C8).
When SETU cannot decide eligibility, or has just told a rider the official
fine, can it hand the person to the right official service, and only to an
official one?

## Design

| Part | File | Role |
|---|---|---|
| Table | `data/next_steps/services.json` | Six official services. Each has its operator as the page itself states it, the date it was opened and checked, how it was checked, and labels in English, Hindi and Bengali. |
| Rules | same file, `rules` | Which services follow which response status. The first matching rule wins; at most 3 steps. |
| Selector | `app/next_steps.py` | Picks steps by response status and fixed keywords (PM-KISAN, challan). Refuses to load a URL that is not `https` on `.gov.in`/`.nic.in`. No model call. |
| API | `app/schemas.py`, `app/main.py` | `next_steps` on every response, empty unless a rule matches. |
| Workspace | `frontend/src/lib/contracts.ts`, `workspace-demo.tsx` | The contract rejects any step that is not an official `https` link. The workspace shows an "Official next steps" list. |

### The services

| Service | URL | How it was checked |
|---|---|---|
| myScheme | `https://www.myscheme.gov.in/` | Opened 28 Sep 2026; the footer names Digital India Corporation |
| PM-KISAN status | `https://pmkisan.gov.in/BeneficiaryStatus_New.aspx` | Opened 28 Sep 2026; title "Know Your Status :: PMKisan Samman Nidhi"; the footer names the Department of Agriculture & Farmers Welfare |
| e-Challan | `https://echallan.parivahan.gov.in/` | HTTP 200 on 27 Sep 2026; named as the official portal by transport departments (C6) |
| DigiLocker | `https://www.digilocker.gov.in/` | Opened 28 Sep 2026; states it is a MeitY initiative. Documents in it are accepted at checks (C4) |
| Cyber crime portal and 1930 | `https://cybercrime.gov.in/` | Named in the PIB Fact Check warning of July 2026 |
| CPGRAMS | `https://pgportal.gov.in/` | Opened 28 Sep 2026; title "CPGRAMS-Home"; content owned by DARPG |

**Not included yet:**
- **The myScheme eligibility engine.** Its title was found, but the page could not be read.
- **Tele-Law.**
- **Nyaya Setu.** Its WhatsApp launch is reported only in the press (C10).

### Which steps follow which answer

| Response | Steps |
|---|---|
| `eligibility_unverified`, PM-KISAN named | PM-KISAN status, myScheme |
| `eligibility_unverified`, other | myScheme |
| `rule_lookup` (traffic fine, after #5) | e-Challan, DigiLocker |
| `needs_clarification` (traffic fine, after #5) | e-Challan |
| `scam_check` mentioning a challan (after #6) | cyber crime portal, e-Challan |
| `scam_check`, other | cyber crime portal |
| `answered`, `abstained` | none |

The traffic and scam rules are already in the table. They take effect when
PRs #5 and #6 merge, because the API selects steps by response status. No
further code change is needed.

## A fix found on the way

The workspace showed an eligibility answer as "Insufficient retrieved
evidence… SETU abstained". That was wrong. The eligibility route answers by
design without citations: it declines to decide and says why. The workspace
now shows it as a notice ("Eligibility not assessed"), followed by the
official next steps. The quarantine is unchanged. No criteria are read and
no decision is made.

## Why eligibility rules were not encoded (P5)

The plan was rules-as-code for three schemes. The PM-KISAN operational
guidelines on pmkisan.gov.in could not be read from this session, and the
project rule is that no criterion comes from a secondary website. Search
results for PM-KISAN also showed several look-alike sites (`pmkisan.app`,
`pmkisann.com`, `pmkisanstatus.ind.in`). That is more evidence for linking
only to official domains.

The government already runs an eligibility engine: "myScheme - Eligibility
Engine" at `rules.myscheme.gov.in`, with per-scheme checkers. Handing off to
it may serve people better than a second, unofficial copy of the same rules.
The choice is left to the owner (PROGRESS, "Waiting for the owner").

## Tests

- **Backend:** `tests/test_next_steps.py`.
  - Every service is official, checked, and labelled in 3 languages.
  - Look-alike and plain-http URLs are rejected.
  - Answered and abstained responses carry no steps.
  - The scheme-specific rule in 3 languages.
  - The traffic and scam rules.
  - Every selected URL is on the reviewed list.
  - The API adds steps to the eligibility answer.
  - The schema caps steps at 3.
- **Frontend:**
  - Contract tests for official links only, and the cap of 3.
  - A workspace test for the notice and its links, and no steps on an ordinary answer.
  - A browser test on desktop, tablet and mobile: the notice and 2 links, no horizontal scroll, and 0 serious accessibility issues in light and dark.

## Limitations

- Links are checked by hand on the date shown. Nothing re-checks them yet;
  adding them to the weekly freshness watch is a small follow-up.
- Keyword rules are narrow: only PM-KISAN gets a scheme-specific link.
- The labels in Hindi and Bengali need review by a native speaker, like all
  other fixed copy.
