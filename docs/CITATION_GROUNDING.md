# Citation grounding design

## Current flow and weaknesses

The retrieval route sends the text of five reranked chunks to the answer model
without chunk identifiers. `GeneratedAnswer` contains only answer text and a
self-reported confidence. After generation, the API exposes every retrieved
chunk as a response-level citation, whether or not it supports the answer.

Consequences:

- the model cannot identify which evidence it used;
- citation precision is uncontrolled and redundant evidence can be returned;
- citation objects identify the document but not the supporting chunk;
- fabricated or unsupported answer claims are constrained only by the prompt;
- citation order happens to follow retrieval order, but there is no explicit
  selection or validation contract.

Chunk UUIDs and metadata are Unicode-safe strings, so the same contract works
for Bengali, Hindi, and English without translating source evidence.

## Small production change

Each retrieved passage is labelled with its existing chunk UUID in the answer
prompt. Structured output now asks for only the UUIDs that materially support
the answer and an explicit abstention flag. The API then:

1. accepts IDs only from the retrieved result set;
2. removes repeated IDs and exact normalized duplicate evidence;
3. emits selected citations in stable retrieval order;
4. includes both `chunk_id` and `document_id`; and
5. returns a localized insufficient-evidence answer with no citations when a
   retrieval answer has no valid supporting citation.

There is deliberately no fallback to all retrieved chunks. Eligibility-table
answers remain outside the chunk-citation contract because they use structured
database criteria rather than retrieved document chunks.

## Evaluation contract

`grounding_set.jsonl` draws twelve answerable queries from the existing
multilingual retrieval set and adds one unanswerable control per language,
keeping five cases per language. Each record states whether it is answerable,
the expected factual content, and known supporting chunk IDs. Support remains
a human annotation: the local evaluator does not claim to infer semantic
entailment.

The deterministic evaluator splits answers on Unicode sentence terminators for
reviewable claim units and scores explicitly supplied claim-to-chunk judgments:

- **Citation precision:** unique cited chunks supporting at least one judged
  claim / unique cited chunks. With no citations it is 1 only for a correct
  abstention, otherwise 0.
- **Support coverage (citation recall):** evidence-requiring claims with at
  least one cited supporting chunk / evidence-requiring claims.
- **Unsupported claim rate:** one minus support coverage.
- **Citation redundancy:** citations duplicating an earlier chunk ID or
  normalized evidence text / all returned citations.
- **Citation count:** raw returned citation count per answer.
- **Grounded abstention:** an unanswerable case marked abstained with no factual
  claims and no citations.

Aggregate scores are macro averages over cases; language breakdowns use the
same definitions. Empty-denominator behavior is explicit in code so results are
repeatable.

## Limitations

Sentence splitting is claim decomposition, not semantic claim extraction.
Support judgments must be supplied by a reviewer (or by a separately isolated,
optional judge) and should not be replaced with fragile word overlap. Citations
remain response-level rather than attached inline to individual answer spans.
The 15 examples are a regression fixture, not a statistically rigorous quality
estimate. Exact-text deduplication catches duplicate evidence but not every
paraphrased redundant passage.
