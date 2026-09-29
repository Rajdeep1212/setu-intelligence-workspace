# Scam Shield: design note and results

Phase 4a of the SETU roadmap (docs/FINDINGS.md, problem P3). Date: 28 Sep 2026.

## Question

A rider gets an SMS: "Your e-challan of Rs 500 is pending, pay now" with a
link. A farmer gets a WhatsApp forward about PM-KUSUM registration. Can SETU
say, from rules and cited official warnings alone, whether the message shows
the known signs of a scam, and point to the official channel instead?

Kerala Police warned on 26 Sep 2026 about fake e-challan SMS that install a
malicious APK (C6). PIB Fact Check has debunked a fake "Students Laptop
Scheme 2026" and a Rs 8,000 PM-KUSUM "registration fee" (C7), and warned in
July 2026 about fake traffic-challan links. None of this was handled in the
repository before this phase.

## Design

| Part | File | Role |
|---|---|---|
| Sources | `data/scam_shield/sources.json` | Official services, the government-domain rule, and 4 debunks. Every entry has its issuer, date and source URL. |
| Checker | `app/agent/scam_shield.py` | Finds links, APKs, OTP or PIN requests, UPI IDs, urgency and debunk matches in English, Hindi and Bengali. No model call and no network access. |
| Agent | `app/agent/graph.py` | A `scam_gate` node runs first. A screened message is answered and ends there; everything else goes on to the premise gate and normal routing. |
| API | `app/schemas.py`, `frontend/src/lib/contracts.ts` | Route and status `scam_check`, and a structured `scam_check` result. The workspace shows the verdict, each link's host as plain text, and the cited warnings. |

### Rules

- **The official-domain rule is structural, not an allow-list.** A host is
  official only if it is `gov.in`, `nic.in` or ends in `.gov.in` or
  `.nic.in`. The GOV.IN registry states that only government organisations
  can register these and that NIC is the only registrar
  ([registry.gov.in FAQ](https://registry.gov.in/faq.php)). FINDINGS P3
  proposed a reviewed allow-list with edit-distance matching; the structural
  rule replaces it because it cannot go stale and needs no curator. The list
  of official services is kept only so answers can name the right portal.
- **The verdict is never "safe".** The four verdicts are `likely_scam`,
  `suspicious`, `official_link` and `no_warning_signs`. The API contract has
  no "safe" value, and a test checks every answer in all three languages.
- **High-risk signs** (any one gives `likely_scam`): a host that uses a
  government or scheme name but is not on `.gov.in`/`.nic.in` (including
  `.in.net` look-alikes), an APK, a request for an OTP, PIN or password, a
  payment link that is not official, a fine to be paid to a personal UPI ID,
  a link to a bare IP address, or a match with a `false_claim` debunk.
- **Medium-risk signs** (give `suspicious`): a shortened link, a punycode
  host, urgency ("today", "licence will be suspended"), or plain `http://`.
- **An unknown non-government link is information only.** A news article
  link is not called suspicious; it gets "no warning signs" with the host
  named as not a government domain.
- **Two kinds of debunk.** A `false_claim` (the laptop scheme, the PM-KUSUM
  fee) is a warning sign on its own. A `channel_warning` (fake e-challan
  links) only counts when the message also uses a risky channel. A genuine
  challan SMS that points to `echallan.parivahan.gov.in` is therefore
  `official_link`, with the PIB warning shown as related context. This was
  found while testing: the first version flagged the genuine message.
- **Pasted links are never made clickable.** The workspace shows only the
  host as text; the only links in the card are the cited warnings.
- **The screen is conservative.** It runs only for a message with a link, an
  APK, an OTP or PIN request, a UPI ID, or a direct "is this message fake?"
  question. Ordinary questions, including traffic-fine questions such as
  "Police asked ₹5,000 for no helmet, is that right?", go on unchanged.

## Evaluation

| Set | Cases | Languages | Result |
|---|---|---|---|
| Development set (`eval/scam_cases.jsonl`) | 32 (17 scam, 7 genuine, 8 not screened) | en 26, hi 4, bn 2 | 32 of 32 |
| Held-out set (`eval/scam_holdout.jsonl`), written after freezing the code | 12 (6 scam, 3 genuine, 3 not screened) | en 9, hi 2, bn 1 | **10 of 12 before the fix**; 12 of 12 after |

| Safety measure | Result |
|---|---|
| Scams reported as official or with no warning signs | 0 |
| Genuine official messages reported as a likely scam | 0 |
| Answers that call a message safe | 0 |
| Model or network calls | 0 |

### What testing found after the code was frozen

1. **Held-out set.** A fake FASTag KYC link was rated only `suspicious`,
   because FASTag and NHAI were not in the list of impersonated names; and a
   fine to be paid to a personal UPI ID was not screened at all. Both were
   fixed (FASTag and NHAI names; a `payment_to_personal_upi` sign and UPI IDs
   as a screening trigger). After the fix the held-out set is no longer truly
   held out, so the honest estimate is the pre-fix **10 of 12 (83%)**.
2. **The domain named in FINDINGS.** MNRE's warning names
   `kusumyojanaonline.in.net`. The frozen checker gave it `no_warning_signs`,
   because scheme names were not in the impersonation list and `.in.net` was
   not recognised as a look-alike suffix. Scheme names (yojana, PM-KUSUM,
   PMAY, Ayushman, PM-JAY, EPFO) and look-alike suffixes (`.in.net`,
   `.in.com`) were added, with this domain and the real
   `pmkusum.mnre.gov.in` as new development cases.

## Limitations

- The name lists and phrase lists are hand-built. A scam site with a neutral
  name (no government or scheme word) and no other sign gets
  `no_warning_signs`. The answer always says to use the official portal, and
  "no warning signs" is never presented as proof.
- A message that hides its link in an image, a QR code or a phone call is not
  covered.
- Only 4 debunks are included. The list needs a named human curator, and a
  new debunk is added only from PIB Fact Check, a government or police
  statement, or reputable reporting of one.
- The Kerala Police statement (C6) is confirmed only through PTI reporting;
  the police post itself was not found.
- Evaluation sets are small (44 cases) and written by the same team as the
  code. They show the rules work; they do not measure real-world coverage.
