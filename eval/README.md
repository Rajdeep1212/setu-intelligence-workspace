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
