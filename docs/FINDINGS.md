# Research findings and build plan

Branch `research/findings-2026-09` · checked 27 Sep 2026 · Phase 0 of the
[build roadmap](#5-updated-12-week-roadmap).

This document grades the 19 research claims behind the SETU build plan
against primary sources, maps each product problem to the code that handles
it today, and sets the 12-week plan with an exit gate per phase. Every source
was read on 27 Sep 2026 unless stated otherwise. Quotes are kept under 15
words; everything else is paraphrased.

Grades: **VERIFIED** (primary source confirms the claim as worded or with a
minor precision), **PARTLY** (the core is right, but a material detail is
wrong or unconfirmed), **UNVERIFIED** (no primary source found either way),
**WRONG** (a primary source contradicts it).

## 1. Problem statement

A person at a traffic checkpoint needs the rule and amount that apply in
their state on that date. Those differ by state and change over time. Parliament
raised central penalties in the MV (Amendment) Act 2019, in force for
penalties from 1 Sep 2019 (C1). Each state then sets its own compounding
(spot-settlement) amounts under s.200. West Bengal did so in January 2022 and
Karnataka in September 2019, and some of Karnataka's amounts are below the
central fines (C3). Even official copies lag: the India Code PDF of the MV Act
retrieved on 27 Sep 2026 still prints the pre-2019 s.184 penalty (P4). Some
questions have no single answer. Earphones for music are not named in central
law, yet the Kolkata Traffic Police schedule books them under s.184 (C2).
Scammers copy official channels, such as fake e-challan SMS messages that
deliver a malicious APK (C6) and fake scheme registrations (C7). Studies from
other jurisdictions show the failure modes are general. Static legal RAG picked the
date-applicable version 0% of the time in a French tax benchmark (C13).
Across ten frontier models, the median model identified only 44% of the
material facts a legal question left out, jurisdiction among them (C14).
Awareness alone did not raise welfare-scheme uptake in a south Indian field
trial (C8). SETU therefore has to condition answers on state
and date, check the user's premise, refuse to show unsourced amounts, and hand
people a safe next step.

## 2. Claim verification

| ID | Claim (short) | Grade | Corrected wording | Primary source | Checked |
|---|---|---|---|---|---|
| C1 | s.184 amended in 2019 to cover handheld devices; Rs 1,000–5,000 first; up to Rs 10,000 subsequent | PARTLY | Act 32 of 2019 s.67 lists "use of handheld communications devices while driving" as dangerous driving (s.184 Explanation (c)). First offence: 6 months–1 year, or Rs 1,000–5,000, or both. Repeat within three years: up to 2 years, or a fine **of** Rs 10,000 (a fixed amount, not "up to"), or both. In force 1 Sep 2019 (S.O. 3110(E)). s.200(1) now allows s.184 to be compounded **only** for handheld-device use (s.86). PIB's summary table says "up to Rs. 10000"; the Act text controls. | [Gazette, Act 32 of 2019](https://egazette.gov.in/WriteReadData/2019/210413.pdf); [PIB 1583331](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1583331) and [table](https://static.pib.gov.in/WriteReadData/userfiles/MVA.pdf) | 2026-09-27 |
| C2 | Earphones for music not named centrally; how KA, WB, DL treat them | PARTLY | Central: not named in s.184 or in the **Motor Vehicles (Driving) Regulations, 2017** (G.S.R. 634(E), 23 Jun 2017). These replaced the *Rules of the Road Regulations, 1989*; there are no "Rules of the Road Regulations 2017". Reg. 37(1) bans handheld phones and other communication devices; reg. 5(3) requires the driver to avoid distracting activity. Breaking these regulations is punishable under s.177A (Rs 500–1,000). G.S.R. 586(E) of 25 Sep 2020 amended the Regulations on handheld devices; the amended text was not read. CMVR full text not checked. **WB:** WB MV Rules 1989 r.218 bars wearing earphones while driving (Indian Kanoon copy only). The Kolkata Traffic Police schedule books earphones under s.184 at Rs 5,000 first / Rs 10,000 subsequent. **KA (2021):** press reports only (Bengaluru traffic police said a Rs 1,000 fine applies); no official order found. **DL:** no official source found. | [Driving Regulations 2017](https://egazette.gov.in/WriteReadData/2017/176975.pdf); [Kolkata Traffic Police offences](https://www.kolkatatrafficpolice.gov.in/offences.pdf) row 50; [PIB 1659408](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1659408) | 2026-09-27 |
| C3 | State s.200 notifications for WB, KA, DL with seven offence amounts | PARTLY | **WB VERIFIED:** No. 208-WT/3M-128/97 (Pt.III)(D), 24 Jan 2022, immediate effect (signed department copy; gazette issue not located). **KA VERIFIED:** TD 250 TDO 2019, Karnataka Gazette Extraordinary No. 781, 21 Sep 2019 (hosted by the Transport Department); no later notice found. Several KA amounts (helmet and triple riding Rs 500) are below the fixed central fine of Rs 1,000. **DL UNVERIFIED:** only a 2008 notification is on the department site; 2020 and Sep 2024 notifications are press-reported. Red-light amounts are UNVERIFIED in all three: no s.200 row names them, and s.184 is compoundable only for handheld devices. Amounts: [data/traffic_offences/](../data/traffic_offences/). | [WB 208-WT](https://transport.wb.gov.in/wp-content/uploads/2022/02/208-WT-DATE-24-01-2022.pdf); [KA TD 250 TDO 2019](https://transport.karnataka.gov.in/storage/pdf-files/section%20200.pdf); [DL 2008](https://transport.delhi.gov.in/sites/default/files/transport_data/trrs35.pdf) | 2026-09-27 |
| C4 | DigiLocker/mParivahan documents valid; CMVR r.139 as amended | VERIFIED | MoRTH advisory of 9 Aug 2018 asked states to accept DigiLocker/mParivahan documents at par with originals. The CMVR was amended in Nov 2018 to allow electronic production (SOP, 20 Sep 2019). G.S.R. 584(E) of 25 Sep 2020, in force 1 Oct 2020, says physical documents are not to be demanded once validated electronically. Only documents on DigiLocker or mParivahan count; a photo or PDF does not. The gazette text of r.139 was not read. | [PIB 9 Aug 2018](https://pib.gov.in/newsite/PrintRelease.aspx?relid=181696); [PIB 1585679](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1585679); [PIB 1659408](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1659408) | 2026-09-27 |
| C5 | J-PAL helmet-fine information RCT, Rajasthan, 17,369 motorists, 2012 | PARTLY | Authors, sample, 112 towns and timing match. **No results are published**: J-PAL lists no paper and says further work is "on hold" pending MV Act amendment. Baseline only: about 35% of stopped riders reported paying a bribe, and the mean payment was about Rs 76. Nothing is known about the effect on bribes. | [J-PAL evaluation page](https://www.povertyactionlab.org/evaluation/changing-beliefs-changing-bribes-india) | 2026-09-27 |
| C6 | Kerala Police warning, 26 Sep 2026, fake e-challan SMS with APK | PARTLY | Confirmed by a PTI report datelined Thiruvananthapuram, 26 Sep 2026, citing a police statement. The Kerala Police post itself was not found. Official domains named by the advisory in general terms: `echallan.parivahan.gov.in` and `parivahan.gov.in` (both return HTTP 200, 27 Sep 2026) and the state MVD site. | [ThePrint/PTI](https://theprint.in/india/keralam-police-warn-of-malicious-apk-scam-via-fake-e-challan-sms/3053993/) (secondary) | 2026-09-27 |
| C7 | PIB Fact Check: fake Students Laptop Scheme 2026 (Jan 2026); Rs 8,000 PM-KUSUM fee (Sep 2024) | VERIFIED | All India Radio reported both PIB Fact Check debunks: laptop scheme on 12 Jan 2026, PM-KUSUM on 8 Sep 2024. PIB debunked further laptop-scheme variants later in 2026. The official PM-KUSUM site is `pmkusum.mnre.gov.in`. | [newsonair, laptop](https://www.newsonair.gov.in/govt-warns-public-against-fake-students-laptop-scheme-2026-messages); [newsonair, PM-KUSUM](https://www.newsonair.gov.in/pib-fact-check-unit-warns-of-scam-fraudsters-charging-rs-8000-for-pm-kusum-yojana-registration) | 2026-09-27 |
| C8 | Berg, Rajasekhar, Manjula: agents raised awareness, not applications or benefits | VERIFIED | EDCC 70(2):901–939 (2022). Awareness rose but applications and receipt did not; possible effects for two new schemes; satisfaction with government services rose. | [doi:10.1086/713880](https://doi.org/10.1086/713880); [author manuscript](https://research-information.bris.ac.uk/ws/files/231072504/Pushing_Welfare_Encouraging_Awareness_and_Uptake_of_Social_Benefits_in_South_India.pdf) | 2026-09-27 |
| C9 | Jugalbandi: 171 programmes, 10 languages, via English | VERIFIED | Microsoft: 10 of 22 official languages and 171 of about 20,000 programmes; speech is transcribed, translated to English, answered, and translated back. | [Microsoft Source Asia](https://news.microsoft.com/source/asia/features/with-help-from-next-generation-ai-indian-villagers-gain-easier-access-to-government-services/) | 2026-09-27 |
| C10 | Nyaya Setu, Law Ministry WhatsApp service, launched 1 Jan 2026, AI plus panel lawyers | PARTLY | PIB confirms a Department of Justice "Nyaya Setu" AI chatbot built by BHASHINI, unveiled 31 Mar 2026. The 1 Jan 2026 WhatsApp launch and panel-lawyer hand-off (via Tele-Law) appear only in press reports. The name is also used by an NIC Chandigarh police app (PIB, 11 Feb 2026). | [PIB 2247310](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2247310); [PIB 2226442](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2226442) | 2026-09-27 |
| C11 | Samadhan Didi, CPGRAMS voice chatbot, 30 May 2026, 22 languages | VERIFIED | Launched 30 May 2026 by DARPG with BHASHINI; supports all 22 scheduled languages. | [newsonair](https://newsonair.gov.in/union-minister-jitendra-singh-launches-ai-enabled-cpgrams-voice-chatbot-samadhan-didi/) | 2026-09-27 |
| C12 | Stanford RegLab: legal AI tools hallucinate ~17–33% | VERIFIED | Lexis+ AI, Westlaw AI-Assisted Research and Ask Practical Law AI each hallucinated 17%–33% of the time (Magesh et al.; JELS 2025). | [RegLab](https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/) | 2026-09-27 |
| C13 | arXiv 2608.09393: static RAG 0% date-applicable; version-aware ~98% | VERIFIED | French tax code, 32,436 article versions. Static RAG retrieved the applicable version 0% of the time; an end-to-end multi-version retriever reached 98.3% mean strict accuracy. Evidence is from French law, not Indian law. | [arXiv 2608.09393](https://arxiv.org/abs/2608.09393) | 2026-09-27 |
| C14 | arXiv 2608.20220 InsufficiencyBench: read and summarise | VERIFIED (read) | 202 items, six domains, 24 US jurisdictions. Jurisdiction is one of eight missing-element categories (46 missing instances). No model exceeds F2 = 0.46; median recall 0.44. The best model still silently answers 13.2% of deficient queries and over-flags 72.4% of complete ones. For SETU: ask for state and date by rule, and measure over-asking too. | [arXiv 2608.20220](https://arxiv.org/abs/2608.20220) | 2026-09-27 |
| C15 | Beeck Center: plain prompting 0% on numerical rules; structured approaches did better | VERIFIED | Experiment 3 (SNAP, three states): plain prompting got 0% on numerical rules such as income and asset limits. RAG with a manually curated rules template produced nearly all rules correctly. Complex logic still needed human oversight. | [Digital Government Hub report](https://digitalgovernmenthub.org/publications/ai-powered-rules-as-code-experiments-with-public-benefits-policy/) | 2026-09-27 |
| C16 | Catala used in production by French administrations | PARTLY | ICFP 2021 paper exists. CNAF announced on 8 Jun 2026 that it chose Catala as a structuring technology for future calculation engines. No source found saying Catala runs in production at CNAF or DGFiP. Licence Apache-2.0. | [CNAF press release](https://www.caf.fr/professionnels/presse/publications/la-cnaf-et-inria-s-engagent-ensemble-pour-developper-catala-une-solution-souveraine-de-calcul-des) | 2026-09-27 |
| C17 | Farmer.Chat: 15,000+ farmers, 300,000+ queries | VERIFIED | Over 15,000 farmers and 300,000 queries, across four countries (not India only). | [arXiv 2409.08916](https://arxiv.org/abs/2409.08916) | 2026-09-27 |
| C18 | IndicVoices language coverage and licence | VERIFIED | 22 scheduled languages, 400+ districts, CC BY 4.0 (reuse, including commercial, with attribution). Access is gated behind sharing contact details on Hugging Face. The recordings are of real speakers, so a privacy review is needed before use. | [Hugging Face dataset card](https://huggingface.co/datasets/ai4bharat/IndicVoices) | 2026-09-27 |
| C19 | No public benchmark for date- or state-applicable retrieval in Indian law | PARTLY | None found. IL-TUR (ACL 2024) and AILQA (arXiv 2607.18825) cover Indian legal understanding and QA, not temporal or state applicability. Temporal benchmarks exist for French tax (C13) and German statutes (arXiv 2605.23497). TaxFlow (2026) applies temporal filtering to Indian tax law, but its data could not be read (paywall). | [IL-TUR](https://arxiv.org/abs/2407.05399); [AILQA](https://arxiv.org/abs/2607.18825); [arXiv 2605.23497](https://arxiv.org/abs/2605.23497) | 2026-09-27 |

### Correction to the plan's example answer

The plan's target answer to "Police say Rs 10,000 for earphones while riding"
says central law does not name earphones and leaves the state amount pending.
The first half holds. For West Bengal the full picture is:

- WB notification 208-WT compounds s.184 at Rs 5,000 for a first offence and
  Rs 10,000 for a repeat within three years (Schedule II Sl. No. 11).
- The Kolkata Traffic Police schedule books "use earphone while driving" under
  s.184 at the same two amounts (row 50), but its row 63 lists radio or mobile
  phone use under WB rule 218(3) at Rs 500 / Rs 1,500.
- s.200(1) allows s.184 to be compounded only for handheld-device use.

So "Rs 10,000" matches the repeat-offence amount on an official Kolkata
schedule, but not a first offence. Whether music earphones fall under s.184 is
not settled by central law. The answer card should say exactly that. It must not
tell the rider the officer is wrong, and it must still end with "pay only through
an e-challan or official receipt, contest later".

## 3. Problems, current code, and fixes

Effort is in working days for one engineer. Every fix is zero-cost: local
code, public-repo GitHub Actions on standard runners, and official public
sources. None needs a paid service.

### P1. Jurisdiction and date

- **Evidence:** C1, C3, C13; India Code's MV Act PDF still shows the pre-2019
  s.184 penalty (retrieved 27 Sep 2026, SHA-256 `1515b622…2127`).
- **Current state:** [db/init.sql:4-24](../db/init.sql) defines `documents`
  and `chunks` with `language` only. Both retrieval legs filter on language
  alone ([dense.py:39](../app/retrieval/dense.py),
  [keyword.py:37-38](../app/retrieval/keyword.py)).
  [pipeline.py:40-54](../app/retrieval/pipeline.py) takes no state or date.
  [schemas.py:6-8](../app/schemas.py) accepts only `query` and `language`.
  Ingestion stores only `prid` and `posted_on`
  ([ingest.py:58](../ingestion/ingest.py)).
- **Fix:** migration 0001 (this branch) adds `jurisdiction`,
  `effective_from`, `effective_to`, `source_hash` and `retrieved_at`. Next:
  add `jurisdiction` and `as_of` to both retrieval legs as hard `WHERE`
  filters on `COALESCE(chunk, document)` values before RRF and rerank. Add
  optional `jurisdiction` and `as_of` to `QueryRequest`. Tag the 8 existing
  PIB documents `IN` (central).
- **Status (28 Sep 2026):** done. Retrieval filters merged in PR #2
  (`app/retrieval/filters.py`); an unknown `effective_from` stays unknown, so
  undated sources are excluded from date-specific searches, and an empty
  filtered result makes the agent abstain. Ingestion now records `source_hash`
  and `retrieved_at` when migration 0001 is present
  (`ingestion/provenance.py`), and `db/backfills/0001_tag_pib_central.sql`
  tags existing PIB documents `IN` (operator-run). Live status is in
  [PROGRESS.md](PROGRESS.md).
- **Acceptance test:** the 6 `temporal_retrieval` cases in
  `eval/temporal_cases.jsonl` flip from xfail to pass (remove their markers).
  A new unit test shows a chunk outside `[effective_from, effective_to)` is
  never returned.
- **Effort:** 4 days (retrieval 2, request schema and ingestion 1, backfill
  and tests 1).
- **Risks:** most PIB releases have no clear effective date, so `NULL` must
  mean "unknown", never "always valid". Hard filters can empty the candidate
  set; the answer must then abstain rather than fall back to unfiltered
  results.

### P2. False premises and missing facts

- **Evidence:** C14 (models miss missing jurisdiction; best still answers
  13.2% of deficient queries), C12, C1/C2 example above.
- **Current state:** the only deterministic guard is the eligibility
  quarantine ([graph.py:85-100](../app/agent/graph.py)). The numeric check
  ([numerical_grounding.py:274](../app/numerical_grounding.py), used at
  [graph.py:235](../app/agent/graph.py)) compares numbers in the model's
  **answer** with evidence. It never checks a number the **user** asserted.
  Nothing asks for a missing state or date.
- **Fix:** add `app/agent/premise.py` with two deterministic functions.
  `missing_facts(query)` detects state and date mentions using a reviewed
  list of state and city names and date patterns in en/hi/bn.
  `check_premise(query, table)` extracts claimed amount and offence and
  compares them with `data/traffic_offences/`. Add a LangGraph node before
  retrieval. A missing state returns a clarifying question; a contradicted
  premise returns the verified amount with sources; an unverified row says so.
- **Acceptance test:** the 3 `missing_facts` and 6 `false_premise` cases flip
  to pass. Add complete-query controls so over-asking is measured too (C14
  over-flag finding).
- **Effort:** 6 days.
- **Risks:** code-mixed and transliterated input (a labelled repo
  limitation); city-to-state mapping (Kolkata Police area versus the rest of
  WB); tone. The response must never tell a user to dispute an officer on the
  spot.

### P3. Scam links and fake scheme messages

- **Evidence:** C6, C7; MNRE's warning names look-alike domains such as
  `kusumyojanaonline.in.net`, which ends in `.net`, not `.gov.in`.
- **Current state:** no URL, SMS or APK handling anywhere in `app/`,
  `ingestion/` or `frontend/src/` (searched 27 Sep 2026).
- **Fix:** a deterministic checker in `app/scam_shield.py`. It matches the
  exact host against a reviewed allow-list (each entry with its official
  source), flags `.apk` links, URL shorteners and look-alike hosts (edit
  distance to allow-listed names), and flags personal-number senders. It also
  matches text against a curated list of PIB Fact Check debunks, each with its
  source URL and date. There is no model in the loop.
- **Acceptance test:** a fixture set of known scam samples (from C6/C7
  descriptions, synthetic) is never marked safe; every allow-listed host
  passes; `gov.in.net`-style hosts fail.
- **Effort:** 4 days.
- **Risks:** allow-lists go stale; "not on the list" must read as "could not
  verify", never "scam". The debunk list needs a named human curator.

### P4. Stale sources and no version history

- **Evidence:** India Code PDF lag (above); C13.
- **Current state:** the scraper fetches with no hash, ETag or retrieval
  time ([scraper.py:159](../ingestion/scraper.py)). The writer upserts on URL,
  overwriting `raw_text` and resetting `created_at`, then deletes the old
  chunks ([db_writer.py:47-63](../ingestion/db_writer.py)). History is
  destroyed on every re-ingest.
- **Fix:** write `source_hash` and `retrieved_at` on ingest. Stop destructive
  upserts: insert a new document version and close the old one with
  `effective_to`. Add a freshness watch as a scheduled GitHub Actions workflow
  on this public repository (standard `ubuntu-latest`, free for public
  repos, no secrets). It re-downloads each source URL in
  `data/traffic_offences/*.json`, compares SHA-256 with the pinned value, and
  fails with a step summary listing changed sources. Store hashes and
  metadata in Git, not source bodies, in line with the README's
  no-source-bodies rule. No cloud bucket.
- **Acceptance test:** a test source whose pinned hash is altered makes the
  watch fail in one run; unchanged sources pass.
- **Effort:** 4 days.
- **Risks:** some government sites block cloud-runner IP ranges (India Code
  returned 403 to one fetch tool). Scanned PDFs can change bytes without
  changing content. GitHub pauses scheduled workflows after 60 days without
  repository activity. The workflow must also be added to
  `scripts/ci_static_checks.py` review rules.

### P5. Eligibility quarantine

- **Evidence:** C15 (plain prompting 0% on numerical rules), C16.
- **Current state:** correctly fails closed.
  [graph.py:155-170](../app/agent/graph.py) returns
  `eligibility_unverified` without reading criteria;
  [seed_eligibility.py:1-9](../ingestion/seed_eligibility.py) labels the three
  rows illustrative placeholders; the UI says no determination is made
  ([eligibility-workflow.tsx:37](../frontend/src/components/workspace/eligibility-workflow.tsx)).
- **Fix:** rules-as-code for 3 schemes as plain, tested Python functions (or
  Catala, Apache-2.0, if the owner prefers). Each clause cites its official
  source clause and effective date. The LLM only extracts user facts into a
  typed profile; the rule function decides.
- **Acceptance test:** one unit test per rule clause, including boundary
  values; a recorded human sign-off per scheme before its quarantine lifts.
- **Effort:** 8 days for 3 schemes.
- **Risks:** scheme guidelines change mid-year; state top-ups differ from
  central rules; the human reviewer is a named dependency.

### P6. Answers stop at information

- **Evidence:** C8 (awareness without uptake).
- **Current state:** `QueryResponse` carries answer, sections and
  citations only ([schemas.py:34-40](../app/schemas.py)). The eligibility
  preview tells users to verify officially but gives no link
  ([eligibility-workflow.tsx:50](../frontend/src/components/workspace/eligibility-workflow.tsx)).
- **Fix:** add an optional `next_steps` list to the response: a document
  checklist and official where-to-apply or where-to-pay links. Each link comes
  only from a reviewed table with its source (e-challan and Parivahan from C6,
  myScheme from C7, CPGRAMS and Tele-Law after their URLs are verified).
- **Acceptance test:** every `next_steps` URL is on the allow-list; a
  response without verified steps carries none.
- **Effort:** 4 days.
- **Risks:** handing off to a WhatsApp service (Nyaya Setu) depends on
  a number found only in press reports (C10); do not ship it until an
  official source confirms it.

### P7. Offline use at a roadside check

- **Evidence:** C4 (DigiLocker/mParivahan documents are valid at checks).
- **Current state:** the frontend has no service worker, web manifest or
  offline data (searched `frontend/src`, 27 Sep 2026). Demo fixtures are
  bundled but not usable offline as a product
  ([bff.ts:9,41](../frontend/src/lib/server/bff.ts)).
- **Fix:** Roadside Mode as a static page that bundles
  `data/traffic_offences/*.json`, shows the bundle's SHA-256 and "valid as of"
  date, and is cached by a service worker. It works with the network off and
  shows only VERIFIED amounts.
- **Acceptance test:** Playwright with the browser offline loads the page and
  shows a verified WB amount with its source; an UNVERIFIED row shows no
  number.
- **Effort:** 5 days.
- **Risks:** a cached bundle ages silently; show its date prominently and
  warn after 90 days. Copy review for tone is a gate.

## 4. Claims that failed or stayed unverified

No claim was graded WRONG. These points stay open:

| Item | What is missing | What would settle it |
|---|---|---|
| C1 subsequent-offence wording | Plan says "up to Rs 10,000"; the Act says "of ten thousand rupees" | Settled. Use the Act text. |
| C2 CMVR text; amended Driving Regulations reg. 37 | CMVR full text not searched; G.S.R. 586(E) (25 Sep 2020) text not read | egazette.gov.in copies of both |
| C2 WB rule 218 | Only an Indian Kanoon copy was read | WB Transport Department copy of the WB MV Rules 1989 as amended |
| C2 Karnataka 2021 earphone order | Press only | Bengaluru Traffic Police or Karnataka Transport order naming the section |
| C2 Delhi earphones | Nothing found | Delhi Traffic Police notice or challan code list |
| C3 WB gazette publication | Department copy only | West Bengal Gazette issue carrying 208-WT |
| C3 KA currency | No superseding notice found on the department page | Karnataka Gazette index for s.200 notifications after 21 Sep 2019 |
| C3 KA amounts below central fines | Legality of compounding below a fixed statutory fine | Legal opinion; any MoRTH circular on the point (press-reported in 2019) |
| C3 Delhi | Current notification not found | Delhi Gazette Part IV notifications of 13 Mar 2020 and Sep 2024 |
| C3 red-light compounding | Which penal section and which row applies | Legal review of s.184 Explanation (a) versus s.177/177A |
| C4 r.139 text | Read via PIB only | egazette copy of G.S.R. 584(E) |
| C5 results | Unpublished | Author working paper, if any |
| C6 primary post | PTI only | Kerala Police official page or verified social account post |
| C10 launch date and panel lawyers | Press only | Department of Justice or PIB release on the WhatsApp service |
| C16 production status | Adoption announced, production not shown | CNAF or DGFiP statement of live use |
| C19 TaxFlow data | Paywalled | Paper's data-availability statement |

## 5. Updated 12-week roadmap

Week 1 starts Monday 28 Sep 2026. A phase starts only when the previous gate
passes. Zero spend throughout: no cloud resources, paid APIs, paid runners or
secrets.

| Phase | Weeks | Scope | Exit gate |
|---|---|---|---|
| 0 Verify and baseline | 1 (28 Sep–4 Oct) | This document, baseline, claim grades | Owner approves this PR; every claim graded with a source (done here) |
| 1 Jurisdiction and date data | 2–3 (5–18 Oct) | Migration 0001 (done), offence tables (done), date/state filters in retrieval, request fields, ingestion hashes, backfill `IN` | The 6 `temporal_retrieval` cases pass; no fine appears without a VERIFIED source (tested); migration applied to a local database with up and down verified |
| 2 Roadside Mode | 4–5 (19 Oct–1 Nov) | Offline page and bundle, document-rights copy (C4), calm payment script | Works with network off (Playwright); copy review confirms no confrontation coaching |
| 3 False-premise guard | 6–7 (2–15 Nov) | `app/agent/premise.py`, LangGraph node, clarifying questions | All 15 temporal cases pass; zero false premises accepted; missing state always asks; complete-query over-ask rate reported |
| 4 Scam Shield and freshness watch | 8–9 (16–29 Nov) | Deterministic link and SMS checker; scheduled GitHub Actions hash watch on the public repo (no cloud bucket) | No known scam sample marked safe; an altered pinned hash fails the watch in one run |
| 5 Rules-as-code and action | 10–12 (30 Nov–20 Dec) | 3 schemes as tested rules; `next_steps` with verified links | A unit test per rule clause; human sign-off recorded before each scheme leaves quarantine |

After week 12: voice and WhatsApp channel, shareable answer card with source
hash, temporal benchmark write-up, and a brand name distinct from "Nyaya
Setu", which is already used by two government services (C10).

## Baseline for this branch

Recorded on Windows 11 with Python 3.11.16 (local conda environment matching
CI) and Node.js 24.19.0 (CI uses 22). Python 3.13 could not install the pinned
`asyncpg==0.29.0` without a C++ toolchain, so it was not used.

| Check | Before (master 602f1ee) | After (this branch) |
|---|---|---|
| `python -m compileall -q app ingestion eval tests` | pass | pass |
| `python -m unittest discover -s tests` | 114 passed | 135 passed (114 + 21 new) |
| `python -m eval.offline_evaluation` | 60/60; report matches `docs/offline-evaluation-report.md` | unchanged, 60/60, report matches |
| `python -m eval.temporal_evaluation` | n/a | 15/15 expected failures, 0 unexpected |
| `python scripts/ci_static_checks.py` | pass | pass |
| `python -m pip check` | pass | pass |
| `npm ci` | pass, 0 vulnerabilities | not re-run (no frontend change) |
| `npm run typecheck` / `npm run lint` | pass / pass | not re-run (no frontend change) |
| `npm run test:run` | 28 passed, 1 skipped | not re-run (no frontend change) |

Notes: the plan's `npm test` starts Vitest in watch mode, so `npm run
test:run` (what CI runs) was used. The README's recorded counts (112 backend,
25 frontend) are older than the current suite (114 and 28). `npm run build`,
`npm run test:e2e` and `docker compose config` were not run for this
documentation-and-data change. The Docker daemon was not running on the
Windows machine, so migration 0001 was first checked structurally only.

### Migration 0001 executed against PostgreSQL

A second run on Linux executed migration 0001 against PostgreSQL 16.13 in a
throwaway cluster, starting from `db/init.sql`. pgvector was not installed
there, so for this test only the `embedding` column type was swapped for
`real[]` and its HNSW index skipped; the migration does not touch either.

| Step | Result |
|---|---|
| Apply `0001_...up.sql` to a fresh `init.sql` schema | Pass; 10 columns added |
| Apply it a second time | Fails at the first `ADD CONSTRAINT` and rolls back; schema unchanged, as the header says |
| `jurisdiction` values `IN`, `IN-WB` | Accepted |
| `jurisdiction` values `IN-WB-KOL`, `in-wb` | Rejected |
| `source_hash` of 64 lowercase hex characters / `ABC` | Accepted / rejected |
| `effective_from = effective_to` (empty half-open range) | Rejected |
| Existing `ON CONFLICT (url)` upsert used by `ingestion/db_writer.py` | Still works |
| Lookup indexes on `documents` and `chunks` | Created |
| `0001_...down.sql` | Pass; all 10 columns removed |
| Re-apply after rollback | Pass |

### Additional notes from the second run

- The API image does not include `data/traffic_offences/` (the `Dockerfile`
  copies `app`, `ingestion` and `models/openvino` only). Add it when the API
  starts reading the tables.
- Possible prior art: a public GitHub project, `mudit108-code/Drive-Legal`,
  has an open issue about offline citizen rights and DigiLocker validity. It
  was seen in search results only and not reviewed.
- A Vercel preview check runs on pull requests in this repository. Keep that
  Vercel account on its free plan to stay within the zero-spend rule.
