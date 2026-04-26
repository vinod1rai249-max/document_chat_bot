from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from backend.app.core.config import get_settings


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.index_path = Path(self.settings.vector_index_dir) / "chunks.faiss"
        self.metadata_path = Path(self.settings.vector_index_dir) / "chunks_metadata.json"
        self.index = self._load_or_create_index()
        self.metadata = self._load_metadata()

    def _load_or_create_index(self) -> faiss.IndexFlatL2:
        if self.index_path.exists():
            return faiss.read_index(str(self.index_path))
        return faiss.IndexFlatL2(self.settings.embedding_dimension)

    def _load_metadata(self) -> list[dict]:
        if self.metadata_path.exists():
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        return []

    def save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def add_embeddings(self, embeddings: list[list[float]], metadata_items: list[dict]) -> None:
        if not embeddings:
            return
        vectors = np.array(embeddings, dtype="float32")
        self.ensure_dimension(vectors.shape[1])
        self.index.add(vectors)
        self.metadata.extend(metadata_items)
        self.save()

    def replace_embeddings(self, embeddings: list[list[float]], metadata_items: list[dict]) -> None:
        if not embeddings:
            self.reset(self.settings.embedding_dimension)
            return
        vectors = np.array(embeddings, dtype="float32")
        self.reset(vectors.shape[1])
        self.index.add(vectors)
        self.metadata = list(metadata_items)
        self.save()

    def search(self, query_embedding: list[float], top_k: int) -> list[dict]:
        if not self.metadata or self.index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype="float32")
        if query.shape[1] != self.index.d:
            return []
        distances, indices = self.index.search(query, top_k)
        results: list[dict] = []

        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(self._normalize_score(float(score)))
            results.append(item)

        return results

    def _normalize_score(self, raw_score: float) -> float:
        if self.index.metric_type == faiss.METRIC_INNER_PRODUCT:
            return raw_score
        return 1.0 / (1.0 + max(raw_score, 0.0))

    def ensure_dimension(self, dimension: int) -> None:
        if self.index.d != dimension:
            self.reset(dimension)

    def reset(self, dimension: int) -> None:
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata = []
        self.save()
