from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PyPDF2 import PdfReader
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.db.models import Document, DocumentChunk
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.ocr_service import OCRService
from backend.app.services.vector_store import VectorStore
from backend.app.utils.text import chunk_text, clean_text


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.ocr_service = OCRService()
        self.vector_store = VectorStore()

    async def save_upload(self, upload: UploadFile) -> Document:
        content = await upload.read()
        return self.save_upload_bytes(upload.filename or "document", content)

    def save_upload_bytes(
        self,
        filename: str,
        content: bytes,
        progress_callback=None,
    ) -> Document:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF, TXT, MD, PNG, JPG, JPEG, and WEBP files are supported.",
            )

        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        self._notify(progress_callback, "saving", "Saving uploaded file", 0.05)

        safe_name = f"{uuid4().hex}_{Path(filename or 'document').name}"
        file_path = self.settings.upload_dir / safe_name
        file_path.write_bytes(content)

        self._notify(progress_callback, "extracting", "Extracting document text", 0.20)
        full_text, page_map = self._extract_text(file_path, suffix)
        cleaned_text = clean_text(full_text)
        if not cleaned_text:
            raise HTTPException(status_code=400, detail="Could not extract text from the file.")

        document = Document(
            filename=filename or safe_name,
            file_type=suffix.lstrip("."),
            file_path=str(file_path),
            content_preview=cleaned_text[:240],
        )
        self.db.add(document)
        self.db.flush()

        self._notify(progress_callback, "chunking", "Creating parent and child chunks", 0.40)
        parent_chunk_payloads = self._build_parent_chunks(document.id, cleaned_text, page_map)
        parent_chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=item["chunk_index"],
                page_number=item["page_number"],
                content=item["content"],
            )
            for item in parent_chunk_payloads
        ]
        self.db.add_all(parent_chunks)
        self.db.flush()

        try:
            child_payloads = self._build_child_payloads(document, parent_chunks)
            self._notify(progress_callback, "embedding", f"Embedding {len(child_payloads)} retrieval chunks", 0.65)
            embeddings = self.embedding_service.embed_texts([item["content"] for item in child_payloads])
            vector_metadata = [
                {
                    "document_id": item["document_id"],
                    "document_name": item["document_name"],
                    "chunk_id": item["parent_chunk_id"],
                    "chunk_index": item["parent_chunk_index"],
                    "page_number": item["page_number"],
                    "excerpt": item["content"][:400],
                    "parent_chunk_id": item["parent_chunk_id"],
                    "parent_excerpt": item["parent_excerpt"],
                    "child_index": item["child_index"],
                }
                for item in child_payloads
            ]

            if embeddings and self.vector_store.index.d != len(embeddings[0]):
                self._notify(progress_callback, "rebuilding_index", "Rebuilding vector index for the current embedding model", 0.82)
                self._rebuild_vector_index()
            else:
                self._notify(progress_callback, "indexing", "Writing vectors to FAISS", 0.82)
                self.vector_store.add_embeddings(embeddings, vector_metadata)
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Indexing failed while generating embeddings or updating the vector index: {exc}",
            ) from exc

        self.db.commit()
        self.db.refresh(document)
        self._notify(progress_callback, "completed", "Document indexed", 1.0)
        return document

    def list_documents(self) -> list[Document]:
        return self.db.query(Document).order_by(Document.created_at.desc()).all()

    def delete_document(self, document_id: int) -> None:
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            raise ValueError("Document not found.")

        file_path = Path(document.file_path)
        self.db.delete(document)
        self.db.commit()

        if file_path.exists():
            file_path.unlink(missing_ok=True)

        self._rebuild_vector_index()

    def _extract_text(self, file_path: Path, suffix: str) -> tuple[str, list[tuple[int | None, str]]]:
        if suffix == ".pdf":
            return self._extract_pdf_text(file_path)

        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            try:
                text = self.ocr_service.extract_text_from_image_file(file_path)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            cleaned = clean_text(text)
            return cleaned, [(None, cleaned)]

        text = file_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_text(text)
        return cleaned, [(None, cleaned)]

    def _extract_pdf_text(self, file_path: Path) -> tuple[str, list[tuple[int | None, str]]]:
        reader = PdfReader(str(file_path))
        pages: list[tuple[int | None, str]] = []
        merged: list[str] = []

        for index, page in enumerate(reader.pages, start=1):
            extracted_text = clean_text(page.extract_text() or "")
            if len(extracted_text) < self.settings.ocr_min_text_length:
                try:
                    image_bytes = self.ocr_service.render_pdf_page_to_png(file_path, index - 1)
                    ocr_text = clean_text(self.ocr_service.extract_text_from_image(image_bytes, "image/png"))
                    page_text = ocr_text or extracted_text
                except RuntimeError:
                    page_text = extracted_text
            else:
                page_text = extracted_text

            if page_text:
                pages.append((index, page_text))
                merged.append(page_text)

        return "\n".join(merged), pages

    def _build_parent_chunks(
        self,
        document_id: int,
        text: str,
        page_map: list[tuple[int | None, str]],
    ) -> list[dict]:
        parent_chunks: list[dict] = []
        global_index = 0

        if len(page_map) == 1 and page_map[0][0] is None:
            for chunk in chunk_text(text, self.settings.parent_chunk_size, self.settings.parent_chunk_overlap):
                parent_chunks.append(
                    {
                        "document_id": document_id,
                        "chunk_index": global_index,
                        "page_number": None,
                        "content": chunk,
                    }
                )
                global_index += 1
            return parent_chunks

        for page_number, page_text in page_map:
            for chunk in chunk_text(page_text, self.settings.parent_chunk_size, self.settings.parent_chunk_overlap):
                parent_chunks.append(
                    {
                        "document_id": document_id,
                        "chunk_index": global_index,
                        "page_number": page_number,
                        "content": chunk,
                    }
                )
                global_index += 1

        return parent_chunks

    def _build_child_payloads(self, document: Document, parent_chunks: list[DocumentChunk]) -> list[dict]:
        child_payloads: list[dict] = []
        for parent_chunk in parent_chunks:
            child_chunks = chunk_text(
                parent_chunk.content,
                self.settings.child_chunk_size,
                self.settings.child_chunk_overlap,
            )
            if not child_chunks:
                child_chunks = [parent_chunk.content]

            for child_index, child_content in enumerate(child_chunks):
                child_payloads.append(
                    {
                        "document_id": document.id,
                        "document_name": document.filename,
                        "parent_chunk_id": parent_chunk.id,
                        "parent_chunk_index": parent_chunk.chunk_index,
                        "page_number": parent_chunk.page_number,
                        "parent_excerpt": parent_chunk.content[:1200],
                        "child_index": child_index,
                        "content": child_content,
                    }
                )

        return child_payloads

    def _rebuild_vector_index(self) -> None:
        all_chunks = (
            self.db.query(DocumentChunk)
            .options(selectinload(DocumentChunk.document))
            .order_by(DocumentChunk.id.asc())
            .all()
        )
        if not all_chunks:
            self.vector_store.reset(self.vector_store.index.d)
            return

        child_payloads: list[dict] = []
        for chunk in all_chunks:
            child_chunks = chunk_text(
                chunk.content,
                self.settings.child_chunk_size,
                self.settings.child_chunk_overlap,
            )
            if not child_chunks:
                child_chunks = [chunk.content]

            for child_index, child_content in enumerate(child_chunks):
                child_payloads.append(
                    {
                        "document_id": chunk.document_id,
                        "document_name": chunk.document.filename if chunk.document else f"Document {chunk.document_id}",
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "excerpt": child_content[:400],
                        "parent_chunk_id": chunk.id,
                        "parent_excerpt": chunk.content[:1200],
                        "child_index": child_index,
                        "content": child_content,
                    }
                )

        embeddings = self.embedding_service.embed_texts([item["content"] for item in child_payloads])
        metadata = [
            {
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "chunk_id": item["chunk_id"],
                "chunk_index": item["chunk_index"],
                "page_number": item["page_number"],
                "excerpt": item["excerpt"],
                "parent_chunk_id": item["parent_chunk_id"],
                "parent_excerpt": item["parent_excerpt"],
                "child_index": item["child_index"],
            }
            for item in child_payloads
        ]
        self.vector_store.replace_embeddings(embeddings, metadata)

    def _notify(self, progress_callback, stage: str, message: str, progress: float) -> None:
        if progress_callback is not None:
            progress_callback(stage=stage, message=message, progress=progress)
