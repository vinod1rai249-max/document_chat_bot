# Document Chatbot App

An original, from-scratch document chatbot built with:

- `Streamlit` for the user interface
- `FastAPI` for the backend API
- `SQLite` for persistent app data
- `FAISS` for vector retrieval
- an `OpenAI-compatible API` for chat, embeddings, and optional vision OCR

## Overview

This app lets users:

- upload PDF, text, markdown, and image-based note files
- extract and index document content
- search documents with hierarchical hybrid RAG
- ask grounded questions with structured answers
- inspect source evidence for every answer
- keep chat history across sessions
- delete stored documents and chat sessions from the UI

## Architecture

The retrieval pipeline is not simple chunk-only RAG. It uses:

- OCR-aware ingestion for scans, notes, and images
- parent-child chunking for stronger recall and answer context
- hybrid retrieval using vector plus lexical search
- reranked parent contexts before answer generation
- structured response formatting with evidence and uncertainty sections

## Project Structure

```text
.
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   └── models.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── chat_service.py
│       │   ├── document_service.py
│       │   ├── embedding_service.py
│       │   ├── indexing_jobs.py
│       │   ├── llm_client.py
│       │   ├── ocr_service.py
│       │   └── vector_store.py
│       ├── utils/
│       │   ├── __init__.py
│       │   └── text.py
│       ├── main.py
│       └── schemas.py
├── frontend/
│   └── app.py
├── tests/
│   └── test_text_utils.py
├── .env.example
├── .gitignore
├── .python-version
├── main.py
├── pyproject.toml
├── README.md
├── requirements.txt
├── uv.lock
└── vercel.json
```

## Features

- Upload `PDF`, `TXT`, `MD`, `PNG`, `JPG`, `JPEG`, and `WEBP` files
- OCR support for scanned and handwritten-style documents
- Asynchronous indexing with visible progress updates
- Hierarchical parent-child retrieval for better document grounding
- Structured answers with:
  - summary
  - key points
  - evidence
  - gaps or uncertainty
- Source snippets and retrieval relevance display
- Chat history persistence
- Delete actions for stored documents and chat sessions
- Premium Streamlit UI styling

## Runtime Storage

The app stores runtime data under:

- `backend/storage/app.db` for SQLite
- `backend/storage/uploads/` for uploaded files
- `backend/storage/vector/` for FAISS index files

These runtime files are intentionally ignored by Git.

## Environment Setup

1. Create a virtual environment
2. Install dependencies
3. Copy `.env.example` to `.env`
4. Fill in your provider and model settings

Example:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run Locally

Start the FastAPI backend:

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the Streamlit frontend in a second terminal:

```powershell
streamlit run frontend/app.py
```

App URLs:

- Frontend: `http://localhost:8501`
- Backend docs: `http://127.0.0.1:8000/docs`

## API Endpoints

- `GET /api/health`
- `GET /api/documents`
- `DELETE /api/documents/{document_id}`
- `POST /api/documents/upload`
- `POST /api/documents/upload-async`
- `GET /api/documents/upload-jobs/{job_id}`
- `GET /api/chats`
- `POST /api/chats`
- `GET /api/chats/{chat_id}`
- `DELETE /api/chats/{chat_id}`
- `POST /api/chats/{chat_id}/ask`

## Deployment Split

This repo is best deployed as two separate services:

### 1. FastAPI backend on Vercel

The repo already includes:

- `main.py` at the repo root exporting the FastAPI app
- `vercel.json` pointing Vercel to that entrypoint

For Vercel:

1. Import the GitHub repo
2. Let Vercel detect Python
3. Set backend environment variables from `.env.example`
4. Deploy the API

Important:

- Vercel is only for the backend API in this setup
- SQLite and local FAISS storage are okay for testing, but not ideal for serious production workloads on serverless platforms

### 2. Streamlit frontend on Streamlit Community Cloud

For Streamlit Community Cloud:

1. Create a new app from this GitHub repo
2. Set the app file path to:

```text
frontend/app.py
```

3. Add frontend environment variables or secrets
4. Set:

```text
STREAMLIT_API_URL=https://your-vercel-backend-url
```

This makes the Streamlit UI call the deployed FastAPI backend instead of localhost.

## Recommended Hosted Setup Notes

If you deploy the frontend and backend separately:

- keep `STREAMLIT_API_URL` pointed at your backend URL
- make sure CORS stays enabled on the backend
- keep `.env` local and never commit it
- prefer hosted databases/vector stores later if you move beyond MVP testing

## Testing

Run the included test file:

```powershell
pytest
```

Suggested manual verification:

1. Start backend and frontend
2. Upload one typed PDF and one image-based note
3. Process files and watch indexing progress
4. Ask a direct factual question from the document
5. Confirm the answer includes structured output and sources
6. Delete a document and verify it disappears from the sidebar
7. Delete a chat and verify it no longer appears in history

## Configuration Notes

- `OPENAI_BASE_URL` can point to OpenAI, OpenRouter, Ollama-compatible services, or another compatible provider
- `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, and `OPENAI_VISION_MODEL` should be chosen carefully to match your provider capabilities
- `EMBEDDING_DIMENSION` must match the actual embedding model output dimension
- `PARENT_CHUNK_SIZE`, `PARENT_CHUNK_OVERLAP`, `CHILD_CHUNK_SIZE`, and `CHILD_CHUNK_OVERLAP` control hierarchical retrieval behavior
- `TESSERACT_CMD` is optional and only needed when using local Tesseract OCR on Windows
- `STREAMLIT_API_URL` controls where the frontend sends API requests

## Git Safety

- `.env` is ignored and is not committed
- `.env.example` is included so the project can be configured safely on another machine

## Current Cleanup Note

The root-level `main.py` is now intentionally part of the project because it is used as the Vercel FastAPI entrypoint.
