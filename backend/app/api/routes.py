from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.database import SessionLocal
from app.schemas import (
    AskRequest,
    AskResponse,
    ChatSessionCreate,
    ChatSessionRead,
    DocumentRead,
    HealthResponse,
    IndexJobCreated,
    IndexJobStatus,
)
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.indexing_jobs import job_store


router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentRead]:
    return DocumentService(db).list_documents()


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        DocumentService(db).delete_document(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/documents/upload", response_model=list[DocumentRead])
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    service = DocumentService(db)
    documents = []
    for upload in files:
        documents.append(await service.save_upload(upload))
    return documents


@router.post("/documents/upload-async", response_model=IndexJobCreated)
async def upload_documents_async(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> IndexJobCreated:
    payloads = []
    filenames = []
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "document"
        payloads.append((filename, content))
        filenames.append(filename)

    job = job_store.create_job(filenames)
    background_tasks.add_task(_process_index_job, job.id, payloads)
    return IndexJobCreated(job_id=job.id, status=job.status)


@router.get("/documents/upload-jobs/{job_id}", response_model=IndexJobStatus)
def get_upload_job(job_id: str) -> IndexJobStatus:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job not found.")
    return IndexJobStatus(job_id=job["id"], **{key: value for key, value in job.items() if key != "id"})


@router.get("/chats", response_model=list[ChatSessionRead])
def list_chats(db: Session = Depends(get_db)) -> list[ChatSessionRead]:
    return ChatService(db).list_chats()


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        ChatService(db).delete_chat(chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/chats", response_model=ChatSessionRead)
def create_chat(payload: ChatSessionCreate, db: Session = Depends(get_db)) -> ChatSessionRead:
    return ChatService(db).create_chat(payload.title)


@router.get("/chats/{chat_id}", response_model=ChatSessionRead)
def get_chat(chat_id: int, db: Session = Depends(get_db)) -> ChatSessionRead:
    chat = ChatService(db).get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


@router.post("/chats/{chat_id}/ask", response_model=AskResponse)
def ask_question(chat_id: int, payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    try:
        answer, structured_answer, sources, messages = ChatService(db).ask(chat_id, payload.question, payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return AskResponse(answer=answer, structured_answer=structured_answer, sources=sources, messages=messages)


def _process_index_job(job_id: str, payloads: list[tuple[str, bytes]]) -> None:
    db = SessionLocal()
    try:
        service = DocumentService(db)
        job_store.update_job(job_id, status="running", stage="starting", progress=0.02, message="Starting indexing")

        total = max(len(payloads), 1)
        for file_number, (filename, content) in enumerate(payloads, start=1):
            base_progress = (file_number - 1) / total
            span = 1.0 / total

            def callback(stage: str, message: str, progress: float) -> None:
                job_store.update_job(
                    job_id,
                    status="running",
                    stage=stage,
                    progress=min(base_progress + (progress * span), 0.98),
                    message=f"{filename}: {message}",
                    documents_indexed=file_number - 1,
                )

            service.save_upload_bytes(filename, content, progress_callback=callback)
            job_store.update_job(
                job_id,
                status="running",
                stage="file_complete",
                progress=min(file_number / total, 0.99),
                message=f"{filename}: Indexed successfully",
                documents_indexed=file_number,
            )

        job_store.update_job(
            job_id,
            status="completed",
            stage="completed",
            progress=1.0,
            message="All documents indexed",
            documents_indexed=len(payloads),
        )
    except HTTPException as exc:
        db.rollback()
        job_store.update_job(
            job_id,
            status="failed",
            stage="failed",
            error=str(exc.detail),
            message=str(exc.detail),
        )
    except Exception as exc:
        db.rollback()
        job_store.update_job(
            job_id,
            status="failed",
            stage="failed",
            error=str(exc),
            message=f"Indexing failed: {exc}",
        )
    finally:
        db.close()
