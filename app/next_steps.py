"""Official next steps after an answer (docs/FINDINGS.md, P6).

Answers used to stop at information. A response can now carry a short list
of official services to act on: where to check a challan, where to report
fraud, where to look up schemes. Every link comes from the reviewed table in
data/next_steps/services.json, must be on .gov.in or .nic.in, and is chosen
by fixed rules on the response status. There is no model call, and a
response with no matching rule carries no steps.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SERVICES_PATH = Path(__file__).resolve().parents[1] / "data" / "next_steps" / "services.json"
LANGUAGES = ("en", "hi", "bn")
MAX_STEPS = 3

MENTIONS = {
    "pm_kisan": re.compile(r"pm[\s-]?kisan|पीएम[\s-]?किसान|प्रधानमंत्री किसान|पीएम-किसान|কিষাণ|কিসান", re.IGNORECASE),
    "challan": re.compile(r"challan|चालान|চালান", re.IGNORECASE),
}


def is_official_url(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host.endswith(".gov.in") or host.endswith(".nic.in"))


@lru_cache(maxsize=1)
def load_table() -> dict[str, Any]:
    table = json.loads(SERVICES_PATH.read_text(encoding="utf-8"))
    for service_id, service in table["services"].items():
        if not is_official_url(service["url"]):
            raise ValueError(f"next step {service_id} is not an https .gov.in/.nic.in URL")
        if set(service["label"]) != set(LANGUAGES):
            raise ValueError(f"next step {service_id} needs a label in {LANGUAGES}")
    for rule in table["rules"]:
        unknown = [step for step in rule["steps"] if step not in table["services"]]
        if unknown:
            raise ValueError(f"rule refers to unknown services: {unknown}")
        mention = rule["when"].get("mentions")
        if mention is not None and mention not in MENTIONS:
            raise ValueError(f"rule uses unknown mention: {mention}")
    return table


def select(response_status: str | None, query: str, language: str | None) -> list[dict[str, str]]:
    """Steps for a response, from the first rule that matches; [] if none."""
    table = load_table()
    language = language if language in LANGUAGES else "en"
    for rule in table["rules"]:
        condition = rule["when"]
        if condition["response_status"] != response_status:
            continue
        mention = condition.get("mentions")
        if mention is not None and not MENTIONS[mention].search(query):
            continue
        return [
            {
                "id": step,
                "label": table["services"][step]["label"][language],
                "url": table["services"][step]["url"],
                "operator": table["services"][step]["operator"],
            }
            for step in rule["steps"][:MAX_STEPS]
        ]
    return []
