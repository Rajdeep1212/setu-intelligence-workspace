"""Backend-selecting query embedding adapter."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from ingestion.embeddings import embed_chunks as _pytorch_embed_chunks

logger = logging.getLogger(__name__)
_openvino_model = None
_pytorch_logged = False


def _get_openvino_model():
    global _openvino_model
    if _openvino_model is None:
        from app.retrieval.openvino_backend import OpenVINOEmbeddingModel

        model_dir = Path(settings.openvino_model_dir) / "bge-m3"
        _openvino_model = OpenVINOEmbeddingModel(model_dir)
    return _openvino_model


def embed_chunks(chunks: list[str], batch_size: int = 16) -> list[list[float]]:
    global _pytorch_logged
    if not chunks:
        return []
    if settings.local_inference_backend == "pytorch":
        if not _pytorch_logged:
            logger.info("Initialized local inference backend=pytorch model=bge-m3")
            _pytorch_logged = True
        return _pytorch_embed_chunks(chunks, batch_size=batch_size)
    return _get_openvino_model().encode(chunks, batch_size=batch_size)
