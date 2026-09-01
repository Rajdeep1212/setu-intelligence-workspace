# Citation and claim-linking design

## Runtime contract

The retrieval route labels each reranked passage with its stored chunk ID. The
structured provider response contains answer text, answer-wide citation IDs for
backward compatibility, and optional claim-specific sections. A section has:

```json
{"text": "One answer claim.", "citation_ids": ["retrieved-chunk-id"]}
```

The API treats provider output as untrusted. For each response it:

1. rejects an unknown or fabricated claim citation ID by abstaining;
2. rejects duplicate IDs inside the typed claim structure;
3. accepts only IDs from the retrieved result set;
4. removes repeated IDs and exact normalized duplicate evidence;
5. emits citations in stable retrieval order; and
6. returns typed answer sections whose IDs survived validation.

Older provider responses may omit sections. In that compatibility path the
answer and its validated answer-wide citation IDs become one section. This
compatibility behavior is locally tested; the expanded provider schema still
requires a future controlled live-provider validation.

The browser renders the returned mapping. It does not infer relationships by
position or lexical overlap. A section with no citation IDs receives no
evidence-linked badge. Internal IDs remain in the typed transport while source
title and publisher are prioritized in the interface.

## Exact trust vocabulary

- **Retrieved citation:** the citation ID belongs to the retrieved result set.
- **Citation validated:** membership and deterministic de-duplication passed.
- **Evidence linked:** a returned answer section carries one or more validated
  retrieved citation IDs.
- **Claim support reviewed:** a separate human or semantic evaluation confirmed
  the relationship.

Membership is not semantic entailment. The runtime does not call a citation a
“grounded fact,” “fact verified,” or “grounding passed.” Model-reported
confidence is uncalibrated and remains labeled engineering metadata.

## Eligibility boundary

Eligibility-table records are excluded from this evidence contract because the
current rows are illustrative and unverified. The frontend workflow makes no
determination and sends no profile. A personal backend eligibility request
returns `eligibility_unverified` without criteria lookup or answer generation.
Future eligibility activation requires reviewed, versioned rules with effective
dates and official-source provenance.

## Evaluation contract

`grounding_set.jsonl` currently contains twelve answerable cases and one
unanswerable control per language, for five cases each in English, Hindi, and
Bengali. Human claim-to-chunk judgments support these metrics:

- citation precision;
- claim support coverage;
- unsupported-claim rate;
- citation redundancy;
- citation count; and
- correct abstention.

The default evaluator is a deterministic structural replay, not live model
generation or semantic entailment. The 15 cases are regression fixtures rather
than statistically credible accuracy evidence.

## Remaining limitations

- Provider compatibility for the expanded optional claim schema has not been
  revalidated with a live call.
- Exact-text de-duplication does not catch paraphrased duplicate evidence.
- Claim support still needs reviewed judgments; retrieval membership alone is
  insufficient.
- The response keeps answer-wide citations for backward compatibility.
- No provider or cloud call occurred while this contract was implemented.
