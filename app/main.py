from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_agent
from app.db import get_session
from app.schemas import Citation, QueryRequest, QueryResponse

app = FastAPI(title="Setu API", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)):
    result = await session.execute(text("SELECT 1"))
    return {"db": "ok" if result.scalar() == 1 else "error"}


@app.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, session: AsyncSession = Depends(get_session)):
    """
    Week 3: routes through the LangGraph agent — an LLM decides between
    document retrieval and the structured eligibility lookup, then
    generates a grounded answer from whichever context it collected.
      Week 4: SSE streaming, API-key auth, rate limiting.

    Needs GROQ_API_KEY or GEMINI_API_KEY set in .env (see app/agent/llm.py).
    First call after a fresh container start will also be slow (~seconds)
    while bge-m3 and the reranker load into memory — cached in module-level
    globals after that, so subsequent calls are fast.
    """
    final_state = await run_agent(session, payload.query, language=payload.language)

    citations = [Citation(**c) for c in final_state.get("citations", [])]

    return QueryResponse(
        answer=final_state.get("answer", "No answer generated."),
        citations=citations,
        route=final_state.get("route"),
        confidence=final_state.get("confidence"),
    )
