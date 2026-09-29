"""Evaluation for Scam Shield (app/agent/scam_shield.py), Phase 4.

eval/scam_cases.jsonl (development) and eval/scam_holdout.jsonl (written after
the code was frozen) hold pasted messages in English, Hindi and Bengali:
known scam patterns from official warnings, genuine official messages,
neutral links, and questions that must not be screened. Offline: no network,
model or database.

    python -m eval.scam_evaluation

It fails on any mismatch, any missed scam (a scam reported as an official
link or as having no warning signs), and any genuine official message
reported as a likely scam.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.agent.scam_shield import check_message, should_check

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "scam_cases.jsonl"


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or CASES_PATH
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(path: Path | None = None) -> tuple[dict[str, Any], bool]:
    cases = load_cases(path)
    results = []
    for case in cases:
        expected = case["expected"]
        triggered = should_check(case["text"])
        report = check_message(case["text"])
        mismatches = {}
        if triggered != expected["trigger"]:
            mismatches["trigger"] = {"expected": expected["trigger"], "actual": triggered}
        if "verdict" in expected and report.verdict != expected["verdict"]:
            mismatches["verdict"] = {"expected": expected["verdict"], "actual": report.verdict}
        missing = [code for code in expected.get("signals_include", []) if code not in report.signals]
        if missing:
            mismatches["signals_missing"] = missing
        results.append({"id": case["id"], "language": case["language"], "label": case["label"], "passed": not mismatches,
                        "mismatches": mismatches, "verdict": report.verdict, "signals": report.signals})

    missed_scams = [r["id"] for r in results if r["label"] == "scam" and r["verdict"] in ("official_link", "no_warning_signs")]
    false_alarms = [r["id"] for r in results if r["label"] == "genuine" and r["verdict"] == "likely_scam"]
    by_language: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        by_language[result["language"]]["passed" if result["passed"] else "failed"] += 1
    report = {
        "schema": "setu.scam-evaluation-report/v1",
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "by_language": {language: dict(counts) for language, counts in sorted(by_language.items())},
        "scams": sum(1 for result in results if result["label"] == "scam"),
        "genuine": sum(1 for result in results if result["label"] == "genuine"),
        "missed_scams": missed_scams,
        "false_alarms_on_genuine": false_alarms,
        "failures": [result for result in results if not result["passed"]],
        "activity_accounting": {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
    }
    return report, not report["failures"] and not missed_scams and not false_alarms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report, success = evaluate(args.cases)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
