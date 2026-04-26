from __future__ import annotations

import json
import re
import time

from openai import APIConnectionError, APIError, RateLimitError
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.db.models import ChatMessage, ChatSession, DocumentChunk
from backend.app.schemas import SourceItem, StructuredAnswer
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.llm_client import LLMClientFactory
from backend.app.services.vector_store import VectorStore


SYSTEM_PROMPT = """You are a helpful document question-answering assistant.
Answer only from the provided document context.
Do not invent facts, names, numbers, tools, dates, or conclusions not supported by the context.
If the answer is not supported by the context, explicitly say: "I could not find that in the uploaded documents."
Return valid JSON only with this exact shape:
{
  "summary": "short grounded answer",
  "key_points": ["point 1", "point 2"],
  "evidence": ["evidence line with citations like [S1]"],
  "gaps_or_uncertainty": ["what is missing or uncertain"]
}
Use citations like [S1], [S2] inside the evidence strings when possible.
"""


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.client = LLMClientFactory.create()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    def create_chat(self, title: str | None = None) -> ChatSession:
        session = ChatSession(title=title or "New Chat")
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_chats(self) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .options(selectinload(ChatSession.messages))
            .order_by(ChatSession.created_at.desc())
            .all()
        )

    def delete_chat(self, chat_id: int) -> None:
        chat = self.db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if chat is None:
            raise ValueError("Chat session not found.")
        self.db.delete(chat)
        self.db.commit()

    def get_chat(self, chat_id: int) -> ChatSession | None:
        return (
            self.db.query(ChatSession)
            .options(selectinload(ChatSession.messages))
            .filter(ChatSession.id == chat_id)
            .first()
        )

    def ask(
        self,
        chat_id: int,
        question: str,
        top_k: int | None = None,
    ) -> tuple[str, StructuredAnswer, list[SourceItem], list[ChatMessage]]:
        chat = self.get_chat(chat_id)
        if chat is None:
            raise ValueError("Chat session not found.")

        if self.vector_store.index.ntotal == 0 or not self.vector_store.metadata:
            raise ValueError("No documents have been indexed yet. Upload and process at least one document first.")

        user_message = ChatMessage(chat_session_id=chat.id, role="user", content=question)
        self.db.add(user_message)
        self.db.flush()

        query_embedding = self.embedding_service.embed_query(question)
        retrievals = self._retrieve_relevant_chunks(question, query_embedding, top_k or self.settings.top_k_results)
        sources = [SourceItem(**item) for item in retrievals]

        context_blocks = []
        for idx, source in enumerate(sources[: self.settings.max_context_sources], start=1):
            location = f"page {source.page_number}" if source.page_number else "text file"
            context_blocks.append(
                f"[S{idx}] Document: {source.document_name} | Location: {location}\n"
                f"{source.excerpt[: self.settings.max_source_excerpt_chars]}"
            )

        recent_history = chat.messages[-self.settings.chat_history_limit :]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for message in recent_history:
            messages.append({"role": message.role, "content": message.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context:\n{chr(10).join(context_blocks) if context_blocks else 'No relevant sources found.'}\n\n"
                    "Return grounded JSON only. Do not include markdown fences or any extra prose outside the JSON object."
                ),
            }
        )

        raw_answer = self._generate_answer(messages)
        structured_answer = self._parse_structured_answer(raw_answer)
        answer = self._render_structured_answer(structured_answer)

        assistant_message = ChatMessage(chat_session_id=chat.id, role="assistant", content=answer)
        self.db.add(assistant_message)
        self.db.commit()

        refreshed = self.get_chat(chat.id)
        return answer, structured_answer, sources, refreshed.messages if refreshed else [user_message, assistant_message]

    def _retrieve_relevant_chunks(self, question: str, query_embedding: list[float], top_k: int) -> list[dict]:
        candidate_limit = max(top_k * 6, 12)
        vector_hits = self.vector_store.search(query_embedding, candidate_limit)
        lexical_hits = self._lexical_search(question, candidate_limit)
        parent_ids = {item.get("parent_chunk_id", item["chunk_id"]) for item in vector_hits} | {
            item["chunk_id"] for item in lexical_hits
        }
        parent_lookup = self._load_chunk_lookup(parent_ids)

        merged: dict[int, dict] = {}

        for rank, item in enumerate(vector_hits):
            chunk_id = item.get("parent_chunk_id", item["chunk_id"])
            parent = parent_lookup.get(chunk_id)
            if parent is None:
                continue
            merged.setdefault(
                chunk_id,
                {
                    "document_id": parent.document_id,
                    "document_name": parent.document.filename if parent.document else item["document_name"],
                    "chunk_id": chunk_id,
                    "chunk_index": parent.chunk_index,
                    "page_number": parent.page_number,
                    "excerpt": parent.content[:1200],
                    "score": 0.0,
                },
            )
            merged[chunk_id]["score"] += item["score"] + (1.0 / (rank + 1))

        for rank, item in enumerate(lexical_hits):
            chunk_id = item["chunk_id"]
            parent = parent_lookup.get(chunk_id)
            if parent is None:
                continue
            merged.setdefault(
                chunk_id,
                {
                    "document_id": parent.document_id,
                    "document_name": parent.document.filename if parent.document else item["document_name"],
                    "chunk_id": chunk_id,
                    "chunk_index": parent.chunk_index,
                    "page_number": parent.page_number,
                    "excerpt": parent.content[:1200],
                    "score": 0.0,
                },
            )
            merged[chunk_id]["score"] += item["score"] + (1.0 / (rank + 1))

        ranked = self._rerank_parent_hits(question, list(merged.values()))
        return ranked[:top_k]

    def _lexical_search(self, question: str, limit: int) -> list[dict]:
        tokens = self._tokenize(question)
        if not tokens:
            return []

        candidates = self.db.query(DocumentChunk).all()
        scored: list[dict] = []
        for chunk in candidates:
            content = chunk.content.lower()
            token_hits = sum(1 for token in tokens if token in content)
            if token_hits == 0:
                continue

            exact_phrase_bonus = 2 if question.strip().lower() in content else 0
            density_bonus = token_hits / max(len(tokens), 1)
            score = float(token_hits + exact_phrase_bonus + density_bonus)
            scored.append(
                {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document.filename if chunk.document else f"Document {chunk.document_id}",
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "excerpt": chunk.content[:1200],
                    "score": score,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def _load_chunk_lookup(self, chunk_ids: set[int]) -> dict[int, DocumentChunk]:
        if not chunk_ids:
            return {}
        rows = (
            self.db.query(DocumentChunk)
            .options(selectinload(DocumentChunk.document))
            .filter(DocumentChunk.id.in_(chunk_ids))
            .all()
        )
        return {row.id: row for row in rows}

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(token) > 2]

    def _rerank_parent_hits(self, question: str, candidates: list[dict]) -> list[dict]:
        tokens = self._tokenize(question)
        question_text = question.lower().strip()

        for item in candidates:
            content = item["excerpt"].lower()
            exact_phrase_bonus = 3.0 if question_text and question_text in content else 0.0
            token_hits = sum(1 for token in tokens if token in content)
            coverage_bonus = token_hits / max(len(tokens), 1)
            early_match_bonus = 0.5 if any(token in content[:300] for token in tokens) else 0.0
            item["score"] = item["score"] + exact_phrase_bonus + coverage_bonus + early_match_bonus

        return sorted(candidates, key=lambda item: item["score"], reverse=True)

    def _generate_answer(self, messages: list[dict]) -> str:
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                completion = self.client.chat.completions.create(
                    model=self.settings.openai_chat_model,
                    messages=messages,
                    temperature=0.1,
                )
                return completion.choices[0].message.content or "I could not generate a response."
            except RateLimitError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(
                    "The answer model is temporarily rate-limited. Please wait a few seconds and try the question again."
                ) from exc
            except (APIConnectionError, APIError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise RuntimeError(
                    "The answer model is temporarily unavailable. Please try the question again shortly."
                ) from exc

        raise RuntimeError("Answer generation failed.") from last_error

    def _parse_structured_answer(self, raw_answer: str) -> StructuredAnswer:
        cleaned = raw_answer.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            payload = json.loads(cleaned)
            return StructuredAnswer(
                summary=str(payload.get("summary", "")).strip() or "I could not find that in the uploaded documents.",
                key_points=self._coerce_string_list(payload.get("key_points")),
                evidence=self._coerce_string_list(payload.get("evidence")),
                gaps_or_uncertainty=self._coerce_string_list(payload.get("gaps_or_uncertainty")),
            )
        except Exception:
            return self._fallback_structured_answer(cleaned)

    def _fallback_structured_answer(self, text: str) -> StructuredAnswer:
        lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
        summary = lines[0] if lines else "I could not find that in the uploaded documents."
        remainder = lines[1:]
        evidence = [line for line in remainder if "[S" in line][:3]
        key_points = [line for line in remainder if line not in evidence][:3]
        gaps = []
        if "could not find" in text.lower() or "not supported" in text.lower():
            gaps.append("The available context did not fully support a more specific answer.")
        return StructuredAnswer(
            summary=summary,
            key_points=key_points,
            evidence=evidence,
            gaps_or_uncertainty=gaps,
        )

    def _render_structured_answer(self, answer: StructuredAnswer) -> str:
        sections = ["## Summary", answer.summary]
        if answer.key_points:
            sections.append("## Key Points")
            sections.extend(f"- {item}" for item in answer.key_points)
        if answer.evidence:
            sections.append("## Evidence")
            sections.extend(f"- {item}" for item in answer.evidence)
        if answer.gaps_or_uncertainty:
            sections.append("## Gaps or Uncertainty")
            sections.extend(f"- {item}" for item in answer.gaps_or_uncertainty)
        return "\n".join(sections)

    def _coerce_string_list(self, value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
