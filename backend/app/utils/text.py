from __future__ import annotations

import re


def clean_text(text: str) -> str:
    normalized = text.replace("\x00", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)

    return chunks
