import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from app.retrieval.openvino_backend import (
    EMBEDDING_DIMENSION,
    OpenVINOEmbeddingModel,
    OpenVINOReranker,
)


OUTPUT = object()


class EmbeddingTokenizer:
    def __call__(self, texts, **kwargs):
        batch = len(texts)
        return {
            "input_ids": np.ones((batch, 2), dtype=np.int64),
            "attention_mask": np.ones((batch, 2), dtype=np.int64),
        }


class EmbeddingCompiledModel:
    def __call__(self, inputs):
        batch = inputs["input_ids"].shape[0]
        hidden = np.zeros((batch, 2, EMBEDDING_DIMENSION), dtype=np.float32)
        hidden[:, 0, 0] = 3.0
        hidden[:, 0, 1] = 4.0
        return {OUTPUT: hidden}


class RerankerTokenizer:
    def __call__(self, texts, **kwargs):
        return {"input_ids": [list(range(1, len(text.split()) + 1)) for text in texts]}

    def prepare_for_model(self, query_ids, passage_ids, **kwargs):
        input_ids = [0, *query_ids, 2, 2, *passage_ids, 2]
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids)}

    def pad(self, items, **kwargs):
        width = max(len(item["input_ids"]) for item in items)
        ids = [item["input_ids"] + [1] * (width - len(item["input_ids"])) for item in items]
        masks = [item["attention_mask"] + [0] * (width - len(item["attention_mask"])) for item in items]
        return {
            "input_ids": np.asarray(ids, dtype=np.int64),
            "attention_mask": np.asarray(masks, dtype=np.int64),
        }


class RerankerCompiledModel:
    def __call__(self, inputs):
        self.last_inputs = inputs
        return {OUTPUT: np.asarray([[2.0], [-2.0]], dtype=np.float32)}


class OpenVINOAdapterTests(unittest.TestCase):
    def test_embedding_contract_and_normalization(self):
        with (
            patch(
                "app.retrieval.openvino_backend._load_tokenizer",
                return_value=EmbeddingTokenizer(),
            ),
            patch(
                "app.retrieval.openvino_backend._load_compiled_model",
                return_value=(
                    EmbeddingCompiledModel(),
                    OUTPUT,
                    {"input_ids", "attention_mask"},
                ),
            ),
        ):
            model = OpenVINOEmbeddingModel("unused")
            vectors = model.encode(["one", "two"], batch_size=2)

        self.assertEqual(len(vectors), 2)
        self.assertTrue(all(len(vector) == EMBEDDING_DIMENSION for vector in vectors))
        self.assertTrue(all(isinstance(value, float) for value in vectors[0]))
        self.assertAlmostEqual(float(np.linalg.norm(vectors[0])), 1.0, places=6)
        self.assertAlmostEqual(vectors[0][0], 0.6, places=6)
        self.assertAlmostEqual(vectors[0][1], 0.8, places=6)

    def test_reranker_contract_sigmoid_and_original_order(self):
        compiled = RerankerCompiledModel()
        with (
            patch(
                "app.retrieval.openvino_backend._load_tokenizer",
                return_value=RerankerTokenizer(),
            ),
            patch(
                "app.retrieval.openvino_backend._load_compiled_model",
                return_value=(compiled, OUTPUT, {"input_ids", "attention_mask"}),
            ),
        ):
            reranker = OpenVINOReranker("unused")
            scores = reranker.compute_score(
                [["query", "short"], ["query", "a much longer passage"]],
                normalize=True,
            )

        self.assertEqual(len(scores), 2)
        self.assertLess(scores[0], scores[1])
        self.assertAlmostEqual(scores[0], 0.1192029, places=6)
        self.assertAlmostEqual(scores[1], 0.8807971, places=6)
        self.assertLessEqual(compiled.last_inputs["input_ids"].shape[1], 256)

    def test_public_reranker_orders_and_shapes_candidates(self):
        fake = Mock()
        fake.compute_score.return_value = [0.1, 0.9]
        candidates = [
            {"id": "low", "content": "low"},
            {"id": "high", "content": "high"},
        ]
        with patch("app.retrieval.rerank._get_reranker", return_value=fake):
            from app.retrieval.rerank import rerank

            results = rerank("query", candidates, top_k=1)

        self.assertEqual([item["id"] for item in results], ["high"])
        self.assertEqual(results[0]["rerank_score"], 0.9)
        fake.compute_score.assert_called_once_with(
            [["query", "low"], ["query", "high"]], normalize=True
        )

    def test_missing_artifacts_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Missing FP32 OpenVINO artifacts"):
                OpenVINOEmbeddingModel(Path(directory))


class BackendSelectionTests(unittest.TestCase):
    def test_retrieval_releases_database_before_cpu_reranking(self):
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.retrieval import pipeline

        session = AsyncSession()
        candidates = [{"id": "one", "content": "supported passage"}]

        async def read_candidates(*_args, **_kwargs):
            self.assertTrue(session.in_transaction())
            return candidates

        def rerank_after_release(*_args, **_kwargs):
            self.assertFalse(session.in_transaction())
            return candidates

        with (
            patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
            patch.object(pipeline, "dense_search", AsyncMock(side_effect=read_candidates)),
            patch.object(pipeline, "keyword_search", AsyncMock(return_value=[])),
            patch.object(pipeline, "rerank", side_effect=rerank_after_release) as reranker,
        ):
            result = asyncio.run(pipeline.retrieve(session, "query"))

        self.assertEqual(result, candidates)
        self.assertFalse(session.in_transaction())
        reranker.assert_called_once()

    def test_retrieval_preserves_caller_pending_writes(self):
        from sqlalchemy import Integer
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import DeclarativeBase, mapped_column

        from app.retrieval import pipeline

        class Base(DeclarativeBase):
            pass

        class PendingWrite(Base):
            __tablename__ = "pending_write"
            id = mapped_column(Integer, primary_key=True)

        async def exercise():
            async with AsyncSession() as session:
                pending = PendingWrite(id=1)
                session.add(pending)
                with (
                    patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
                    patch.object(pipeline, "dense_search", AsyncMock(return_value=[])),
                    patch.object(pipeline, "keyword_search", AsyncMock(return_value=[])),
                    patch.object(pipeline, "rerank", return_value=[]),
                ):
                    await pipeline.retrieve(session, "query")
                self.assertIn(pending, session.new)
                self.assertTrue(session.in_transaction())

        asyncio.run(exercise())

    def test_retrieval_preserves_explicit_caller_transaction(self):
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.retrieval import pipeline

        async def exercise():
            async with AsyncSession() as session, session.begin():
                original = session.get_transaction()

                def rerank_in_caller_transaction(*_args, **_kwargs):
                    self.assertIs(session.get_transaction(), original)
                    self.assertTrue(original.is_active)
                    return []

                with (
                    patch.object(pipeline, "embed_chunks", return_value=[[0.0]]),
                    patch.object(pipeline, "dense_search", AsyncMock(return_value=[])),
                    patch.object(pipeline, "keyword_search", AsyncMock(return_value=[])),
                    patch.object(pipeline, "rerank", side_effect=rerank_in_caller_transaction),
                ):
                    await pipeline.retrieve(session, "query")
                self.assertIs(session.get_transaction(), original)

        asyncio.run(exercise())

    def test_failure_and_cancellation_respect_transaction_ownership(self):
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.errors import DatabaseUnavailableError, RetrievalUnavailableError
        from app.retrieval import pipeline

        async def exercise(caller_owned, stage, failure_kind):
            async with AsyncSession() as session:
                original = await session.begin() if caller_owned else None
                errors = {
                    "cancelled": (asyncio.CancelledError(), asyncio.CancelledError),
                    "runtime": (RuntimeError("fixture"), RetrievalUnavailableError),
                    "database": (OperationalError("fixture", {}, Exception("fixture")), DatabaseUnavailableError),
                }
                error, expected = errors[failure_kind]
                mocks = {
                    "embed_chunks": Mock(return_value=[[0.0]]),
                    "dense_search": AsyncMock(return_value=[]),
                    "keyword_search": AsyncMock(return_value=[]),
                    "rerank": Mock(return_value=[]),
                }
                mocks[stage].side_effect = error
                with patch.multiple(pipeline, **mocks):
                    with self.assertRaises(expected):
                        await pipeline.retrieve(session, "query")
                self.assertEqual(session.in_transaction(), caller_owned)
                if caller_owned:
                    self.assertIs(session.get_transaction(), original)
                    self.assertTrue(original.is_active)

        for caller_owned in (False, True):
            for stage in ("embed_chunks", "dense_search", "keyword_search", "rerank"):
                kinds = ("runtime", "cancelled", "database") if stage in ("dense_search", "keyword_search") else ("runtime", "cancelled")
                for failure_kind in kinds:
                    with self.subTest(caller_owned=caller_owned, stage=stage, failure_kind=failure_kind):
                        asyncio.run(exercise(caller_owned, stage, failure_kind))

    def test_pytorch_selection_preserves_contract(self):
        from app.retrieval import embeddings

        expected = [[1.0] * EMBEDDING_DIMENSION]
        with (
            patch.object(embeddings.settings, "local_inference_backend", "pytorch"),
            patch.object(embeddings, "_pytorch_embed_chunks", return_value=expected) as backend,
        ):
            actual = embeddings.embed_chunks(["query"], batch_size=4)

        self.assertIs(actual, expected)
        backend.assert_called_once_with(["query"], batch_size=4)

    def test_openvino_selection_preserves_contract(self):
        from app.retrieval import embeddings

        expected = [[1.0] * EMBEDDING_DIMENSION]
        model = Mock()
        model.encode.return_value = expected
        with (
            patch.object(embeddings.settings, "local_inference_backend", "openvino"),
            patch.object(embeddings, "_get_openvino_model", return_value=model),
        ):
            actual = embeddings.embed_chunks(["query"], batch_size=4)

        self.assertIs(actual, expected)
        model.encode.assert_called_once_with(["query"], batch_size=4)


if __name__ == "__main__":
    unittest.main()
