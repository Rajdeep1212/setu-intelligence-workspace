import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
