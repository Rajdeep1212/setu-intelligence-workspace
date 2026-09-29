# Roadside Mode: design note and results

Phase 2 of the SETU roadmap (docs/FINDINGS.md, problem P7). Date: 28 Sep 2026.

## Question

Can a person at a traffic checkpoint, possibly with no network, see the
official on-the-spot amount for an offence and where it comes from, without
SETU ever showing a number it cannot back with a primary source?

## Design

| Part | Choice | Why |
|---|---|---|
| Data | `frontend/scripts/roadside-bundle.mjs` bundles `data/traffic_offences/*.json` into `frontend/src/data/roadside-bundle.json` with its SHA-256 and newest `retrieved_at` | The page needs no backend or database. The output is deterministic, so a unit test fails when the committed bundle is stale. |
| Rules | `frontend/src/lib/roadside.ts`, pure functions | Every safety rule is unit-tested in isolation. |
| Offline | Hand-written service worker `frontend/public/roadside-sw.js`, scope `/roadside` | Next.js 16 retries soft navigations offline but cannot serve a full reload without a service worker (bundled docs: `offline-support.md`). No PWA library, so no new dependency. |
| Page | `/roadside`, statically prerendered | Loads fast and can be cached whole. |

### Display rules

1. A number appears only for a `VERIFIED` state compounding row with amounts.
2. Red-light jumping never shows an amount in any state, even if data were
   added. It depends on whether it is booked as a signal violation (s.177) or
   as dangerous driving (s.184, which s.200(1) does not allow to be
   compounded). That is an open legal question.
3. Where the Act names one fixed fine (`central_law.fixed_fine_inr`, new in
   this change and tested against the Act's own wording), a lower state amount
   is flagged and shown beside the central fine, never merged into it.
   Karnataka's helmet (Rs 500 vs Rs 1,000), triple riding (Rs 500 vs
   Rs 1,000) and driving without a licence (Rs 1,000 and Rs 2,000 vs Rs 5,000
   for two/three-wheelers and light motor vehicles) are the cases today.
4. Police fine lists appear under "Other official lists", labelled "Police
   fine list (not a notification)".
5. Notes written for maintainers are cleaned before display: references to
   repository files and to other rows are removed.
6. The bundle date is shown prominently, with a warning after 90 days.
7. The checkpoint guidance is calm: pay only through an e-challan or an
   official receipt, contest later through official channels, and use
   DigiLocker or mParivahan documents (a photo or PDF does not count; C4). A
   test fails if the page ever says to refuse, argue, or that the officer is
   wrong.

## Results

| Measure | Result |
|---|---|
| Rows in the bundle | 21 (3 states × 7 offences): 12 show a verified amount, 9 show none (all of Delhi, and red-light in West Bengal and Karnataka) |
| Unit tests (Vitest) | 21 new: 16 display rules, 5 rendered-page tests |
| Offline, Playwright on desktop, tablet and phone | Load once, go offline, reload: the West Bengal handheld-device amounts (Rs 5,000 first, Rs 10,000 repeat) and their notification still show, and the state picker still works (Delhi shows no number) |
| Accessibility (axe) | 0 violations in light and dark themes across four page states |
| Layout | No horizontal scrolling on any viewport |
| Outside requests | 0 from the page; only 127.0.0.1 |

## Findings along the way

- **Site-wide contrast defect:** the light theme's muted grey (`#66757a`) was
  4.38:1 on the page background, below the 4.5:1 WCAG AA minimum. It affected
  every page's intro text and back link but was never tested, because the
  existing accessibility test only covers the workspace in dark mode. Changed
  to `#5c6b70` (4.72:1 or better on every light background).
- **A browser test near its time limit:** "all primary routes render" loads
  six pages in one test and took 25–32 s against a 30 s limit on a busy
  laptop. It now has three times the budget (`test.slow()`).
- **Phone theme toggle:** the site header hides the theme button on phones,
  so phone users cannot switch themes on these pages. This is existing
  behaviour, left for a design follow-up.

## Limitations

- The service worker caches the page after the first online visit. A person
  who has never opened it cannot use it offline.
- Only three states are covered, and Delhi has no verified amounts yet.
- Amounts are shown as published. SETU does not decide whether a state
  amount below the central fine is lawful.
- Browsers can clear cached data when storage runs low. The page shows
  whether it is saved, but cannot guarantee it stays saved.
