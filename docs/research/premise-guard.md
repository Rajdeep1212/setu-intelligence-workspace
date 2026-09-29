# False-premise guard: design note and results

Phase 3 of the SETU roadmap (docs/FINDINGS.md, problem P2). Date: 28 Sep 2026.

## Question

When someone asks "Police say the helmet fine is ₹5,000. Is that right?",
does SETU check the claim against the official notification, or does it
accept it? And when the question leaves out the one fact the answer depends
on, the state, does SETU ask instead of guessing?

Commercial legal AI tools hallucinated in 17–33% of queries, with sycophancy
towards false premises named as one cause (C12). Retrieval over the current
text of a law picked the date-applicable version 0% of the time in a French
tax benchmark (C13). So this guard is deterministic, and it respects dates.

## Design

| Part | File | Role |
|---|---|---|
| Checker | `app/agent/premise.py` | Reads the question in English, Hindi, Bengali or Hinglish: offence, place, first or repeat offence, claimed amount, year. Compares the claim with VERIFIED amounts in `data/traffic_offences`. No model call. |
| Answers | `app/agent/premise_answer.py` | Fixed templates in English, Hindi and Bengali, filled only with table values. Calm guidance; "Not legal advice". |
| Agent | `app/agent/graph.py` | A `premise_gate` node runs before routing. Traffic-fine questions are answered and end there; all other questions pass through unchanged. |
| API | `app/schemas.py`, `frontend/src/lib/contracts.ts` | New `response_status` values `needs_clarification` and `rule_lookup`, route `traffic_rules`, and a structured `premise_check`. The workspace shows these with their official source. |

### Rules

- **Triggering is conservative:** a question needs both an offence word and a
  fine or enforcement word ("fine", "challan", "officer", जुर्माना, पकड़े,
  জরিমানা, ধরা). "Pay" is excluded on purpose, so "pay my insurance premium of
  ₹4,000" is never treated as a fine claim.
- **Amounts are read only when tied to money:** a ₹ or rupee marker, a
  multiplier (thousand, lakh, हज़ार, হাজার, "10k"), or a number directly
  after a fine word ("challan 3000 hai kya"). Years, counts ("three people")
  and section numbers are ignored. Devanagari and Bengali digits are
  normalised.
- **A missing state gets a question, never a guess.** A named state SETU does
  not cover (Mumbai, Chennai …) gets "SETU covers West Bengal, Karnataka and
  Delhi", not "which state?".
- **Dates are respected.** A request `as_of` date, or a year in the question,
  is checked against the notification's effective date. West Bengal's
  notification took effect on 24 Jan 2022, so "helmet fine in Kolkata in 2020"
  gets `not_in_force`, never today's amount. This was found while testing:
  the Phase 1 test "Helmet fine in 2019?" would otherwise have been answered
  with a 2022 amount.
- **Never confirmed or contradicted:** red-light jumping (legal review),
  earphones (not named in s.184; C2), and UNVERIFIED rows (all of Delhi).
- **Two offences in one question** get "please ask about one offence at a
  time".

## Evaluation

| Set | Cases | Languages | Result |
|---|---|---|---|
| Temporal suite, missing-facts and false-premise cases | 9 | en 3, hi 3, bn 3 | 9 of 9 pass; the whole suite is now **15 of 15** (was 6 pass, 9 xfail) |
| Development set (`eval/premise_cases.jsonl`) | 31 | en 18, bn 6, hi 5, Hinglish 2 | 31 of 31 |
| Held-out set (`eval/premise_holdout.jsonl`), written after freezing the code | 12 | en 7, bn 2, hi 2, Hinglish 1 | **10 of 12 before the fix**; 12 of 12 after |

Safety measures across both sets:

| Measure | Result |
|---|---|
| False premises accepted (a contradicted claim reported as matching) | 0 |
| Over-asking (a clarifying question when the place was given) | 0 of 31 complete questions |
| False triggers (a non-traffic question treated as a fine question) | 0 of 8 |
| Model calls for traffic-fine questions | 0 (previously at least 2: route and answer) |

### What the held-out set found

Both held-out failures had the same cause: a claim made without any fine
word, such as "The officer says I must pay INR 4,000 …" or "पकड़े जाने पर
दस हज़ार रुपये लगेंगे?" ("if caught, will it cost ten thousand?"). The failure
was safe: the guard stayed silent and the question went to normal retrieval,
with no wrong verdict. The fix added enforcement-context words (officer,
caught, पकड़, लगेंगे, ধরা) and new traps for "pay" and "fee" phrasing. After
the fix the held-out set is no longer truly held out, so the honest
generalisation estimate is the pre-fix 10 of 12 (83%).

## Limitations

- The lexicons are hand-built. They cover common phrasings, not every
  dialect, transliteration or spelling. Code-mixed Hindi–English in
  Devanagari with English offence words is only partly covered.
- Only one claimed amount is checked. A question with two amounts uses the
  first.
- Vehicle class is not asked for. When a state sets different amounts by
  vehicle, a claim matching any class counts as matching, and the answer
  lists every class.
- Evaluation sets are small (43 cases) and written by the same team as the
  code. They show the rules work; they do not measure real-world coverage.
