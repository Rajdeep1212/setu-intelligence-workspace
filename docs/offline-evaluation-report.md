# Offline evaluation report

Evaluation version: `4C-2.1`

Mode: `deterministic_fixture_replay`
Result: **60 / 60 cases passed**

This is deterministic fixture replay. It does not claim live retrieval accuracy, provider answer quality, or semantic entailment.

## Coverage

| Dimension | Cases | Passed |
|---|---:|---:|
| retrieval | 15 | 15 |
| grounding | 15 | 15 |
| numeric | 15 | 15 |
| routing | 9 | 9 |
| adversarial | 6 | 6 |

| Language | Cases | Passed |
|---|---:|---:|
| en | 20 | 20 |
| hi | 20 | 20 |
| bn | 20 | 20 |

## Metrics

| Metric | Value |
|---|---:|
| Fixture P@1 | 0.6000 |
| Fixture P@3 | 0.6444 |
| Fixture P@5 | 0.6267 |
| Fixture Recall@5 | 0.6730 |
| Fixture MRR@5 | 0.8000 |
| Citation-ID precision | 0.7500 |
| Expected support coverage (answered cases) | 1.0000 |
| Unsupported-claim rate | 0.0000 |
| Abstention correctness | 1.0000 |
| Numeric validation accuracy | 1.0000 |
| Eligibility guard accuracy | 1.0000 |

Citation-ID precision includes malformed-ID fixtures. Expected support coverage is calculated only for fixtures expected to produce an answered result; malformed and insufficient-evidence fixtures are scored through abstention correctness.

Corpus label fingerprint: `53a68285ec499ed2df83debfc48df24448ebe53da2e3fd4b03d47c0004652a02`

## Mode boundaries

- Fixture replay: **run**.
- Live local retrieval: **not run**; separately authorized local release check.
- Provider-routed quality: **not run**; future explicitly budgeted provider check.
- Semantic entailment review: **not run**; requires separate human or semantic judgments.

## Interpretation limits

- The retrieval ranking is a deterministic fixture replay, not a live retriever measurement.
- Citation membership does not prove semantic entailment.
- Route checks measure the deterministic quarantine guard, not provider route accuracy.
- Number-word support is a small reviewed lexicon, not general semantic number parsing.
- Code-mixed and transliterated language handling remains a labeled limitation.
- No provider, database, model download, or cloud service is used by this evaluation.

Activity accounting: **0 provider calls, 0 database requests, 0 external requests, and 0 model downloads.**
