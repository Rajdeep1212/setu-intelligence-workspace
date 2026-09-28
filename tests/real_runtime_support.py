"""Opt-in support for the real-runtime staging acceptance gate.

This module replaces only the outbound structured-generation function.  The
FastAPI application, installed LangGraph package, graph nodes, OpenVINO
retrieval, PostgreSQL reads, grounding, and response validation stay real.
"""

from __future__ import annotations

import os
import re
import threading
import logging
from collections import Counter
from dataclasses import dataclass
from time import perf_counter

from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.models import GeneratedAnswer, GeneratedClaim, RouteDecision
from app.config import settings
from app.errors import LLMProviderError


STAGING_DATABASE = "setu_corpus_staging"
EXPECTED_COUNTS = (26, 331, 0)
FAILURE_QUESTION = "SETU integration provider failure"
_CHUNK_PATTERN = re.compile(
    r"\[chunk_id=([^\]]+)\]\n"
    r"(?:\[source_scope=[^\]]*\]\n)?"
    r"(.*?)(?=\n\n\[chunk_id=|\n\nQuestion: )",
    re.DOTALL,
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderCase:
    language: str
    markers: tuple[str, ...]
    claims: tuple[tuple[str, str], ...]
    abstained: bool = False
    alternatives: tuple[
        tuple[tuple[str, ...], tuple[tuple[str, str], ...]], ...
    ] = ()


PROVIDER_CASES = {
    "PMSBY के लिए कौन पात्र है?": ProviderCase(
        language="hi", markers=("age group of 18 to 70 years",),
        claims=(("conditions", "भाग लेने वाले बैंक या डाकघर के 18 से 70 वर्ष आयु के व्यक्तिगत खाताधारक योजना में शामिल हो सकते हैं।"),),
        alternatives=((
            ("All bank account holders other than institutional account holders",),
            (("conditions", "संस्थागत खाताधारकों को छोड़कर सभी बैंक खाताधारक PMSBY की सदस्यता ले सकते हैं।"),),
        ),),
    ),
    "Where do I apply for the student credit card scheme?\n\nClarification reply: West Bengal": ProviderCase(
        language="en", markers=("Register on the official WBSCC online portal",),
        claims=(("direct_answer", "Register on the official WBSCC online portal and upload the required documents."),),
    ),
    "How do I register for e-Shram and what do I need?": ProviderCase(
        language="en",
        markers=("Aadhaar linked Mobile number", "Aadhaar Number"),
        claims=(
            (
                "direct_answer",
                "To register, have your Aadhaar number and Aadhaar-linked mobile number ready, as listed in the cited official FAQ.",
            ),
        ),
    ),
    "प्रधानमंत्री उज्ज्वला योजना के लिए आवेदन कैसे करूँ और कौन से दस्तावेज़ चाहिए?": ProviderCase(
        language="hi",
        markers=("Documents Required", "Know Your Customer"),
        claims=(
            (
                "required_documents",
                "उपलब्ध आधिकारिक अंश में ग्राहक-परिचय फॉर्म तथा पहचान और पते के प्रमाण सहित आवश्यक दस्तावेज़ बताए गए हैं।",
            ),
        ),
    ),
    "পশ্চিমবঙ্গ স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব?": ProviderCase(
        language="bn",
        markers=(
            "Register on the official WBSCC online portal",
            "Upload required documents",
        ),
        claims=(
            (
                "how_to_apply",
                "সরকারি ডব্লিউবিএসসিসি অনলাইন পোর্টালে নিবন্ধন করে প্রয়োজনীয় নথি আপলোড করতে বলা হয়েছে।",
            ),
        ),
    ),
    "ई-श्रम कार्ड बनते ही ₹3,000 मिलते हैं ना?": ProviderCase(
        language="hi",
        markers=("financial/ monetary/ cash benefits", "financial benefits"),
        claims=(
            (
                "limitations",
                "उपलब्ध आधिकारिक प्रश्नोत्तर अंश ई-श्रम पंजीकरण के आधार पर किसी नकद लाभ की पुष्टि नहीं करता; इसलिए पूछी गई राशि की पुष्टि नहीं की जा सकती।",
            ),
        ),
        abstained=True,
    ),
}


class RealRuntimeHarness:
    """State shared by the unittest runner and the loopback Uvicorn process."""

    def __init__(self) -> None:
        source_url = settings.database_engine_url
        if source_url.database != "setu":
            raise RuntimeError("Integration base database must be the application database")
        if source_url.host not in {"db", "localhost", "127.0.0.1"}:
            raise RuntimeError("Integration database host is not an approved local target")

        staging_url = source_url.set(database=STAGING_DATABASE)
        self.engine = create_async_engine(
            staging_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            connect_args={"server_settings": {"default_transaction_read_only": "on"}},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.database_observations: list[dict[str, object]] = []
        self.staging_chunk_ids: set[str] = set()
        self.provider_calls: Counter[str] = Counter()
        self.provider_records: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()

    async def get_session(self):
        async with self.sessions() as session:
            started = perf_counter()
            row = (
                await session.execute(
                    text(
                        """
                        SELECT current_database(),
                               (SELECT count(*) FROM documents),
                               (SELECT count(*) FROM chunks),
                               (SELECT count(*) FROM eligibility_criteria)
                        """
                    )
                )
            ).one()
            database_name = str(row[0])
            counts = (int(row[1]), int(row[2]), int(row[3]))
            if database_name != STAGING_DATABASE or counts != EXPECTED_COUNTS:
                raise RuntimeError("Staging database identity or counts changed")
            logger.info(
                "staging_session_profile request_id=- acquire_and_guard_ms=%.2f "
                "pool_size=1 max_overflow=0 documents=%s chunks=%s eligibility=%s",
                (perf_counter() - started) * 1000,
                counts[0],
                counts[1],
                counts[2],
            )
            self.database_observations.append(
                {"database": database_name, "counts": counts}
            )
            if not self.staging_chunk_ids:
                result = await session.execute(text("SELECT id::text FROM chunks"))
                self.staging_chunk_ids = {str(value) for value in result.scalars()}
            await session.rollback()
            logger.info(
                "staging_session_profile request_id=- guard_transaction_released=true"
            )
            yield session

    def generate_structured(
        self,
        *,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type,
        **_: object,
    ):
        if stage == "route_decision":
            query = user_prompt
            with self._lock:
                self.provider_calls[query] += 1
            if query == FAILURE_QUESTION:
                raise LLMProviderError()
            if query not in PROVIDER_CASES:
                raise AssertionError("Unexpected question reached provider boundary")
            return RouteDecision(route="retrieve_docs")

        if stage != "answer_generation" or response_model is not GeneratedAnswer:
            raise AssertionError("Unexpected provider stage or response model")
        query = user_prompt.rsplit("\n\nQuestion: ", 1)[-1]
        case = PROVIDER_CASES.get(query)
        if case is None:
            raise AssertionError("Unexpected answer-generation question")
        expected_language = {
            "en": "Target output language: English.",
            "hi": "Target output language: Hindi.",
            "bn": "Target output language: Bengali.",
        }[case.language]
        if expected_language not in system_prompt:
            raise AssertionError("Selected response language did not reach generation")

        chunks = _CHUNK_PATTERN.findall(user_prompt)
        with self._lock:
            self.provider_records[query] = {
                "language": case.language,
                "retrieved_passages": [
                    {"chunk_id": chunk_id, "passage": content}
                    for chunk_id, content in chunks
                ],
            }
        selected: tuple[int, str, str, tuple[tuple[str, str], ...]] | None = None
        evidence_options = ((case.markers, case.claims),) + case.alternatives
        for markers, option_claims in evidence_options:
            for rank, (chunk_id, content) in enumerate(chunks, start=1):
                if any(marker.casefold() in content.casefold() for marker in markers):
                    selected = (rank, chunk_id, content, option_claims)
                    break
            if selected is not None:
                break
        if selected is None:
            logger.error("staging_passage_missing query=%r chunk_ids=%s", query, [item[0] for item in chunks])
            raise AssertionError("Required useful passage was not retrieved")

        rank, chunk_id, content, selected_claims = selected
        claims = [
            GeneratedClaim(kind=kind, text=claim, citation_ids=[chunk_id])
            for kind, claim in selected_claims
        ]
        answer = " ".join(claim.text for claim in claims)
        with self._lock:
            self.provider_calls[query] += 1
            self.provider_records[query].update({
                "useful_passage_rank": rank,
                "chunk_id": chunk_id,
                "passage": content,
                "language": case.language,
            })
        return GeneratedAnswer(
            answer=answer,
            confidence=0.9,
            citation_ids=[chunk_id],
            claims=claims,
            abstained=case.abstained,
        )


def integration_api_key() -> SecretStr:
    value = os.environ.get("SETU_INTEGRATION_API_KEY")
    if not value:
        raise RuntimeError("SETU_INTEGRATION_API_KEY is required")
    return SecretStr(value)
