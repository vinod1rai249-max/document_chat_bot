from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: int
    filename: str
    file_type: str
    content_preview: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceItem(BaseModel):
    document_id: int
    document_name: str
    chunk_id: int
    chunk_index: int
    page_number: int | None = None
    excerpt: str
    score: float


class StructuredAnswer(BaseModel):
    summary: str
    key_points: list[str] = []
    evidence: list[str] = []
    gaps_or_uncertainty: list[str] = []


class MessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None)


class ChatSessionRead(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: list[MessageRead] = []

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=10)


class AskResponse(BaseModel):
    answer: str
    structured_answer: StructuredAnswer
    sources: list[SourceItem]
    messages: list[MessageRead]


class HealthResponse(BaseModel):
    status: str


class IndexJobCreated(BaseModel):
    job_id: str
    status: str


class IndexJobStatus(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: float
    message: str
    documents_indexed: int
    total_files: int
    filenames: list[str]
    error: str | None = None
