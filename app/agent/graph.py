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

import functools

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import generate_structured
from app.agent.models import GeneratedAnswer, RouteDecision
from app.agent.state import AgentState
from app.agent.tools import check_eligibility_tool, retrieve_docs_tool
from app.grounding import abstention_message, select_citations

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
    "never invent scheme details, numbers, or eligibility criteria. Answer "
    "in the same language the question was asked in. For document evidence, "
    "return only the chunk IDs that materially support the final answer. "
    "Never invent a chunk ID and do not cite merely related context."
)


async def route_node(state: AgentState) -> dict:
    decision = generate_structured(
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

    result = generate_structured(
        stage="answer_generation",
        system_prompt=ANSWER_SYSTEM_PROMPT,
        user_prompt=f"Context:\n{context}\n\nQuestion: {state['query']}",
        response_model=GeneratedAnswer,
    )

    if state["route"] == "retrieve_docs":
        citations = select_citations(
            state.get("retrieved_chunks", []), result.citation_ids
        )
        if result.abstained or not citations:
            return {
                "answer": abstention_message(state["query"], state.get("language")),
                "citations": [],
                "confidence": 0.0,
            }
    else:
        citations = []

    return {"answer": result.answer, "citations": citations, "confidence": result.confidence}


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
