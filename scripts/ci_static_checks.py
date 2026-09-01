"""Lightweight publication and workflow checks for zero-spend CI.

This is intentionally a narrow deterministic guard, not a comprehensive
security audit or a replacement for GitHub's workflow parser.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
EXPECTED_ACTIONS = {
    "actions/checkout": "11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/setup-python": "42375524e23c412d93fb67b49958b491fce71c38",
    "actions/setup-node": "1e60f620b9541d16bece96c5465dc8ee9832be0b",
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8")
    return [ROOT / item for item in output.split("\0") if item]


def check_workflow(errors: list[str]) -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lowered = text.casefold()
    required_fragments = (
        "permissions:\n  contents: read",
        "runs-on: ubuntu-latest",
        "python-version: \"3.11\"",
        "node-version: \"22\"",
        "python -m eval.offline_evaluation",
        "npm run test:run",
        "npm run test:e2e",
    )
    for fragment in required_fragments:
        if fragment not in text:
            errors.append(f"workflow missing required fragment: {fragment}")
    prohibited = (
        "pull_request_target",
        "workflow_dispatch",
        "secrets.",
        "permissions: write",
        "upload-artifact",
        "download-artifact",
        "actions/cache",
        "runs-on: windows",
        "runs-on: macos",
        "larger runner",
        "environment:",
        "docker build",
        "huggingface",
    )
    for fragment in prohibited:
        if fragment in lowered:
            errors.append(f"workflow contains prohibited capability: {fragment}")

    uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    if not uses:
        errors.append("workflow contains no actions")
    for reference in uses:
        if "@" not in reference:
            errors.append(f"action lacks ref: {reference}")
            continue
        action, ref = reference.rsplit("@", 1)
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"action is not pinned to a full commit SHA: {action}")
        if action in EXPECTED_ACTIONS and ref != EXPECTED_ACTIONS[action]:
            errors.append(f"action SHA differs from reviewed release: {action}")


def check_fixtures(errors: list[str]) -> None:
    manifest = json.loads((ROOT / "eval" / "offline_manifest.json").read_text(encoding="utf-8"))
    rows = []
    for line_number, line in enumerate(
        (ROOT / "eval" / "offline_cases.jsonl").read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid offline case JSON at line {line_number}")
            continue
        required = {"id", "language", "category", "provenance", "tags"}
        if not required.issubset(row):
            errors.append(f"offline case line {line_number} is missing required keys")
        rows.append(row)
    if len(rows) != manifest.get("headline_case_count"):
        errors.append("offline case count differs from manifest")
    if len({row.get("id") for row in rows}) != len(rows):
        errors.append("offline case identifiers are not unique")


def check_document_links(errors: list[str]) -> None:
    for path in tracked_files():
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            clean = target.strip().split("#", 1)[0]
            if not clean or re.match(r"^(?:https?://|mailto:)", clean):
                continue
            linked = (path.parent / clean).resolve()
            try:
                linked.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"documentation link escapes repository: {path.relative_to(ROOT)}")
                continue
            if not linked.exists():
                errors.append(f"missing documentation link: {path.relative_to(ROOT)} -> {target}")


def check_publication_content(errors: list[str]) -> None:
    tracked = tracked_files()
    for path in tracked:
        relative = path.relative_to(ROOT).as_posix()
        if relative == ".env" or relative.endswith("/.env"):
            errors.append(f"environment file is tracked: {relative}")

    secret_pattern = re.compile(
        r"(?:AIza[0-9A-Za-z_-]{30,}|ghp_[0-9A-Za-z]{30,}|sk-[0-9A-Za-z]{24,}|"
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)"
    )
    for path in tracked:
        if path.suffix.lower() not in {".json", ".jsonl", ".md", ".py", ".ts", ".tsx", ".yml", ".yaml"}:
            continue
        if secret_pattern.search(path.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"obvious secret-like pattern in tracked content: {path.relative_to(ROOT)}")

    unsafe_phrases = (
        "citation proves the claim",
        "citations prove the claim",
        "verified source badge",
        "you are eligible for",
        "you are not eligible for",
    )
    frontend_paths = [
        path
        for path in tracked
        if path.relative_to(ROOT).as_posix().startswith("frontend/src/")
        and ".test." not in path.name
    ]
    for path in frontend_paths:
        content = path.read_text(encoding="utf-8", errors="replace").casefold()
        for phrase in unsafe_phrases:
            if phrase in content:
                errors.append(f"prohibited trust wording in {path.relative_to(ROOT)}: {phrase}")


def main() -> int:
    errors: list[str] = []
    check_workflow(errors)
    check_fixtures(errors)
    check_document_links(errors)
    check_publication_content(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Lightweight publication checks passed (not a comprehensive security audit).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
