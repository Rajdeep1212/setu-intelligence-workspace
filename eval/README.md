# Retrieval eval set — Week 2

`eval_set.jsonl` holds hand-labeled query → relevant-chunk pairs, one JSON
object per line:

```json
{"query": "who is eligible for PM Kisan", "language": "en", "relevant_chunk_ids": ["<uuid>", "<uuid>"]}
```

## How to build it
1. Run Week 1 ingestion so you have real chunks in Postgres.
2. Pick ~20-30 realistic questions a user might ask, spread evenly across
   `en` / `hi` / `bn` (roughly 7-10 each, not all English).
3. For each question, look at the `chunks` table and find the 1-3 chunks
   that genuinely answer it:
   ```sql
   SELECT id, language, left(content, 120) FROM chunks WHERE content ILIKE '%pm kisan%';
   ```
4. Add a line to `eval_set.jsonl` with the question and those chunk ids.

Keep this file in version control — it's your regression baseline for Week 5
(RAGAS + the GitHub Actions eval gate both reuse it), so it should grow
rather than get thrown away once Week 2 is "done".

## Running it
```bash
# from the repo root, with the API's venv/deps available (same deps /query uses)
python -m eval.precision_at_k
```

Prints overall precision@5 and a per-language breakdown — read
`docs/ROADMAP.md` (Week 5) for why the per-language breakdown matters more
than the aggregate number.

## Citation grounding

`grounding_set.jsonl` is a compact human-readable grounding fixture with five
queries each for Bengali, Hindi, and English. Run the deterministic citation
contract replay (no model or provider call) with:

```bash
python -m eval.grounding_metrics
```

For reviewed system outputs, pass `--predictions path.jsonl`. Each prediction
must contain its case `id`, citations with `chunk_id`, and `claim_judgments`
whose `supporting_chunk_ids` were assigned by a human reviewer. If judgments
are omitted, the Unicode-safe local splitter exposes claims but deliberately
marks them unsupported rather than pretending lexical overlap proves support.
