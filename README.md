# Document Chatbot App

An original from-scratch document chatbot implementation using:

- Frontend: Streamlit
- Backend: FastAPI
- Database: SQLite
- Vector search: FAISS
- LLM API: OpenAI-compatible client

## Folder Structure

```text
.
├── backend
│   └── app
│       ├── api
│       │   └── routes.py
│       ├── core
│       │   └── config.py
│       ├── db
│       │   ├── database.py
│       │   └── models.py
│       ├── services
│       │   ├── chat_service.py
│       │   ├── document_service.py
│       │   ├── embedding_service.py
│       │   ├── llm_client.py
│       │   └── vector_store.py
│       ├── utils
│       │   └── text.py
│       ├── main.py
│       └── schemas.py
├── frontend
│   └── app.py
├── tests
│   └── test_text_utils.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Features

- Upload PDF, TXT, and Markdown documents
- Upload handwritten note images such as PNG and JPG
- Persist document metadata and chat history in SQLite
- Build hierarchical parent and child chunks for retrieval
- Retrieve child chunks in FAISS and answer from reranked parent contexts
- Show indexing progress while documents are being processed
- Generate answers with an OpenAI-compatible chat model
- Display source snippets with each answer
- Maintain multi-session chat history

## Database Setup

The database is created automatically on backend startup at:

```text
backend/storage/app.db
```

No manual migration step is required for the MVP.

## Environment Setup

1. Create a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Fill in your OpenAI-compatible API values.

Example:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run Instructions

Start the FastAPI backend:

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start the Streamlit frontend:

```powershell
streamlit run frontend/app.py
```

Frontend default URL:

```text
http://localhost:8501
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

- `GET /api/health`
- `GET /api/documents`
- `POST /api/documents/upload`
- `GET /api/chats`
- `POST /api/chats`
- `GET /api/chats/{chat_id}`
- `POST /api/chats/{chat_id}/ask`

## Testing Steps

1. Run `pytest` for the included utility smoke tests.
2. Start the backend and open `/docs` to verify the API boots successfully.
3. Start Streamlit and upload one PDF or TXT file.
4. Ask a question that is explicitly answered in the document.
5. Confirm the response includes source snippets and that the chat appears in the sidebar history.
6. Refresh the frontend and verify the existing chat session can still be reopened.

## Notes

- `faiss-cpu` may take a little longer to install on Windows.
- If you use a non-OpenAI provider, point `OPENAI_BASE_URL` to that provider's compatible endpoint.
- Handwritten notes and scanned PDFs use OCR through the configured `OPENAI_VISION_MODEL`, so that model must support image input.
- If the vision API is unavailable, the app can fall back to local OCR with Tesseract. Install Tesseract locally and optionally set `TESSERACT_CMD` in `.env` on Windows.
- Retrieval quality can be tuned with `PARENT_CHUNK_SIZE`, `PARENT_CHUNK_OVERLAP`, `CHILD_CHUNK_SIZE`, `CHILD_CHUNK_OVERLAP`, and `TOP_K_RESULTS`.
