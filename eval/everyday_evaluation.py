"""Everyday-use evaluation for scheme questions (M2.2).

eval/everyday_cases.jsonl holds 12 held-out questions (4 English, 4 Hindi,
4 Bengali), written before any tuning. Each states the expected response
status, the answer sections a person needs, and the evidence that must be
there. eval/everyday_retrieval.json holds what retrieval returned for each
question from the staged scheme corpus, recorded once on a laptop.

    python -m eval.everyday_evaluation                    # offline; prints JSON
    python -m eval.everyday_evaluation --markdown-out docs/everyday-evaluation-report.md
    python -m eval.everyday_evaluation --capture          # laptop only, see below

The default run is offline: no provider, database, network or model. It
replays the saved results through today's agent graph and scores three things
separately:

- status: what the code decides. When the code hands the evidence to the
  provider, the provider would answer or abstain; that is recorded as
  "provider_decides" and only counts as a pass where an answer is expected.
- evidence: the expected official source, and the passage, are in the saved
  top results (same rule as the corpus retrieval checks).
- sections: only sections the code writes can be checked. Provider-written
  sections carry no label in the response today, so they are reported as
  not checkable and do not pass.

It does not measure answer wording. --capture needs the local models and the
staging database (corpus/README.md); it reads only and rewrites the saved
results, so the report must be regenerated and reviewed with it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from app.agent.graph import run_agent
from app.agent.models import RouteDecision
from app.grounding import query_language
from app.next_steps import is_official_url
from app.next_steps import select as select_next_steps
from ingestion.corpus_pipeline import assess_retrieval_check

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "everyday_cases.jsonl"
RETRIEVAL_PATH = ROOT / "eval" / "everyday_retrieval.json"
REPORT_PATH = ROOT / "docs" / "everyday-evaluation-report.md"
STAGING_DATABASE = "setu_corpus_staging"

PROVIDER_DECIDES = "provider_decides"
EXPECTED_STATUSES = {"answered", "abstained", "needs_clarification", "eligibility_unverified"}
# Sections the code writes itself, and the status that produces each.
CODE_SECTIONS = {
    "clarifying_question": "needs_clarification",
    "eligibility_handoff": "eligibility_unverified",
    "plain_abstention": "abstained",
}
PROVIDER_SECTIONS = {"direct_answer", "how_to_apply", "conditions", "official_source", "limitations"}
SECTIONS = set(CODE_SECTIONS) | PROVIDER_SECTIONS | {"official_next_step"}
SAVED_FIELDS = ("id", "document_id", "title", "url", "content", "rerank_score")


class _ProviderNeeded(Exception):
    """The graph reached answer generation; offline, that is where it stops."""


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_retrieval() -> dict[str, Any]:
    return json.loads(RETRIEVAL_PATH.read_text(encoding="utf-8"))


async def _observe(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    routed_by_provider = False

    def provider(**kwargs):
        nonlocal routed_by_provider
        if kwargs["stage"] == "route_decision":
            # Assumption, stated in the report: the provider router sends a general question to retrieval.
            routed_by_provider = True
            return RouteDecision(route="retrieve_docs")
        raise _ProviderNeeded

    with (
        patch("app.agent.graph.generate_structured", side_effect=provider),
        patch("app.agent.graph.retrieve_docs_tool", new=AsyncMock(return_value=results)),
    ):
        try:
            state = await run_agent(object(), query)
            status, answer = state.get("response_status", "answered"), state.get("answer", "")
        except _ProviderNeeded:
            status, answer = PROVIDER_DECIDES, ""
    steps = select_next_steps("answered" if status == PROVIDER_DECIDES else status, query, query_language(query, None))
    return {"status": status, "answer": answer, "next_steps": steps, "routed_by": "provider" if routed_by_provider else "code"}


def _evidence(check: dict[str, Any], results: list[dict[str, Any]], observed: dict[str, Any]) -> dict[str, Any]:
    if check.get("official_next_step"):
        urls = [step["url"] for step in observed["next_steps"]]
        return {"passed": bool(urls) and all(is_official_url(url) for url in urls), "next_step_urls": urls}
    return assess_retrieval_check(check, results, set(check.get("expected_urls", [])))


def _section(name: str, observed: dict[str, Any]) -> str:
    if name == "official_next_step":
        return "present" if observed["next_steps"] else "missing"
    if name in CODE_SECTIONS:
        return "present" if observed["status"] == CODE_SECTIONS[name] and observed["answer"].strip() else "missing"
    return "not_checkable"  # provider-written; the response has no section labels yet


async def score_case(case: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    observed = await _observe(case["query"], results)
    expected = case["expected_status"]
    status_passed = observed["status"] == (PROVIDER_DECIDES if expected == "answered" else expected)
    evidence = [_evidence(check, results, observed) for check in case["evidence"]]
    sections = {name: _section(name, observed) for name in case["required_sections"]}
    result = {
        "id": case["id"],
        "language": case["language"],
        "status": {"expected": expected, "observed": observed["status"], "routed_by": observed["routed_by"], "passed": status_passed},
        "evidence": {"passed": all(check["passed"] for check in evidence), "checks": evidence},
        "sections": {"passed": all(value == "present" for value in sections.values()), "required": sections},
    }
    result["passed"] = all(result[part]["passed"] for part in ("status", "evidence", "sections"))
    return result


def evaluate() -> dict[str, Any]:
    cases, saved = load_cases(), load_retrieval()
    results = [asyncio.run(score_case(case, saved["results"][case["id"]])) for case in cases]
    by_language: dict[str, Counter] = {}
    for result in results:
        counts = by_language.setdefault(result["language"], Counter())
        for part in ("status", "evidence", "sections", "passed"):
            counts[part] += bool(result[part] if part == "passed" else result[part]["passed"])
    return {
        "schema": "setu.everyday-evaluation-report/v1",
        "captured": saved["captured"],
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "status_passed": sum(result["status"]["passed"] for result in results),
        "evidence_passed": sum(result["evidence"]["passed"] for result in results),
        "sections_passed": sum(result["sections"]["passed"] for result in results),
        "by_language": {language: dict(counts) for language, counts in sorted(by_language.items())},
        "results": results,
        "activity_accounting": {"provider_calls": 0, "database_requests": 0, "external_requests": 0, "model_downloads": 0},
    }


def markdown(report: dict[str, Any]) -> str:
    mark = {True: "pass", False: "fail"}
    lines = [
        "# Everyday-use evaluation (M2.2)",
        "",
        "Generated by `python -m eval.everyday_evaluation --markdown-out docs/everyday-evaluation-report.md`.",
        "Offline replay of saved retrieval results; no provider, database, network or model.",
        "It does not measure answer wording.",
        "",
        f"Retrieval results recorded: {report['captured']['at']} from `{report['captured']['database']}`"
        f" ({report['captured']['documents']} documents, {report['captured']['chunks']} chunks).",
        "",
        "| Measure | Passed |",
        "|---|---|",
        f"| All three (case passes) | {report['passed']} of {report['cases']} |",
        f"| Status decided as expected | {report['status_passed']} of {report['cases']} |",
        f"| Evidence in the saved top results | {report['evidence_passed']} of {report['cases']} |",
        f"| Required sections present | {report['sections_passed']} of {report['cases']} |",
        "",
        "| Case | Expected status | Observed | Status | Evidence | Sections |",
        "|---|---|---|---|---|---|",
    ]
    for result in report["results"]:
        sections = ", ".join(f"{name}: {value}" for name, value in result["sections"]["required"].items())
        lines.append(
            f"| {result['id']} | {result['status']['expected']} | {result['status']['observed']} |"
            f" {mark[result['status']['passed']]} | {mark[result['evidence']['passed']]} | {sections} |"
        )
    lines += [
        "",
        "`provider_decides`: the code handed the evidence to the provider, which would answer or abstain.",
        "It passes only where an answer is expected. Routing by the provider is assumed to choose retrieval.",
        "`not_checkable`: the section is written by the provider and the response has no section labels yet.",
        "",
    ]
    return "\n".join(lines)


async def capture(database_name: str = STAGING_DATABASE) -> dict[str, Any]:
    """Record retrieval for every case from the staging database (read only)."""
    from datetime import datetime, timezone

    from sqlalchemy import URL, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.agent.tools import retrieve_docs_tool
    from ingestion.staging_db import LocalDatabaseConfig, connect_staging

    config = LocalDatabaseConfig.from_env_file()
    await (await connect_staging(config, database_name)).close()  # refuses anything but the local staging database
    engine = create_async_engine(
        URL.create("postgresql+asyncpg", username=config.user, password=config.password,
                   host=config.host, port=config.port, database=database_name),
        pool_size=1,
        max_overflow=0,
    )
    # The two FP32 models do not fit in memory together on the laptop (M2.4):
    # embed every question first, release that model, then search and rerank.
    import gc

    from app.retrieval import embeddings

    cases = load_cases()
    vectors = dict(zip((case["query"] for case in cases), embeddings.embed_chunks([case["query"] for case in cases])))
    embeddings._openvino_model = None
    gc.collect()

    saved: dict[str, Any] = {"results": {}}
    try:
        async with AsyncSession(engine) as session:
            documents = (await session.execute(text("SELECT count(*) FROM documents"))).scalar_one()
            chunks = (await session.execute(text("SELECT count(*) FROM chunks"))).scalar_one()
            for case in cases:
                with patch("app.retrieval.pipeline.embed_chunks", side_effect=lambda queries: [vectors[q] for q in queries]):
                    results = await retrieve_docs_tool(session, case["query"], None)
                saved["results"][case["id"]] = [
                    {key: (float(r[key]) if key == "rerank_score" else None if r.get(key) is None else str(r[key])) for key in SAVED_FIELDS}
                    for r in results
                ]
    finally:
        await engine.dispose()
    saved["captured"] = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "database": database_name,
        "documents": documents,
        "chunks": chunks,
    }
    RETRIEVAL_PATH.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return saved["captured"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="record retrieval from the local staging database")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    if args.capture:
        print(json.dumps(asyncio.run(capture())))
        return 0
    report = evaluate()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(text, encoding="utf-8", newline="\n")
    if args.markdown_out:
        args.markdown_out.write_text(markdown(report), encoding="utf-8", newline="\n")
    if not (args.json_out or args.markdown_out):
        print(text, end="")
    return 0  # a baseline, not a gate: the tracked report is compared in tests


if __name__ == "__main__":
    raise SystemExit(main())
