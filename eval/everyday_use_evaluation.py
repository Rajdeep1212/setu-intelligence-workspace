"""Validate the reviewed everyday-use scenarios against captured evidence.

This is an offline evidence/checkpoint audit. It makes no provider, database,
network, or model calls and does not claim live answer quality.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "everyday_use_cases.jsonl"
MANIFEST_PATHS = tuple(
    ROOT / "corpus" / "manifests" / name
    for name in ("batch-001.json", "batch-002.json", "batch-003.json")
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def evaluate() -> dict[str, Any]:
    cases = load_jsonl(CASES_PATH)
    manifests = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in MANIFEST_PATHS
    }
    sources: dict[str, dict[str, Any]] = {}
    checks: dict[str, dict[str, Any]] = {}
    for batch_id, manifest in manifests.items():
        for item in manifest["items"]:
            for source in item["sources"]:
                if source.get("processing_status") == "retrieval_checked":
                    sources[source["official_url"]] = source
            for check in item.get("retrieval_checks", []):
                checks[f"{batch_id}:{check['check_id']}"] = check
        for check in manifest.get("batch_retrieval_checks", []):
            checks[f"{batch_id}:{check['check_id']}"] = check

    failures: list[str] = []
    if len(cases) != 12 or len({case["id"] for case in cases}) != 12:
        failures.append("cases must contain 12 unique IDs")
    if Counter(case["language"] for case in cases) != Counter(en=4, hi=4, bn=4):
        failures.append("cases must be balanced 4/4/4 across en/hi/bn")
    required_scenarios = {
        "application_steps", "eligibility", "missing_state",
        "similar_scheme_names", "unsupported_amount", "legal_inconclusive",
    }
    if not required_scenarios.issubset({case["scenario"] for case in cases}):
        failures.append("required everyday scenarios are missing")

    evidence_passes = 0
    checkpoint_passes = 0
    for case in cases:
        if not case.get("expected_behavior") or not case.get("required_sections"):
            failures.append(f"{case['id']}: missing expected behavior")
        if case.get("must_not_request_sensitive_values") is not True:
            failures.append(f"{case['id']}: sensitive-data guard missing")
        case_evidence_ok = True
        for evidence in case.get("evidence", []):
            source = sources.get(evidence["source_url"])
            if not source:
                failures.append(f"{case['id']}: evidence source is not retrieval-checked")
                case_evidence_ok = False
                continue
            text = (ROOT / source["extracted_path"]).read_text(encoding="utf-8").casefold()
            missing = [m for m in evidence["passage_markers"] if m.casefold() not in text]
            if missing:
                failures.append(f"{case['id']}: missing evidence markers {missing}")
                case_evidence_ok = False
        evidence_passes += int(case_evidence_ok)
        check = checks.get(case.get("retrieval_check_ref", ""))
        if not check or check.get("status") != "passed":
            failures.append(f"{case['id']}: referenced retrieval checkpoint did not pass")
        else:
            checkpoint_passes += 1

    return {
        "schema": "setu.everyday-use-evaluation/v1",
        "cases": len(cases),
        "by_language": dict(Counter(case["language"] for case in cases)),
        "source_passage_checks_passed": evidence_passes,
        "retrieval_checkpoints_passed": checkpoint_passes,
        "failures": failures,
        "passed": not failures,
        "activity": {"provider_calls": 0, "database_requests": 0, "external_requests": 0},
    }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
