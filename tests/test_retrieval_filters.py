"""Phase 1: jurisdiction- and date-aware retrieval (docs/FINDINGS.md, P1).

Offline tests. A recording stand-in replaces the database session, so SQL is
inspected, not executed. The same filters were also executed against
PostgreSQL 16 with migration 0001 applied when this change was made; see the
pull request for that run.
"""

import asyncio
import hashlib
import unittest

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.agent import graph, tools
from app.agent.models import RouteDecision
from app.retrieval import pipeline
from app.retrieval.dense import dense_search
from app.retrieval.filters import RetrievalFilters
from app.retrieval.keyword import keyword_search
from app.schemas import QueryRequest

# SHA-256 of the unfiltered SQL on master before Phase 1. Without filters the
# statements must stay byte-identical, so a database without migration 0001
# keeps working.
UNFILTERED_DENSE_SQL_SHA256 = "7db36dda04b61ce7d82eada392cf7cc4f93f00a0a73e2405f9dcf3a37ae09b4b"
UNFILTERED_KEYWORD_SQL_SHA256 = "33163b0f6b6f8b34a4f64436c382f95276c5f9ba0e5899713f6feb665514ff41"
FILTER_COLUMNS = ("jurisdiction", "effective_from", "effective_to")


class RecordingSession:
    def __init__(self):
        self.statements = []

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), dict(params or {})))
        return []


def _run_legs(**filters):
    session = RecordingSession()
    asyncio.run(dense_search(session, [0.0], None, 5, **filters))
    asyncio.run(keyword_search(session, "helmet fine", None, 5, **filters))
    return session.statements


def _sha(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


class UnfilteredSqlTests(unittest.TestCase):
    def test_sql_is_byte_identical_to_pre_phase1(self):
        (dense_sql, dense_params), (keyword_sql, keyword_params) = _run_legs()

        self.assertEqual(_sha(dense_sql), UNFILTERED_DENSE_SQL_SHA256)
        self.assertEqual(_sha(keyword_sql), UNFILTERED_KEYWORD_SQL_SHA256)
        self.assertEqual(set(dense_params), {"embedding", "language", "limit"})
        self.assertEqual(set(keyword_params), {"query", "language", "limit"})

    def test_no_migration_columns_are_referenced(self):
        for sql, _ in _run_legs():
            for column in FILTER_COLUMNS:
                self.assertNotIn(column, sql)


class FilteredSqlTests(unittest.TestCase):
    def test_jurisdiction_only(self):
        for sql, params in _run_legs(jurisdiction="IN-WB"):
            self.assertIn(
                "COALESCE(c.jurisdiction, d.jurisdiction) IN (CAST(:jurisdiction AS text), 'IN')", sql
            )
            self.assertNotIn("effective_from", sql)
            self.assertEqual(params["jurisdiction"], "IN-WB")
            self.assertNotIn("as_of", params)

    def test_as_of_only(self):
        for sql, params in _run_legs(as_of=date(2019, 6, 15)):
            self.assertNotIn("jurisdiction", sql)
            self.assertIn("COALESCE(c.effective_from, d.effective_from) <= CAST(:as_of AS date)", sql)
            self.assertIn("COALESCE(c.effective_to, d.effective_to) > CAST(:as_of AS date)", sql)
            self.assertEqual(params["as_of"], date(2019, 6, 15))
            self.assertNotIn("jurisdiction", params)

    def test_both_filters_come_before_ranking(self):
        for sql, params in _run_legs(jurisdiction="IN-KA", as_of=date(2026, 9, 27)):
            where_at = sql.index("WHERE")
            order_at = sql.index("ORDER BY")
            for column in FILTER_COLUMNS:
                self.assertTrue(where_at < sql.index(column) < order_at, column)
            self.assertEqual(params["jurisdiction"], "IN-KA")
            self.assertEqual(params["as_of"], date(2026, 9, 27))

    def test_date_range_is_half_open(self):
        # effective_from is inclusive (<=) and effective_to exclusive (>), matching
        # the migration's CHECK (effective_to > effective_from).
        sql, _ = _run_legs(as_of=date(2022, 1, 24))[0]
        self.assertIn("effective_from) <= CAST(:as_of AS date)", sql)
        self.assertIn("effective_to) > CAST(:as_of AS date)", sql)
        self.assertNotIn("effective_to) >= ", sql)
        self.assertNotIn("effective_from) < CAST", sql)

    def test_unknown_start_date_never_counts_as_valid(self):
        # NULL effective_from means "unknown" (docs/FINDINGS.md, P1 risks), so
        # an undated source cannot answer a date-specific question.
        sql, _ = _run_legs(as_of=date(2019, 6, 15))[0]
        self.assertNotIn("effective_from, d.effective_from) IS NULL", sql)
        self.assertIn("effective_to, d.effective_to) IS NULL", sql)

    def test_values_are_bound_not_formatted(self):
        for sql, _ in _run_legs(jurisdiction="IN-DL", as_of=date(2024, 9, 11)):
            self.assertNotIn("IN-DL", sql)
            self.assertNotIn("2024-09-11", sql)
            self.assertIn(":jurisdiction", sql)
            self.assertIn(":as_of", sql)


class FilterValidationTests(unittest.TestCase):
    def test_accepts_central_and_state_codes(self):
        RetrievalFilters(jurisdiction="IN")
        RetrievalFilters(jurisdiction="IN-WB", as_of=date(2026, 1, 1))

    def test_rejects_bad_codes_before_any_sql(self):
        for bad in ("in-wb", "IN-WB-KOL", "WB", "IN-W", "IN-WB'; DROP TABLE chunks; --"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                RetrievalFilters(jurisdiction=bad)
            session = RecordingSession()
            with self.subTest(leg="dense", bad=bad), self.assertRaises(ValueError):
                asyncio.run(dense_search(session, [0.0], None, 5, jurisdiction=bad))
            self.assertEqual(session.statements, [])

    def test_rejects_non_date_as_of(self):
        with self.assertRaises(ValueError):
            RetrievalFilters(as_of="2026-09-27")

    def test_no_filters_means_no_kwargs(self):
        self.assertEqual(RetrievalFilters().as_kwargs(), {})
        self.assertFalse(RetrievalFilters().active)


class ThreadingTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_forwards_filters_to_both_legs(self):
        dense = AsyncMock(return_value=[])
        keyword = AsyncMock(return_value=[])
        with (
            patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
            patch.object(pipeline, "dense_search", dense),
            patch.object(pipeline, "keyword_search", keyword),
            patch.object(pipeline, "rerank", return_value=[]),
        ):
            await pipeline.retrieve(AsyncSession(), "q", "en", jurisdiction="IN-WB", as_of=date(2019, 6, 15))

        for leg in (dense, keyword):
            self.assertEqual(leg.await_args.kwargs, {"jurisdiction": "IN-WB", "as_of": date(2019, 6, 15)})

    async def test_pipeline_passes_no_filter_kwargs_when_unset(self):
        dense = AsyncMock(return_value=[])
        keyword = AsyncMock(return_value=[])
        with (
            patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
            patch.object(pipeline, "dense_search", dense),
            patch.object(pipeline, "keyword_search", keyword),
            patch.object(pipeline, "rerank", return_value=[]),
        ):
            await pipeline.retrieve(AsyncSession(), "q", "en")

        self.assertEqual(dense.await_args.kwargs, {})
        self.assertEqual(keyword.await_args.kwargs, {})

    async def test_pipeline_rejects_bad_jurisdiction_before_embedding(self):
        embed = patch.object(pipeline, "embed_chunks")
        with embed as embedder, self.assertRaises(ValueError):
            await pipeline.retrieve(object(), "q", jurisdiction="bad")
        embedder.assert_not_called()

    async def test_tool_forwards_only_set_filters(self):
        retrieve = AsyncMock(return_value=[])
        with patch.object(tools, "retrieve", retrieve):
            await tools.retrieve_docs_tool(object(), "q", "hi", jurisdiction="IN-KA")
        self.assertEqual(retrieve.await_args.kwargs, {"language": "hi", "jurisdiction": "IN-KA"})

    async def test_graph_node_passes_state_filters(self):
        tool = AsyncMock(return_value=[])
        session = object()
        state = {"query": "q", "language": "bn", "jurisdiction": "IN-WB", "as_of": date(2019, 6, 15)}
        with patch.object(graph, "retrieve_docs_tool", tool):
            await graph.retrieve_docs_node(state, session)
        tool.assert_awaited_once_with(session, "q", "bn", jurisdiction="IN-WB", as_of=date(2019, 6, 15))

    async def test_graph_node_without_filters_keeps_old_call(self):
        tool = AsyncMock(return_value=[])
        session = object()
        with patch.object(graph, "retrieve_docs_tool", tool):
            await graph.retrieve_docs_node({"query": "q", "language": "en"}, session)
        tool.assert_awaited_once_with(session, "q", "en")


class EmptyFilteredRetrievalTests(unittest.TestCase):
    def test_agent_abstains_instead_of_falling_back(self):
        route = RouteDecision(route="retrieve_docs", scheme_name_hint=None)
        retrieve = AsyncMock(return_value=[])
        session = object()
        with (
            patch.object(graph, "generate_structured", side_effect=[route]) as generate,
            patch.object(graph, "retrieve_docs_tool", retrieve),
        ):
            result = asyncio.run(
                graph.run_agent(
                    session, "What did the 2019 transport notification say?", language="en",
                    jurisdiction="IN-WB", as_of=date(2019, 8, 31),
                )
            )

        retrieve.assert_awaited_once_with(
            session, "What did the 2019 transport notification say?", "en", jurisdiction="IN-WB", as_of=date(2019, 8, 31)
        )
        self.assertEqual(retrieve.await_count, 1)
        self.assertEqual([call.kwargs["stage"] for call in generate.call_args_list], ["route_decision"])
        self.assertEqual(result["response_status"], "abstained")
        self.assertEqual(result["citations"], [])


class QueryRequestTests(unittest.TestCase):
    def test_filters_are_optional(self):
        request = QueryRequest(query="helmet fine")
        self.assertIsNone(request.jurisdiction)
        self.assertIsNone(request.as_of)

    def test_accepts_valid_filters(self):
        request = QueryRequest(query="helmet fine", jurisdiction="IN-KA", as_of="2026-09-27")
        self.assertEqual(request.jurisdiction, "IN-KA")
        self.assertEqual(request.as_of, date(2026, 9, 27))

    def test_rejects_invalid_filters(self):
        for payload in (
            {"jurisdiction": "IN-WB-KOL"},
            {"jurisdiction": "wb"},
            {"as_of": "27-09-2026"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                QueryRequest(query="helmet fine", **payload)


if __name__ == "__main__":
    unittest.main()
