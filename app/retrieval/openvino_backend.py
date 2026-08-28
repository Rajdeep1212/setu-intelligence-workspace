"""Native OpenVINO adapters for SETU's validated FP32 retrieval models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1024
EMBEDDING_MAX_LENGTH = 8192
QUERY_MAX_LENGTH = 192
RERANKER_MAX_LENGTH = 256


def _load_tokenizer(model_dir: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_dir, local_files_only=True)


def _load_compiled_model(model_dir: Path):
    xml_path = model_dir / "openvino_model.xml"
    bin_path = model_dir / "openvino_model.bin"
    if not xml_path.is_file() or not bin_path.is_file():
        raise RuntimeError(
            f"Missing FP32 OpenVINO artifacts in {model_dir}. "
            "Run: docker compose --profile openvino-export run --rm openvino-export"
        )

    try:
        import openvino as ov
    except ImportError as exc:  # pragma: no cover - exercised in production initialization
        raise RuntimeError(
            "OpenVINO backend selected but the openvino runtime is not installed"
        ) from exc

    core = ov.Core()
    model = core.read_model(xml_path)

    floating_constant_types: set[str] = set()
    for operation in model.get_ops():
        if operation.get_type_name() != "Constant":
            continue
        element_type = operation.get_output_element_type(0).get_type_name()
        if element_type.startswith(("f", "bf")):
            floating_constant_types.add(element_type)
    if not floating_constant_types or floating_constant_types != {"f32"}:
        raise RuntimeError(
            f"OpenVINO artifact {model_dir} is not FP32-only: "
            f"floating constants={sorted(floating_constant_types)}"
        )

    compiled = core.compile_model(
        model,
        "CPU",
        {"INFERENCE_PRECISION_HINT": "f32", "PERFORMANCE_HINT": "LATENCY"},
    )
    output = compiled.output(0)
    input_names = {port.get_any_name() for port in compiled.inputs}
    return compiled, output, input_names


def _model_inputs(tokenized: dict[str, Any], input_names: set[str]) -> dict[str, np.ndarray]:
    return {
        name: np.asarray(tokenized[name])
        for name in input_names
        if name in tokenized
    }


class OpenVINOEmbeddingModel:
    """BGE-M3 feature extraction with CLS pooling and L2 normalization."""

    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        self.compiled_model, self.output, self.input_names = _load_compiled_model(
            self.model_dir
        )
        self.tokenizer = _load_tokenizer(self.model_dir)
        logger.info("Initialized local inference backend=openvino model=bge-m3")

    def encode(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            tokenized = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=EMBEDDING_MAX_LENGTH,
                return_tensors="np",
            )
            outputs = self.compiled_model(_model_inputs(tokenized, self.input_names))
            hidden = np.asarray(outputs[self.output], dtype=np.float32)
            if hidden.ndim != 3 or hidden.shape[2] != EMBEDDING_DIMENSION:
                raise RuntimeError(
                    f"Unexpected BGE-M3 output shape {hidden.shape}; expected (*, *, 1024)"
                )
            cls_vectors = hidden[:, 0, :]
            norms = np.linalg.norm(cls_vectors, axis=1, keepdims=True)
            if not np.isfinite(cls_vectors).all() or np.any(norms == 0):
                raise RuntimeError("BGE-M3 produced invalid embedding values")
            vectors.append(cls_vectors / norms)

        return np.concatenate(vectors, axis=0).astype(np.float32).tolist()


def _sigmoid(logits: np.ndarray) -> np.ndarray:
    result = np.empty_like(logits, dtype=np.float32)
    positive = logits >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exponent = np.exp(logits[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


class OpenVINOReranker:
    """BGE reranker preserving FlagEmbedding's production pair semantics."""

    def __init__(self, model_dir: str | Path):
        self.model_dir = Path(model_dir)
        self.compiled_model, self.output, self.input_names = _load_compiled_model(
            self.model_dir
        )
        self.tokenizer = _load_tokenizer(self.model_dir)
        logger.info(
            "Initialized local inference backend=openvino model=bge-reranker-v2-m3"
        )

    def compute_score(
        self, sentence_pairs: list[list[str]], normalize: bool = True
    ) -> float | list[float]:
        if not sentence_pairs:
            return []

        queries = self.tokenizer(
            [pair[0] for pair in sentence_pairs],
            add_special_tokens=False,
            max_length=QUERY_MAX_LENGTH,
            truncation=True,
        )["input_ids"]
        passages = self.tokenizer(
            [pair[1] for pair in sentence_pairs],
            add_special_tokens=False,
            max_length=RERANKER_MAX_LENGTH,
            truncation=True,
        )["input_ids"]
        prepared = [
            self.tokenizer.prepare_for_model(
                query_ids,
                passage_ids,
                truncation="only_second",
                max_length=RERANKER_MAX_LENGTH,
                padding=False,
            )
            for query_ids, passage_ids in zip(queries, passages)
        ]

        length_order = np.argsort([-len(item["input_ids"]) for item in prepared])
        sorted_items = [prepared[index] for index in length_order]
        tokenized = self.tokenizer.pad(
            sorted_items,
            padding=True,
            max_length=RERANKER_MAX_LENGTH,
            return_tensors="np",
        )
        outputs = self.compiled_model(_model_inputs(tokenized, self.input_names))
        sorted_logits = np.asarray(outputs[self.output], dtype=np.float32).reshape(-1)
        sorted_scores = _sigmoid(sorted_logits) if normalize else sorted_logits

        scores = np.empty_like(sorted_scores)
        scores[length_order] = sorted_scores
        values = scores.astype(np.float32).tolist()
        return values[0] if len(values) == 1 else values
