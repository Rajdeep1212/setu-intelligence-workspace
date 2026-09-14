"""Send the fixed latency measurement set without printing sensitive inputs."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("everyday-en-01", "everyday-bn-01")
EXPECTED = {
    "everyday-en-01": {
        "source_url": "https://eshram.gov.in/faqs",
        "link_kinds": ["application", "help"],
    },
    "everyday-bn-01": {
        "source_url": "https://wb.gov.in/government-schemes-details-west-bengal-student-credit-card-scheme.aspx",
        "link_kinds": ["application", "help"],
    },
}


def _cases() -> dict[str, dict]:
    path = ROOT / "eval" / "everyday_use_cases.jsonl"
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {value["id"]: value for value in values}


def main() -> int:
    api_key = os.environ.get("SETU_API_KEY")
    if not api_key:
        raise RuntimeError("SETU_API_KEY is required")
    cases = _cases()
    selected_case = os.environ.get("SETU_LATENCY_CASE_FILTER")
    if selected_case and selected_case not in CASE_IDS:
        raise RuntimeError("SETU_LATENCY_CASE_FILTER must name a declared case")
    selected_case_ids = (selected_case,) if selected_case else CASE_IDS
    for case_id in selected_case_ids:
        case = cases[case_id]
        payload = json.dumps(
            {"query": case["query"], "language": case["language"]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8000/query",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            method="POST",
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.load(response)
            status_code = response.status
        duration_ms = (time.perf_counter() - started) * 1000
        citations = body.get("citations", [])
        link_kinds = [link.get("kind") for link in body.get("official_links", [])]
        expected = EXPECTED[case_id]
        source_match = bool(citations) and citations[0].get("url") == expected["source_url"]
        quality_ok = (
            status_code == 200
            and body.get("response_status") == "answered"
            and len(citations) == 1
            and source_match
            and link_kinds == expected["link_kinds"]
        )
        print(
            "LATENCY_CASE "
            f"id={case_id} http={status_code} duration_ms={duration_ms:.2f} "
            f"status={body.get('response_status')} citations={len(citations)} "
            f"sections={len(body.get('sections', []))} "
            f"link_kinds={','.join(link_kinds)} source_match={str(source_match).lower()} "
            f"quality_ok={str(quality_ok).lower()}"
        )
        if not quality_ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
