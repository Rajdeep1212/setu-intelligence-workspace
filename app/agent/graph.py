"""
LangGraph agent — Week 3.

    route --(retrieve_docs)--> retrieve_docs -----> generate -> END
          `-(check_eligibility)-> check_eligibility -^

`session` (an AsyncSession, request-scoped in FastAPI) is bound into the
tool nodes via functools.partial when the graph is built, rather than
carried inside the state dict — state is meant to be the serializable
"memory" of the conversation, and a DB session isn't that.
"""

from __future__ import annotations

import asyncio
import functools
import logging

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import generate_structured
from app.agent.models import GeneratedAnswer, RouteDecision
from app.agent.state import AgentState
from app.agent.tools import check_eligibility_tool, retrieve_docs_tool
from app.grounding import abstention_message, query_language, select_citations
from app.language import (
    answer_uses_target_language,
    dominant_supported_script,
    target_language_instruction,
)
from app.numerical_grounding import (
    NumericalGroundingResult,
    validate_numerical_grounding,
)


logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = (
    "You route citizen questions about Indian government schemes and "
    "public documents to the right tool. Use check_eligibility only when "
    "the user is asking whether they personally qualify for one specific "
    "named scheme (income/age/state limits etc). Use retrieve_docs for "
    "everything else — general questions, 'what is X', 'how do I apply', "
    "comparisons."
)

ANSWER_SYSTEM_PROMPT = (
    "You are Setu, an assistant that answers questions about Indian "
    "government schemes and public documents using ONLY the provided "
    "context. If the context doesn't contain the answer, say so plainly — "
    "never invent scheme details, numbers, or eligibility criteria. Use only "
    "facts explicitly supported by the supplied context; do not add remembered "
    "or external facts. Do not introduce a number, percentage, date, quantity, "
    "or scale statement unless it is explicitly supported by evidence that you "
    "cite. Omit unsupported details rather than guessing. Answer "
    "in the same language the question was asked in. For document evidence, "
    "return only the chunk IDs that materially support the final answer. "
    "Never invent a chunk ID and do not cite merely related context."
)

NUMERICAL_CORRECTION_INSTRUCTION = (
    "Correction required: regenerate the answer once from the same evidence. "
    "Use only facts explicitly supported by that evidence. Every number, "
    "percentage, date, quantity, and scale statement must be explicitly "
    "supported by a chunk ID returned as a citation. Omit unsupported details."
)


def _selected_citation_evidence(
    retrieved_chunks: list[dict], citations: list[dict]
) -> list[str]:
    selected_ids = {citation["chunk_id"] for citation in citations}
    return [
        str(chunk.get("content", ""))
        for chunk in retrieved_chunks
        if str(chunk["id"]) in selected_ids
    ]


async def route_node(state: AgentState) -> dict:
    decision = await asyncio.to_thread(
        generate_structured,
        stage="route_decision",
        system_prompt=ROUTER_SYSTEM_PROMPT,
        user_prompt=state["query"],
        response_model=RouteDecision,
    )
    update: dict = {"route": decision.route}
    if decision.scheme_name_hint:
        update["scheme_name_hint"] = decision.scheme_name_hint
    return update


async def retrieve_docs_node(state: AgentState, session: AsyncSession) -> dict:
    chunks = await retrieve_docs_tool(session, state["query"], state.get("language"))
    return {"retrieved_chunks": chunks}


async def check_eligibility_node(state: AgentState, session: AsyncSession) -> dict:
    hint = state.get("scheme_name_hint") or state["query"]
    matches = await check_eligibility_tool(session, hint)
    return {"eligibility_matches": matches}


async def generate_node(state: AgentState) -> dict:
    if state["route"] == "check_eligibility" and state.get("eligibility_matches"):
        context = "\n\n".join(
            f"Scheme: {m['scheme_name']}\nCriteria: {m['criteria']}"
            for m in state["eligibility_matches"]
        )
    elif state.get("retrieved_chunks"):
        context = "\n\n".join(
            f"[chunk_id={c['id']}]\n{c['content']}"
            for c in state["retrieved_chunks"]
        )
    else:
        return {
            "answer": abstention_message(state["query"], state.get("language")),
            "citations": [],
            "confidence": 0.0,
        }

    target_language = query_language(state["query"], state.get("language"))
    user_prompt = f"Context:\n{context}\n\nQuestion: {state['query']}"
    system_prompt = (
        f"{ANSWER_SYSTEM_PROMPT}\n\n"
        f"{target_language_instruction(target_language)}"
    )
    retrieved_chunks = state.get("retrieved_chunks", [])
    correction_categories: str | None = None

    for attempt in (1, 2):
        result = await asyncio.to_thread(
            generate_structured,
            stage="answer_generation",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=GeneratedAnswer,
        )

        if state["route"] == "retrieve_docs":
            citations = select_citations(retrieved_chunks, result.citation_ids)
            if result.abstained or not citations:
                return {
                    "answer": abstention_message(
                        state["query"], state.get("language")
                    ),
                    "citations": [],
                    "confidence": 0.0,
                }
            numerical_result = validate_numerical_grounding(
                result.answer,
                _selected_citation_evidence(retrieved_chunks, citations),
            )
        else:
            citations = []
            numerical_result = NumericalGroundingResult(0, 0)

        language_valid = answer_uses_target_language(
            result.answer, target_language
        )
        numerical_valid = numerical_result.is_valid
        if language_valid and numerical_valid:
            if attempt == 2:
                logger.info(
                    "answer_correction_succeeded stage=answer_generation "
                    "attempt=2 validation_categories=%s unsupported_count=0",
                    correction_categories or "unknown",
                )
            return {
                "answer": result.answer,
                "citations": citations,
                "confidence": result.confidence,
            }

        failed_categories = ",".join(
            category
            for category, failed in (
                ("language", not language_valid),
                ("numerical_grounding", not numerical_valid),
            )
            if failed
        )
        if not language_valid:
            event = (
                "answer_language_mismatch"
                if attempt == 1
                else "answer_language_correction_failed"
            )
            logger.warning(
                "%s stage=answer_generation attempt=%s target_language=%s "
                "detected_script=%s correction_attempt=1",
                event,
                attempt,
                target_language,
                dominant_supported_script(result.answer),
            )
        if not numerical_valid:
            event = (
                "answer_numerical_grounding_mismatch"
                if attempt == 1
                else "answer_numerical_grounding_correction_failed"
            )
            logger.warning(
                "%s stage=answer_generation attempt=%s unsupported_count=%s "
                "correction_attempt=1",
                event,
                attempt,
                numerical_result.unsupported_count,
            )

        if attempt == 2:
            logger.warning(
                "answer_correction_failed stage=answer_generation attempt=2 "
                "validation_categories=%s unsupported_count=%s",
                failed_categories,
                numerical_result.unsupported_count,
            )
            return {
                "answer": abstention_message(state["query"], target_language),
                "citations": [],
                "confidence": 0.0,
            }

        logger.warning(
            "answer_correction_started stage=answer_generation attempt=1 "
            "validation_categories=%s unsupported_count=%s",
            failed_categories,
            numerical_result.unsupported_count,
        )
        correction_categories = failed_categories
        system_prompt = (
            f"{ANSWER_SYSTEM_PROMPT}\n\n"
            f"{target_language_instruction(target_language, correction=True)}\n\n"
            f"{NUMERICAL_CORRECTION_INSTRUCTION}"
        )

    raise AssertionError("answer generation attempts exhausted")


def _pick_route(state: AgentState) -> str:
    return state["route"]


def build_graph(session: AsyncSession):
    graph = StateGraph(AgentState)

    graph.add_node("route", route_node)
    graph.add_node("retrieve_docs", functools.partial(retrieve_docs_node, session=session))
    graph.add_node("check_eligibility", functools.partial(check_eligibility_node, session=session))
    graph.add_node("generate", generate_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        _pick_route,
        {"retrieve_docs": "retrieve_docs", "check_eligibility": "check_eligibility"},
    )
    graph.add_edge("retrieve_docs", "generate")
    graph.add_edge("check_eligibility", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


async def run_agent(session: AsyncSession, query: str, language: str | None = None) -> AgentState:
    compiled_graph = build_graph(session)
    initial_state: AgentState = {"query": query, "language": language}
    return await compiled_graph.ainvoke(initial_state)
