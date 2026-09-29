"""Adversarial evaluation for the deterministic premise checker (Phase 3).

eval/premise_cases.jsonl holds hand-written questions in English, Hindi,
Bengali and Hinglish. Each case states what app/agent/premise.py must extract
(fine question or not, place, offence, first or repeat offence, claimed
amount), which facts it must ask for, and the verdict against the verified
offence tables. The run is offline: no provider, database, network or model.

    python -m eval.premise_evaluation            # prints a JSON report
    python -m eval.premise_evaluation --json-out report.json

It exits non-zero on any mismatch, on any accepted false premise, and when a
non-traffic question triggers the checker.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.agent.premise import SUPPORTED_JURISDICTIONS, check_premise, extract_facts, load_table, missing_facts

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "premise_cases.jsonl"


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _actual(case: dict[str, Any]) -> dict[str, Any]:
    facts = extract_facts(case["query"])
    actual: dict[str, Any] = {
        "fine_question": facts.is_fine_question,
        "jurisdiction": facts.jurisdiction,
        "place_supported": facts.place_supported,
        "offence": facts.offence_id,
        "occurrence": facts.occurrence,
        "claimed": facts.claimed_inr[0] if facts.claimed_inr else None,
        "missing": missing_facts(case["query"]),
    }
    if facts.is_fine_question and facts.jurisdiction in SUPPORTED_JURISDICTIONS:
        actual["verdict"] = check_premise(case["query"], load_table(facts.jurisdiction), facts)["verdict"]
    return actual


def evaluate() -> tuple[dict[str, Any], bool]:
    cases = load_cases()
    results = []
    for case in cases:
        actual = _actual(case)
        mismatches = {
            key: {"expected": value, "actual": actual.get(key)}
            for key, value in case["expected"].items()
            if actual.get(key) != value
        }
        results.append({"id": case["id"], "language": case["language"], "passed": not mismatches, "mismatches": mismatches, "actual": actual})

    by_language: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        by_language[result["language"]]["passed" if result["passed"] else "failed"] += 1

    accepted_false_premises = [
        result["id"]
        for case, result in zip(cases, results)
        if case["expected"].get("verdict") == "contradicted" and result["actual"].get("verdict") == "supported"
    ]
    complete = [
        result for case, result in zip(cases, results)
        if case["expected"].get("fine_question") and case["expected"].get("missing") == []
    ]
    non_traffic = [result for case, result in zip(cases, results) if case["expected"].get("fine_question") is False]
    over_asked = [result["id"] for result in complete if result["actual"]["missing"]]
    false_triggers = [result["id"] for result in non_traffic if result["actual"]["fine_question"]]

    report = {
        "schema": "setu.premise-evaluation-report/v1",
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "by_language": {language: dict(counts) for language, counts in sorted(by_language.items())},
        "accepted_false_premises": accepted_false_premises,
        "over_ask": {"complete_questions": len(complete), "asked_anyway": over_asked},
        "false_triggers": {"non_traffic_questions": len(non_traffic), "triggered": false_triggers},
        "failures": [result for result in results if not result["passed"]],
        "activity_accounting": {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
    }
    success = not report["failures"] and not accepted_false_premises and not false_triggers
    return report, success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report, success = evaluate()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
