"""Expected-failure suite for date-, state- and premise-aware answering.

These 15 cases (5 each in English, Hindi and Bengali) describe behaviour SETU
does not have yet. Every case is a strict expected failure: the run succeeds
while each capability probe fails, and fails if a probe starts passing before
its case is re-marked. It is deliberately separate from the frozen 60-case
gate in eval/offline_evaluation.py, which requires a 100% pass rate.

Probes are offline. The retrieval probe passes a recording stand-in for the
database session, so no SQL reaches a database.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.retrieval.dense import dense_search
from app.retrieval.keyword import keyword_search


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "temporal_cases.jsonl"
OFFENCE_DIR = ROOT / "data" / "traffic_offences"
LANGUAGES = ("en", "hi", "bn")
CATEGORIES = ("temporal_retrieval", "missing_facts", "false_premise")
EXPECTED_CASE_COUNT = 15


class _RecordingSession:
    """Stands in for AsyncSession and records statements instead of executing them."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), dict(params or {})))
        return []


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _offence_table(jurisdiction: str) -> dict[str, Any]:
    return json.loads((OFFENCE_DIR / f"{jurisdiction.removeprefix('IN-')}.json").read_text(encoding="utf-8"))


def _manifest_errors(cases: list[dict[str, Any]]) -> list[str]:
    errors = []
    if len(cases) != EXPECTED_CASE_COUNT:
        errors.append(f"expected {EXPECTED_CASE_COUNT} cases, found {len(cases)}")
    if len({case["id"] for case in cases}) != len(cases):
        errors.append("case IDs are not unique")
    if Counter(case["language"] for case in cases) != Counter({language: 5 for language in LANGUAGES}):
        errors.append("cases are not 5 per language")
    if {case["category"] for case in cases} - set(CATEGORIES):
        errors.append("unsupported category present")
    return errors


def _fixture_errors(case: dict[str, Any]) -> list[str]:
    """Check that each case's expectation is itself grounded in tracked data."""
    expected = case["expected"]
    if case["category"] == "temporal_retrieval":
        dt.date.fromisoformat(expected["as_of"])
        _offence_table(expected["jurisdiction"])
        return []
    if case["category"] == "missing_facts":
        return [] if expected["missing"] else [f"{case['id']}: no missing fact named"]
    table = _offence_table(expected["jurisdiction"])
    row = next(o for o in table["offences"] if o["offence_id"] == expected["offence_id"])
    state = row["state_compounding"]
    if state["status"] != "VERIFIED":
        return [f"{case['id']}: premise must be checked against a VERIFIED row"]
    applicable = [a["inr"] for a in state["amounts"] if a["occurrence"] in (expected["occurrence"], "any")]
    if not applicable:
        return [f"{case['id']}: no verified amount for occurrence {expected['occurrence']}"]
    if expected["verdict"] == "contradicted" and expected["claimed_inr"] in applicable:
        return [f"{case['id']}: claimed amount matches the table, so it is not a false premise"]
    return []


async def _probe_temporal_retrieval(case: dict[str, Any]) -> tuple[bool, str]:
    expected = case["expected"]
    session = _RecordingSession()
    filters = {"jurisdiction": expected["jurisdiction"], "as_of": dt.date.fromisoformat(expected["as_of"])}
    try:
        await dense_search(session, [0.0], None, 5, **filters)
        await keyword_search(session, case["query"], None, 5, **filters)
    except TypeError:
        return False, "retrieval legs accept no jurisdiction/as_of arguments"
    for sql, params in session.statements:
        if not all(column in sql for column in ("jurisdiction", "effective_from", "effective_to")):
            return False, "retrieval SQL does not filter on jurisdiction and effective dates"
        if expected["jurisdiction"] not in params.values():
            return False, "retrieval SQL does not bind the requested jurisdiction"
    return True, "jurisdiction and date filters applied before ranking"


def _probe_missing_facts(case: dict[str, Any]) -> tuple[bool, str]:
    try:
        premise = importlib.import_module("app.agent.premise")
    except ModuleNotFoundError:
        return False, "app.agent.premise is not implemented"
    missing = set(premise.missing_facts(case["query"]))
    return (set(case["expected"]["missing"]) <= missing), f"missing facts reported: {sorted(missing)}"


def _probe_false_premise(case: dict[str, Any]) -> tuple[bool, str]:
    try:
        premise = importlib.import_module("app.agent.premise")
    except ModuleNotFoundError:
        return False, "app.agent.premise is not implemented"
    result = premise.check_premise(case["query"], _offence_table(case["expected"]["jurisdiction"]))
    return result.get("verdict") == case["expected"]["verdict"], f"verdict: {result.get('verdict')}"


def evaluate() -> tuple[dict[str, Any], bool]:
    cases = load_cases()
    manifest_errors = _manifest_errors(cases)
    fixture_errors = [error for case in cases for error in _fixture_errors(case)]
    results = []
    for case in cases:
        if case["category"] == "temporal_retrieval":
            passed, detail = asyncio.run(_probe_temporal_retrieval(case))
        elif case["category"] == "missing_facts":
            passed, detail = _probe_missing_facts(case)
        else:
            passed, detail = _probe_false_premise(case)
        expected_fail = case["expected_status"] == "xfail"
        outcome = {(True, True): "xpass", (False, True): "xfail", (True, False): "pass", (False, False): "fail"}[(passed, expected_fail)]
        results.append({"id": case["id"], "language": case["language"], "category": case["category"], "outcome": outcome, "detail": detail})

    outcomes = Counter(result["outcome"] for result in results)
    report = {
        "schema": "setu.temporal-evaluation-report/v1",
        "mode": "strict_expected_failure",
        "cases": len(results),
        "outcomes": dict(outcomes),
        "by_language": {language: dict(Counter(r["outcome"] for r in results if r["language"] == language)) for language in LANGUAGES},
        "by_category": {category: dict(Counter(r["outcome"] for r in results if r["category"] == category)) for category in CATEGORIES},
        "manifest_errors": manifest_errors,
        "fixture_errors": fixture_errors,
        "unexpected": [r for r in results if r["outcome"] in ("xpass", "fail")],
        "results": results,
        "activity_accounting": {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
    }
    success = not manifest_errors and not fixture_errors and not report["unexpected"]
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
    if not success:
        print("temporal expected-failure suite changed: " + "; ".join(
            report["manifest_errors"] + report["fixture_errors"] + [f"{r['id']} {r['outcome']}" for r in report["unexpected"]]
        ))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
