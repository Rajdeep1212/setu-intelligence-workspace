# SETU evaluation fixtures

SETU keeps three deliberately different evaluation surfaces. Their results
must not be combined into one accuracy claim:

- `eval_set.jsonl` has 15 corpus-linked retrieval labels (5 per language).
- `grounding_set.jsonl` has 15 reviewed answerability/support labels (5 per
  language; 12 answerable and 3 unanswerable).
- `offline_cases.jsonl` is the versioned 60-case deterministic fixture-replay
  gate described by `offline_manifest.json`.

The 60 headline cases are unique: 15 retrieval-label replays, 15 grounding
contract replays, 15 numerical cases, 9 deterministic routing cases, and 6
adversarial configured-behavior cases. English, Hindi, and Bengali each have
20 cases. Only the retrieval cases are corpus-linked; the other 45 are mock or
synthetic. See the generated [offline evaluation report](../docs/offline-evaluation-report.md).

Run the provider-free, network-free, database-free CI evaluation from the
repository root:

```bash
python -m eval.offline_evaluation
```

Use `--json-out` and `--markdown-out` for machine- and human-readable files.
The command exits nonzero if the manifest, fingerprint, case pass rate, or a
required fixture-replay threshold differs. It performs no live retrieval and
does not measure provider answer quality or semantic entailment.

## Temporal and false-premise cases

`temporal_cases.jsonl` holds 15 cases (5 each in English, Hindi and Bengali)
for behaviour SETU is adding phase by phase: retrieval filtered by state and
as-of date, asking for a missing state, and checking a claimed fine against
`data/traffic_offences/`. They are kept out of the 60-case gate, which
requires every case to pass.

| Category | Cases | Status |
|---|---|---|
| `temporal_retrieval` | 6 | `pass` since Phase 1 (state and date filters in both retrieval legs) |
| `missing_facts` | 3 | `pass` since Phase 3 (`app/agent/premise.py` asks for the state) |
| `false_premise` | 6 | `pass` since Phase 3 (claimed amounts checked against verified tables) |

```bash
python -m eval.temporal_evaluation
```

The run is strict in both directions. It exits zero only when every `pass`
case passes and every `xfail` case still fails. It exits nonzero if a `pass`
case regresses, if an `xfail` case starts passing before its `expected_status`
is changed, or if a false-premise case stops matching a verified table row.
Expected result today: 15 pass, 0 unexpected. See
[FINDINGS](../docs/FINDINGS.md) (P1 and P2).

## Premise checker cases

`premise_cases.jsonl` (development set) and `premise_holdout.jsonl` (written
after the code was frozen) test `app/agent/premise.py` in English, Hindi,
Bengali and Hinglish: offence, place, first or repeat offence, claimed
amount, the facts to ask for, and the verdict against the verified tables.

```bash
python -m eval.premise_evaluation
```

It fails on any mismatch, any accepted false premise, and any non-traffic
question that triggers the checker. It also reports the over-ask rate on
complete questions. Results and the held-out history are in
[research/premise-guard.md](../docs/research/premise-guard.md).

## Corpus-linked retrieval labels

`eval_set.jsonl` stores one short authored query and its reviewed relevant
chunk identifiers per JSON line:

```json
{"query": "who is eligible for PM Kisan", "language": "en", "relevant_chunk_ids": ["<uuid>"]}
```

The legacy live-retrieval command is:

```bash
python -m eval.precision_at_k
```

It requires a compatible populated local database and is excluded from CI.
Never point it at the protected cloud database for portfolio checks.

## Citation grounding

`grounding_set.jsonl` contains five reviewed cases for each supported language.
The standalone structural contract replay remains available without a model or
provider call:

```bash
python -m eval.grounding_metrics
```

For separately reviewed system outputs, pass `--predictions path.jsonl`. Each
prediction must contain its case `id`, citations with `chunk_id`, and human
`claim_judgments`. If judgments are omitted, the Unicode-safe splitter exposes
claims but marks them unsupported instead of treating lexical overlap as
semantic proof.

## Everyday-use evaluation (M2.2)

`everyday_cases.jsonl` holds 12 held-out scheme questions (4 English, 4 Hindi,
4 Bengali), written before any tuning. Each states the expected response
status, the sections a person needs, and the evidence. The run replays saved
retrieval results (`everyday_retrieval.json`) through the agent graph, with no
provider, database, network or model:

```bash
python -m eval.everyday_evaluation --markdown-out docs/everyday-evaluation-report.md
```

It scores status, evidence and sections separately and does not measure answer
wording. Recording the retrieval results is a laptop step: it reads the local
staging database and needs both local models.

```bash
python -m eval.everyday_evaluation --capture
```

Status on 9 Oct 2026: **not recorded yet.** Two attempts on the laptop ran out
of memory (7.7 GB machine; the two models total 4.23 GiB), so there is no
baseline and the two tests that need the file are skipped. Do not tune
anything these cases cover until the baseline is recorded and committed.

## Interpretation boundary

The deterministic 60-case gate covers citation membership, duplicate and
unknown IDs, expected support labels, abstention, a small reviewed multilingual
numeric lexicon, route quarantine, malformed schemas, bounded input, prompt
hierarchy, sanitized errors, and fixture secret patterns. Existing backend and
frontend suites separately cover wrong-language output, redirect and upstream
origin rejection, duplicate-submission prevention, retry prevention, and
client-visible contract validation.

Code-mixed/transliterated language behavior remains a labeled limitation.
Prompt-injection checks prove only that retrieved text stays in the user
context beneath the configured evidence-only system instruction; they do not
claim universal resistance.
