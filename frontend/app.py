from __future__ import annotations

import os
import time
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

API_URL = os.getenv("STREAMLIT_API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Doc Chat Studio", page_icon=":page_facing_up:", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Manrope', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(191, 219, 254, 0.55), transparent 28%),
                radial-gradient(circle at top right, rgba(251, 191, 36, 0.18), transparent 24%),
                linear-gradient(180deg, #f7f8fc 0%, #eef2ff 100%);
            color: #10233f;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(241,245,255,0.97) 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.22);
        }

        .hero-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(29, 78, 216, 0.90));
            border: 1px solid rgba(147, 197, 253, 0.22);
            border-radius: 26px;
            padding: 28px 30px 24px 30px;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
            color: white;
            margin-bottom: 22px;
        }

        .hero-kicker {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: rgba(191, 219, 254, 0.9);
            margin-bottom: 12px;
            font-weight: 700;
        }

        .hero-title {
            font-size: 3rem;
            line-height: 1.02;
            font-weight: 800;
            margin: 0;
            color: #ffffff;
        }

        .hero-copy {
            margin-top: 14px;
            font-size: 1rem;
            color: rgba(226, 232, 240, 0.96);
            max-width: 760px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin: 18px 0 10px 0;
        }

        .stat-card {
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 14px 16px;
            backdrop-filter: blur(8px);
        }

        .stat-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: rgba(191, 219, 254, 0.88);
            margin-bottom: 6px;
            font-weight: 700;
        }

        .stat-value {
            font-size: 1.3rem;
            font-weight: 800;
            color: #fff;
        }

        .panel-card {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 22px;
            padding: 18px 18px 8px 18px;
            box-shadow: 0 20px 50px rgba(30, 41, 59, 0.08);
            margin-bottom: 16px;
        }

        .section-eyebrow {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #3157d5;
            font-weight: 800;
            margin-bottom: 6px;
        }

        .section-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #10233f;
            margin-bottom: 4px;
        }

        .section-copy {
            color: #475569;
            font-size: 0.95rem;
            margin-bottom: 0;
        }

        .doc-card, .chat-card {
            background: rgba(248, 250, 252, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 12px 12px 10px 12px;
            margin-bottom: 10px;
        }

        .doc-title, .chat-title {
            font-weight: 800;
            color: #10233f;
            margin-bottom: 4px;
        }

        .doc-meta, .chat-meta {
            color: #64748b;
            font-size: 0.86rem;
            line-height: 1.45;
        }

        div[data-testid="stChatMessage"] {
            background: rgba(255,255,255,0.74);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 22px;
            box-shadow: 0 12px 30px rgba(30, 41, 59, 0.06);
            padding: 8px 10px;
            margin-bottom: 12px;
        }

        .stButton > button {
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.24);
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            color: #10233f;
            font-weight: 700;
        }

        .stButton > button:hover {
            border-color: rgba(49, 87, 213, 0.45);
            color: #1d4ed8;
        }

        .danger-button > button {
            background: linear-gradient(180deg, #fff5f5 0%, #ffe4e6 100%);
            color: #b42318;
            border-color: rgba(244, 63, 94, 0.18);
        }

        .soft-pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.18);
            border: 1px solid rgba(255,255,255,0.14);
            font-size: 0.82rem;
            color: #eff6ff;
            margin-right: 8px;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def api_get(path: str) -> Any:
    try:
        response = httpx.get(f"{API_URL}{path}", timeout=60.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        st.error(f"Backend request failed: {exc}")
        st.stop()


def api_post(path: str, json: dict | None = None, files: list[tuple[str, tuple]] | None = None) -> Any:
    try:
        response = httpx.post(f"{API_URL}{path}", json=json, files=files, timeout=120.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            try:
                payload = exc.response.json()
                detail = payload.get("detail", payload)
            except Exception:
                detail = exc.response.text
            st.error(f"Backend request failed: {detail}")
        else:
            st.error(f"Backend request failed: {exc}")
        st.stop()


def api_delete(path: str) -> Any:
    try:
        response = httpx.delete(f"{API_URL}{path}", timeout=60.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            try:
                payload = exc.response.json()
                detail = payload.get("detail", payload)
            except Exception:
                detail = exc.response.text
            st.error(f"Backend request failed: {detail}")
        else:
            st.error(f"Backend request failed: {exc}")
        st.stop()


def use_async_indexing() -> bool:
    return "vercel.app" not in API_URL


def ensure_chat() -> int:
    if st.session_state.get("chat_id"):
        return st.session_state["chat_id"]
    chat = api_post("/api/chats", json={"title": "New Chat"})
    st.session_state["chat_id"] = chat["id"]
    return chat["id"]


def confirm_delete(kind: str, item_id: int, path: str, on_success=None) -> None:
    key = f"confirm_{kind}_{item_id}"
    st.session_state[key] = True
    st.rerun()


def render_delete_controls(kind: str, item_id: int, delete_path: str, active_cleanup=None) -> None:
    key = f"confirm_{kind}_{item_id}"
    if st.session_state.get(key):
        col_confirm, col_cancel = st.sidebar.columns(2)
        with col_confirm:
            st.sidebar.markdown('<div class="danger-button">', unsafe_allow_html=True)
            if st.sidebar.button("Confirm", key=f"confirm-btn-{kind}-{item_id}", use_container_width=True):
                api_delete(delete_path)
                st.session_state.pop(key, None)
                if active_cleanup is not None:
                    active_cleanup()
                st.rerun()
            st.sidebar.markdown("</div>", unsafe_allow_html=True)
        with col_cancel:
            if st.sidebar.button("Cancel", key=f"cancel-btn-{kind}-{item_id}", use_container_width=True):
                st.session_state.pop(key, None)
                st.rerun()
    else:
        st.sidebar.markdown('<div class="danger-button">', unsafe_allow_html=True)
        if st.sidebar.button("Delete", key=f"delete-{kind}-{item_id}", use_container_width=True):
            st.session_state[key] = True
            st.rerun()
        st.sidebar.markdown("</div>", unsafe_allow_html=True)


def render_sidebar() -> tuple[list[dict], list[dict]]:
    st.sidebar.markdown(
        """
        <div class="panel-card">
            <div class="section-eyebrow">Workspace</div>
            <div class="section-title">Doc Chat Studio</div>
            <p class="section-copy">Upload documents, search them intelligently, and keep answers grounded with source evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Start New Chat", use_container_width=True):
        chat = api_post("/api/chats", json={"title": "New Chat"})
        st.session_state["chat_id"] = chat["id"]
        st.rerun()

    uploaded_files = st.sidebar.file_uploader(
        "Upload PDF, text, or note images",
        type=["pdf", "txt", "md", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    if st.sidebar.button("Process Files", use_container_width=True, disabled=not uploaded_files):
        files = [
            (
                "files",
                (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream"),
            )
            for uploaded_file in uploaded_files or []
        ]
        if use_async_indexing():
            job = api_post("/api/documents/upload-async", files=files)
            status_box = st.sidebar.status("Indexing documents...", expanded=True)
            progress_placeholder = st.sidebar.empty()
            while True:
                status = api_get(f"/api/documents/upload-jobs/{job['job_id']}")
                progress_value = max(0.0, min(float(status["progress"]), 1.0))
                status_box.update(
                    label=f"Indexing documents... {int(progress_value * 100)}%",
                    state="running" if status["status"] not in {"completed", "failed"} else ("error" if status["status"] == "failed" else "complete"),
                    expanded=True,
                )
                progress_placeholder.progress(progress_value, text=status["message"])

                if status["status"] == "completed":
                    st.sidebar.success(f"Indexed {status['documents_indexed']} document(s).")
                    break
                if status["status"] == "failed":
                    st.sidebar.error(status["error"] or status["message"])
                    break
                time.sleep(1.2)
        else:
            status_box = st.sidebar.status("Processing files on hosted backend...", expanded=True)
            progress_placeholder = st.sidebar.empty()
            progress_placeholder.progress(0.15, text="Uploading files to the API")
            status_box.update(label="Uploading files...", state="running", expanded=True)
            api_post("/api/documents/upload", files=files)
            progress_placeholder.progress(0.75, text="Indexing and storing document chunks")
            status_box.update(label="Indexing files...", state="running", expanded=True)
            progress_placeholder.progress(1.0, text="Done")
            status_box.update(label="Files indexed successfully", state="complete", expanded=True)
            st.sidebar.success(f"Indexed {len(files)} document(s).")
        st.rerun()

    documents = api_get("/api/documents")
    chats = api_get("/api/chats")

    st.sidebar.markdown(
        f"""
        <div class="panel-card">
            <div class="section-eyebrow">Library</div>
            <div class="section-title">Stored Documents</div>
            <p class="section-copy">{len(documents)} indexed document(s) ready for retrieval.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if documents:
        for doc in documents:
            preview = doc["content_preview"][:120]
            if len(doc["content_preview"]) > 120:
                preview += "..."
            st.sidebar.markdown(
                f"""
                <div class="doc-card">
                    <div class="doc-title">{doc['filename']}</div>
                    <div class="doc-meta">Type: {doc['file_type'].upper()}<br/>{preview}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_delete_controls("doc", doc["id"], f"/api/documents/{doc['id']}")
    else:
        st.sidebar.info("No documents uploaded yet.")

    st.sidebar.markdown(
        f"""
        <div class="panel-card">
            <div class="section-eyebrow">Conversations</div>
            <div class="section-title">Chat History</div>
            <p class="section-copy">{len(chats)} saved chat session(s).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for chat in chats:
        st.sidebar.markdown(
            f"""
            <div class="chat-card">
                <div class="chat-title">Chat #{chat['id']}</div>
                <div class="chat-meta">{chat['title']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_open, col_delete = st.sidebar.columns([2.2, 1])
        with col_open:
            if st.button("Open", key=f"chat-open-{chat['id']}", use_container_width=True):
                st.session_state["chat_id"] = chat["id"]
                st.rerun()
        with col_delete:
            key = f"confirm_chat_{chat['id']}"
            if st.session_state.get(key):
                st.markdown('<div class="danger-button">', unsafe_allow_html=True)
                if st.button("Confirm", key=f"chat-confirm-{chat['id']}", use_container_width=True):
                    api_delete(f"/api/chats/{chat['id']}")
                    st.session_state.pop(key, None)
                    if st.session_state.get("chat_id") == chat["id"]:
                        st.session_state.pop("chat_id", None)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="danger-button">', unsafe_allow_html=True)
                if st.button("Delete", key=f"chat-delete-{chat['id']}", use_container_width=True):
                    st.session_state[key] = True
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    return documents, chats


def render_messages(messages: list[dict]) -> None:
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return

    st.markdown("### Sources")
    for idx, source in enumerate(sources, start=1):
        location = f"Page {source['page_number']}" if source["page_number"] else "Text segment"
        title = f"{idx}. {source['document_name']} - {location}"
        with st.expander(title):
            st.caption(f"Chunk #{source['chunk_index']} - Relevance {source['score']:.3f}")
            st.write(source["excerpt"])


def render_structured_answer(structured_answer: dict) -> None:
    st.markdown("## Summary")
    st.write(structured_answer["summary"])

    if structured_answer.get("key_points"):
        st.markdown("## Key Points")
        for item in structured_answer["key_points"]:
            st.markdown(f"- {item}")

    if structured_answer.get("evidence"):
        st.markdown("## Evidence")
        for item in structured_answer["evidence"]:
            st.markdown(f"- {item}")

    if structured_answer.get("gaps_or_uncertainty"):
        st.markdown("## Gaps or Uncertainty")
        for item in structured_answer["gaps_or_uncertainty"]:
            st.markdown(f"- {item}")


def render_hero(documents: list[dict], chats: list[dict]) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-kicker">Document Intelligence Workspace</div>
            <h1 class="hero-title">Premium RAG chat for real-world documents.</h1>
            <p class="hero-copy">
                Search PDFs, notes, scans, and images with grounded answers, structured outputs, and traceable source evidence.
            </p>
            <div>
                <span class="soft-pill">Hybrid parent-child retrieval</span>
                <span class="soft-pill">Structured answers</span>
                <span class="soft-pill">OCR-aware ingestion</span>
            </div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Indexed Docs</div>
                    <div class="stat-value">{len(documents)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Saved Chats</div>
                    <div class="stat-value">{len(chats)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Answer Style</div>
                    <div class="stat-value">Structured</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_styles()
    documents, chats = render_sidebar()
    chat_id = ensure_chat()
    chat = api_get(f"/api/chats/{chat_id}")

    render_hero(documents, chats)

    st.markdown(
        """
        <div class="panel-card">
            <div class="section-eyebrow">Ask & Explore</div>
            <div class="section-title">Document Chatbot</div>
            <p class="section-copy">Ask precise questions, summarize dense files, and inspect the exact evidence used in every answer.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not documents:
        st.warning("No indexed documents found yet. Upload a file in the sidebar and click Process Files before asking questions.")

    render_messages(chat["messages"])

    prompt = st.chat_input("Ask something about your documents", disabled=not documents)
    if prompt:
        prompt = prompt.strip()
        if len(prompt) < 3:
            st.warning("Please enter a question with at least 3 characters.")
            st.stop()

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching documents and drafting answer..."):
                result = api_post(f"/api/chats/{chat_id}/ask", json={"question": prompt})
            render_structured_answer(result["structured_answer"])
            render_sources(result["sources"])

        st.rerun()


if __name__ == "__main__":
    main()
