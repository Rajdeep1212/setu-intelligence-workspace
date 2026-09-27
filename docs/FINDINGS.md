# SETU research findings and fix plan

Date checked: 27 September 2026. Branch: `research/findings-2026-09`.

This report checks the research behind the next SETU milestones against
primary sources, maps each problem to the current code, and proposes fixes
that cost nothing to run. Values that could not be confirmed from a live
source are marked UNVERIFIED. Nothing here is legal advice.

## 1. Problem statement

People in India often need a rule, fine or scheme answer at the moment it
matters: at a traffic checkpoint, on a suspicious SMS, or at a scheme office.
The correct answer frequently depends on **where** they are and **when** the
event happened, and the official sources that settle it are scattered.

Verified evidence for this:

- The central Motor Vehicles Act sets a range for dangerous driving
  (Section 184: Rs 1,000 to 5,000 for a first offence), while Section 200
  lets each State Government notify its own compounding amounts in the
  Official Gazette (C1, C3).
- Enforcement differs below the state level. Kolkata Traffic Police lists
  earphone use while driving under Section 184 at Rs 5,000 (first) and
  Rs 10,000 (subsequent), while the central Act's text names only handheld
  communication devices (C2).
- Fraudsters copy official channels. Kerala Police warned on 26 Sep 2026 about
  fake e-challan SMS messages that install a malicious APK (C6), and PIB Fact
  Check has debunked fake scheme offers (C7).
- Commercial legal AI tools still hallucinate in roughly 17 to 33 percent of
  queries (C12), and retrieval over only the current text of a law picks the
  date-applicable version 0 percent of the time in a French tax benchmark (C13).
- Information alone does not raise scheme uptake (C8).

SETU already validates citation membership and numeric grounding. It does not
yet know jurisdiction or effective dates, check user premises, verify links,
track source changes, or help people act on an answer.

## 2. Claim verification

Grades: **VERIFIED** means confirmed from a primary source, or, for news events
such as a warning or a launch, from reputable reporting of the official
statement. **PARTLY** means part of the claim is confirmed and the rest is
corrected or open. **UNVERIFIED** means no live source could be read.
**WRONG** means a source contradicts it.

| ID | Claim (corrected wording) | Grade | Source(s) |
|---|---|---|---|
| C1 | MV Act §184 (as amended by Act 32 of 2019) includes use of handheld communications devices while driving. First offence: imprisonment 6 months to 1 year and/or fine Rs 1,000 to 5,000. **Correction:** a subsequent offence within three years carries up to 2 years and/or a fine up to Rs 10,000. | VERIFIED | Statute text on [Indian Kanoon §184](https://indiankanoon.org/doc/9295814/); [AAP Tax Law: 2019 Act §184](https://www.aaptaxlaw.com/motor-vehicles-act-2019/section-183-184-185-186-187-189-of-motor-vehicles-amendment-act-2019.html). India Code could not be reached from this environment. |
| C2 | The central Act's §184 text names handheld communication devices, not earphones for music. **Correction:** Kolkata Traffic Police's official offence list includes "no person shall use earphone while driving" under §184 at Rs 5,000 / Rs 10,000 (list updated 28.10.2024). Bengaluru Traffic Police announced enforcement against gadgets in Oct 2021 (navigation allowed). Rules of the Road Regulations 2017 were not read. | PARTLY | [Kolkata Traffic Police offences list](https://www.kolkatatrafficpolice.gov.in/offences.pdf); [Deccan Herald, Oct 2021](https://www.deccanherald.com/india/karnataka/bengaluru/headphones-while-driving-youll-now-have-to-cough-up-hefty-fine-1036768.html) |
| C3 | §200: offences may be compounded by officers and for amounts that the State Government specifies by notification in the Official Gazette (confirmed). **West Bengal:** WB Traffic Police publishes Schedule II of Notification No. 208-WT/3M-128/97 (Pt. III)(D) dated 24.01.2022. **Karnataka:** UNVERIFIED; only 2019 news of reduced fines. **Delhi:** UNVERIFIED; news of a Sep 2024 decision to compound at 50% of the challan amount, no notification found on the Delhi Transport Department notifications page. | PARTLY | [Indian Kanoon §200](https://indiankanoon.org/doc/106194272/); [WB Traffic Police offences](https://www.wbtrafficpolice.com/offences-and-penalties.php); [Deccan Herald, Karnataka 2019](https://www.deccanherald.com/india/karnataka/penalties-under-motor-vehicles-act-cut-in-karnataka-763072.html); [Deccan Herald, Delhi Sep 2024](https://www.deccanherald.com/india/delhi/delhi-govt-decides-compounding-of-traffic-offences-at-50-per-cent-of-challan-amount-3186600); [Delhi Transport notifications](https://transport.delhi.gov.in/notifications) |
| C4 | A PIB release on the 2019 amendment covers validity of documents in electronic form through DigiLocker and mParivahan. The exact Rule 139 CMVR text and the MoRTH SOP could not be opened (timeout; redirect needing approval). | PARTLY | [PIB release 195457](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=195457&reg=48&lang=2) |
| C5 | J-PAL study (Banerjee, Duflo, Firth, Keniston, Olken, Weaver; Rajasthan; 17,369 motorists; 2012) told riders the exact helmet fine. **Correction:** J-PAL reports status only; continued work was put on hold pending the MV Act amendment. No published results found. | PARTLY | [J-PAL evaluation](https://www.povertyactionlab.org/evaluation/changing-beliefs-changing-bribes-india); [J-PAL RBBB](https://www.povertyactionlab.org/evaluation/changing-beliefs-changing-bribes-rajasthan-bribes-banners-and-beliefs-project-rbbb) |
| C6 | Kerala Police warning on 26 Sep 2026 about fake e-challan SMS leading to a malicious APK; advice to use only official MVD, Parivahan or e-challan sites and report to 1930. The exact list of official e-challan domains is not yet confirmed. | PARTLY | [ThePrint (PTI), 26 Sep 2026](https://theprint.in/india/keralam-police-warn-of-malicious-apk-scam-via-fake-e-challan-sms/3053993/) |
| C7 | PIB Fact Check debunked a fake "Students Laptop Scheme 2026" (12 Jan 2026) and warned about fraudsters charging Rs 8,000 for PM-KUSUM registration (Sep 2024). | VERIFIED | [News On AIR, Jan 2026](https://www.newsonair.gov.in/govt-warns-public-against-fake-students-laptop-scheme-2026-messages); [News On AIR, Sep 2024](https://www.newsonair.gov.in/pib-fact-check-unit-warns-of-scam-fraudsters-charging-rs-8000-for-pm-kusum-yojana-registration) |
| C8 | Berg, Rajasekhar and Manjula (16 schemes, south India): agents raised awareness but not application submission or scheme receipt. | VERIFIED | [University of Bristol record](https://research-information.bris.ac.uk/en/publications/pushing-welfare-encouraging-awareness-and-uptake-of-social-benefi/) |
| C9 | Jugalbandi (2023): 10 languages, 171 of about 20,000 programmes, pipeline translates to English before the LLM. | VERIFIED | [Microsoft Source Asia](https://news.microsoft.com/source/asia/features/with-help-from-next-generation-ai-indian-villagers-gain-easier-access-to-government-services/) |
| C10 | Nyaya Setu (Ministry of Law and Justice) launched 1 Jan 2026 on WhatsApp; AI responses plus panel lawyers; focuses on access and navigation. | VERIFIED | [NewsBytes](https://www.newsbytesapp.com/news/science/government-launches-nyaya-setu-chatbot-for-legal-aid-on-whatsapp/story) |
| C11 | Samadhan Didi for CPGRAMS (DARPG) launched 30 May 2026; voice grievances in all 22 scheduled languages; built with Bhashini. | VERIFIED | [Business Standard](https://www.business-standard.com/amp/industry/news/centre-unveils-ai-enabled-chatbot-to-help-citizens-launch-grievances-online-126053001262_1.html) |
| C12 | Stanford RegLab: Lexis+ AI, Westlaw AI-Assisted Research and Ask Practical Law AI hallucinated in 17 to 33 percent of queries; causes include retrieval errors and sycophancy. | VERIFIED | [Stanford RegLab](https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/) |
| C13 | arXiv 2608.09393 (Aug 2026): static RAG over the current corpus retrieved the date-applicable version 0 percent of the time (2.7 percent accuracy); version-aware, date-conditioned retrieval reached 98.3 percent end to end (99.1 percent with oracle version selection). | VERIFIED | [arXiv 2608.09393](https://arxiv.org/html/2608.09393) |
| C14 | arXiv 2608.20220 (InsufficiencyBench): legal advice on underspecified queries. Not read: rate-limited earlier, and the abstract page needs a fetch approval. | UNVERIFIED | [arXiv 2608.20220](https://arxiv.org/abs/2608.20220) |
| C15 | Beeck Center / Digital Benefits Network: plain prompting scored 0 percent on numerical eligibility rules; templates, RAG and modular steps with human review did better. | VERIFIED | [Digital Government Hub summary](https://digitalgovernmenthub.org/publications/ai-powered-rules-as-code-experiments-with-public-benefits-policy-summary/) |
| C16 | Catala (Merigoux et al., ICFP 2021) is a language for encoding law. Production use by DGFiP and CNAF is indicated by Inria's page title, but the page itself was blocked. | PARTLY | [arXiv 2103.03198](https://arxiv.org/abs/2103.03198); [Inria](https://www.inria.fr/en/catala-software-dgfip-cnaf) |
| C17 | Farmer.Chat: over 15,000 farmers and 300,000 queries across four countries. | VERIFIED | [arXiv 2409.08916](https://arxiv.org/abs/2409.08916) |
| C18 | IndicVoices: CC BY 4.0, 22 languages, 23.7K hours (11.2K transcribed). Download requires agreeing to share contact information. | VERIFIED | [Hugging Face dataset card](https://huggingface.co/datasets/ai4bharat/IndicVoices) |
| C19 | No public benchmark was found that tests date- or state-applicable retrieval for Indian law. IL-TUR (ACL 2024) covers legal understanding tasks; AILQA (arXiv 2607.18825, Jul 2026) covers criminal-law QA and states its results do not validate answers under the currently applicable law. A negative claim cannot be fully proven. | PARTLY | [IL-TUR](https://arxiv.org/abs/2407.05399); [AILQA](https://arxiv.org/html/2607.18825) |

Totals: 11 VERIFIED, 7 PARTLY, 1 UNVERIFIED, 0 WRONG (two claims corrected: C1, C2).

## 3. Problems, current state and fixes

All fixes below run locally or on free GitHub Actions for this public
repository. None needs a paid service.

### P1. Jurisdiction and date

- **Evidence:** C1, C2, C3, C13.
- **Current state:** `documents` and `chunks` have no jurisdiction or
  effective-date columns (`db/init.sql` lines 4–23). Both retrieval legs filter
  only by language (`app/retrieval/dense.py` line 36,
  `app/retrieval/keyword.py` lines 37–38), and `retrieve()` accepts no state or
  date (`app/retrieval/pipeline.py` lines 40–46).
- **Gap and risk:** SETU can cite a real but inapplicable rule with full
  confidence. Kolkata Police and West Bengal Police publish separate lists, so
  state alone is too coarse.
- **Fix:** migration `db/migrations/0001_jurisdiction_and_effective_dates.sql`
  (added on this branch) adds `jurisdiction`, `effective_from`,
  `effective_to`, `source_hash` and `retrieved_at`. Jurisdiction codes go down
  to the enforcing authority (for example `IN-WB-KOL` for Kolkata Police).
  Next: pass `jurisdiction` and `as_of` into both retrieval legs and filter
  before ranking.
- **Acceptance test:** the temporal cases in `eval/temporal_cases.jsonl`
  (added on this branch) pass.
- **Effort:** 3–4 days. **Risk:** mapping each source to an authority needs
  manual review.

### P2. False premises and missing facts

- **Evidence:** C12 (sycophancy as a cause), C14 (topic only).
- **Current state:** `validate_numerical_grounding`
  (`app/numerical_grounding.py` line 274) checks numbers in SETU's *answer*
  against evidence. Nothing checks numbers or rules claimed in the *question*.
  The only fallback is abstention (`app/agent/graph.py` lines 103–109); there
  is no clarifying question.
- **Fix:** a deterministic premise step before generation that extracts a
  claimed amount and offence from the question and compares it with the
  offence table; ask for the place and date when they are missing.
- **Acceptance test:** zero accepted false premises and a clarifying question
  for every underspecified case in `eval/temporal_cases.jsonl`.
- **Effort:** 3 days. **Risk:** multilingual number extraction; reuse the
  existing number-word lexicon in `app/numerical_grounding.py`.

### P3. Scam links and fake scheme messages

- **Evidence:** C6, C7.
- **Current state:** no link or message checking exists. `app/security.py`
  covers API authentication only.
- **Fix:** a deterministic checker with an allow-list of official domains
  (`gov.in`, `nic.in` and named portals, confirmed from official sources
  first), flags for APK links, punycode and look-alike domains, and a curated
  list of PIB Fact Check debunks. No LLM call is needed.
- **Acceptance test:** no known scam sample is marked safe; a set of genuine
  official links passes.
- **Effort:** 3 days. **Risk:** an allow-list goes stale; freshness watch (P4)
  covers it.

### P4. Stale sources

- **Evidence:** C13.
- **Current state:** the scraper covers PIB only (`ingestion/scraper.py`
  line 37). `documents.url` is `UNIQUE` (`db/init.sql` line 9) and
  `ingestion/db_writer.py` line 47 uses `ON CONFLICT (url) DO UPDATE`, so
  re-ingesting a source overwrites the older version. History is lost, which
  makes date-applicable answers impossible.
- **Fix:** keep one row per source version. This needs a later migration that
  replaces the `UNIQUE (url)` key with `UNIQUE (url, source_hash)` together with
  a matching change to the upsert in `ingestion/db_writer.py`; changing only the
  key would break ingestion. Migration 0001 on this branch already adds the
  `source_hash` and `retrieved_at` columns it needs. Also add a scheduled GitHub
  Actions job that hashes official sources and opens an issue when one changes.
- **Acceptance test:** a changed source produces a new version row and a stale
  flag in one run.
- **Effort:** 2–3 days. **Risk:** some government sites block automated
  fetches; record them as manual-check sources.

### P5. Eligibility quarantine

- **Evidence:** C15, C16.
- **Current state:** the route guard (`app/agent/graph.py` lines 85–101) and
  `check_eligibility_node` (lines 155–157) block eligibility decisions; the
  seeded criteria are marked illustrative (`ingestion/seed_eligibility.py`
  line 7).
- **Fix:** encode each scheme's rules as small, tested Python functions with a
  source clause per rule; the LLM only extracts facts. Leave quarantine only
  after a human review.
- **Acceptance test:** one unit test per rule clause, plus reviewer sign-off.
- **Effort:** 5 days for 3 schemes. **Risk:** scheme rules change; version them
  with effective dates like P1.

### P6. Answers stop at information

- **Evidence:** C8.
- **Current state:** `QueryResponse` (`app/schemas.py` lines 34–60) carries
  answer sections and citations only.
- **Fix:** optional `next_steps` (document checklist, official where-to-apply
  link, hand-off to myScheme, CPGRAMS or Nyaya Setu). Do not rebuild grievance
  filing or legal consultation.
- **Acceptance test:** schema tests; every link in `next_steps` is on the
  official allow-list.
- **Effort:** 2 days.

### P7. Offline use at a checkpoint

- **Evidence:** the roadside scenario; network coverage is not guaranteed.
- **Current state:** the frontend has no offline support or service worker;
  demo fixtures only.
- **Fix:** ship the offence table as a static, hashed JSON bundle with the
  frontend and render Roadside Mode from it without any API call.
- **Acceptance test:** the Roadside view renders with the network disabled in
  Playwright.
- **Effort:** 3 days. **Safety:** copy must never coach confrontation; the
  script is to pay only through an official e-challan or receipt and contest
  it later through official channels.

## 4. Open items

- **C14:** approve a fetch of arXiv 2608.20220 or paste its abstract.
- **C3 (Karnataka, Delhi):** the gazette notifications were not found. Official
  PDFs or photos of the current compounding notifications would let the table
  be filled.
- **C3 (West Bengal):** the table uses the WB Traffic Police and Kolkata
  Traffic Police published lists. The gazette PDF of Notification
  208-WT/3M-128/97 (Pt. III)(D) was not read.
- **C4:** the Rule 139 CMVR text and MoRTH SOP need a manual read.
- **C6:** confirm the official e-challan domains from Parivahan itself.
- **Prior art:** a public GitHub project, `mudit108-code/Drive-Legal`, has an
  open issue about offline citizen rights and DigiLocker validity. It was
  seen in search results only and not reviewed.
- **Naming:** "Nyaya Setu" (C10) overlaps with the SETU name.

## 5. Roadmap

Phases run one after another. A phase starts only when the previous gate
passes. Zero spend throughout: local runs, free tiers and GitHub Actions on
this public repository only.

| Phase | Weeks | Work | Exit gate |
|---|---|---|---|
| 0. Verify | 1 | This report, baseline checks | Every claim graded with a source; baseline green |
| 1. Jurisdiction and date data | 2–3 | Migration, offence table, date-conditioned retrieval | Temporal cases pass; no fine without a source |
| 2. Roadside Mode | 4–5 | Offline bundle and view | Works offline; copy review passed |
| 3. False-premise guard | 6–7 | Premise check, clarifying questions | Zero false premises accepted |
| 4. Scam Shield and freshness watch | 8–9 | Link checker, scheduled source hashing | No scam marked safe; changes flagged in one run |
| 5. Answer to action | 10–12 | Rules-as-code for 3 schemes, `next_steps` | Rule tests and human sign-off |

## 6. Baseline results (27 Sep 2026)

| Check | Result |
|---|---|
| `python -m compileall -q app ingestion eval tests scripts` | Pass |
| `python -m unittest discover -s tests` | 114 tests, all pass (README says 112) |
| `python -m eval.offline_evaluation` | Pass; report identical to `docs/offline-evaluation-report.md` |
| `python scripts/ci_static_checks.py` | Pass |
| `python -m pip check` | No broken requirements |
| Frontend `npm run test:run` | 28 passed, 1 skipped by design (README says 25) |
| Frontend `npm run typecheck`, `npm run lint` | Pass |
