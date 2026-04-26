from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.services.llm_client import LLMClientFactory


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = LLMClientFactory.create()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        batch_size = max(self.settings.embedding_batch_size, 1)

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = self.client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=batch,
            )
            embeddings.extend(item.embedding for item in response.data)

        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
