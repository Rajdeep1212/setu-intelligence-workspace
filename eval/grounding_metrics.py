"""Small, deterministic grounding evaluator for human support judgments."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from app.grounding import select_citations


CLAIM_BOUNDARY = re.compile(r"(?<=[.!?।॥])\s+|[\r\n]+")


def extract_claims(answer: str) -> list[str]:
    """Split multilingual prose into review units without judging support."""
    return [
        part.strip(" \t-*•")
        for part in CLAIM_BOUNDARY.split(answer)
        if part.strip()
    ]


def _fingerprint(citation: dict) -> str:
    text = str(citation.get("content") or citation.get("snippet") or "")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split()) or f"id:{citation.get('chunk_id')}"


def score_case(case: dict, prediction: dict) -> dict:
    citations = prediction.get("citations", [])
    cited_ids = [str(citation["chunk_id"]) for citation in citations]
    unique_cited_ids = set(cited_ids)
    judgments = prediction.get("claim_judgments")
    if judgments is None:
        judgments = [
            {"claim": claim, "supporting_chunk_ids": []}
            for claim in extract_claims(prediction.get("answer", ""))
        ]

    supported_ids = {
        str(chunk_id)
        for judgment in judgments
        for chunk_id in judgment.get("supporting_chunk_ids", [])
    }
    supported_claims = sum(
        bool(
            unique_cited_ids.intersection(
                map(str, judgment.get("supporting_chunk_ids", []))
            )
        )
        for judgment in judgments
    )

    seen_ids: set[str] = set()
    seen_evidence: set[str] = set()
    redundant = 0
    for citation in citations:
        chunk_id = str(citation["chunk_id"])
        evidence = _fingerprint(citation)
        if chunk_id in seen_ids or evidence in seen_evidence:
            redundant += 1
        seen_ids.add(chunk_id)
        seen_evidence.add(evidence)

    correct_abstention = bool(
        not case["answerable"]
        and prediction.get("abstained")
        and not judgments
        and not citations
    )
    precision_numerator = len(unique_cited_ids.intersection(supported_ids))
    precision_denominator = len(unique_cited_ids)
    precision = (
        precision_numerator / precision_denominator
        if precision_denominator
        else float(correct_abstention)
    )
    claim_count = len(judgments)
    coverage = supported_claims / claim_count if claim_count else 1.0

    return {
        "language": case["language"],
        "unanswerable": float(not case["answerable"]),
        "citation_precision": precision,
        "support_coverage": coverage,
        "unsupported_claim_rate": 1.0 - coverage,
        "citation_redundancy": redundant / len(citations) if citations else 0.0,
        "citation_count": len(citations),
        "correct_abstention": float(correct_abstention),
    }


def summarize(dataset: list[dict], predictions: list[dict]) -> dict:
    by_id = {prediction["id"]: prediction for prediction in predictions}
    scores = [score_case(case, by_id[case["id"]]) for case in dataset]

    def aggregate(items: list[dict]) -> dict:
        metric_names = (
            "citation_precision",
            "support_coverage",
            "unsupported_claim_rate",
            "citation_redundancy",
            "citation_count",
        )
        result = {
            name: round(sum(item[name] for item in items) / len(items), 4)
            for name in metric_names
        }
        unanswerable = sum(item["unanswerable"] for item in items)
        result["grounded_abstention_rate"] = (
            round(
                sum(item["correct_abstention"] for item in items) / unanswerable,
                4,
            )
            if unanswerable
            else 0.0
        )
        return result

    languages: dict[str, list[dict]] = defaultdict(list)
    for score in scores:
        languages[score["language"]].append(score)

    return {
        "queries": len(dataset),
        "answerable": sum(bool(case["answerable"]) for case in dataset),
        "unanswerable": sum(not case["answerable"] for case in dataset),
        "overall": aggregate(scores),
        "by_language": {
            language: aggregate(items) for language, items in sorted(languages.items())
        },
    }


def structural_replay(dataset: list[dict]) -> tuple[list[dict], list[dict]]:
    """Replay legacy return-all versus validated selection; no model calls."""
    pools: dict[str, list[str]] = defaultdict(list)
    for case in dataset:
        pools[case["language"]].extend(case["supporting_chunk_ids"][:1])

    before: list[dict] = []
    after: list[dict] = []
    for case in dataset:
        support = list(map(str, case["supporting_chunk_ids"]))
        candidates: list[str] = []
        for chunk_id in support[:1] + pools[case["language"]]:
            if chunk_id not in candidates:
                candidates.append(chunk_id)
            if len(candidates) == 3:
                break
        chunks = [
            {
                "id": chunk_id,
                "document_id": f"doc-{chunk_id}",
                "content": f"evidence-{chunk_id}",
            }
            for chunk_id in candidates
        ]
        judgments = [
            {"claim": fact, "supporting_chunk_ids": support}
            for fact in case["expected_facts"]
        ]
        before.append(
            {
                "id": case["id"],
                "abstained": not case["answerable"],
                "citations": [
                    {"chunk_id": chunk["id"], "content": chunk["content"]}
                    for chunk in chunks
                ],
                "claim_judgments": judgments,
            }
        )
        requested = support + ["fabricated-not-retrieved"]
        selected = select_citations(chunks, requested)
        after.append(
            {
                "id": case["id"],
                "abstained": not bool(selected),
                "citations": [
                    {"chunk_id": item["chunk_id"], "content": item["snippet"]}
                    for item in selected
                ],
                "claim_judgments": judgments,
            }
        )
    return before, after


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).with_name("grounding_set.jsonl"),
    )
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args()

    dataset = load_jsonl(args.dataset)
    if args.predictions:
        print(json.dumps(summarize(dataset, load_jsonl(args.predictions)), indent=2))
        return

    before, after = structural_replay(dataset)
    print("Deterministic structural replay (not live model generation)")
    report = {
        "before": summarize(dataset, before),
        "after": summarize(dataset, after),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
