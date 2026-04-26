from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.core.config import get_settings

try:
    from vercel.blob import get, put
except ImportError:  # pragma: no cover - optional in local dev until installed
    get = None
    put = None


class BlobPersistence:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.token = self._resolve_blob_token()
        self.enabled = bool(
            self.settings.persist_state_to_blob
            and self.token
            and get is not None
            and put is not None
        )
        self.sqlite_path = self._sqlite_path()
        self.artifacts = {
            "app.db": self.sqlite_path,
            "chunks.faiss": Path(self.settings.vector_index_dir) / "chunks.faiss",
            "chunks_metadata.json": Path(self.settings.vector_index_dir) / "chunks_metadata.json",
        }

    def sync_down(self) -> None:
        if not self.enabled:
            return

        for name, local_path in self.artifacts.items():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            result = get(
                self._blob_path(name),
                access=self.settings.blob_access,
                token=self.token,
            )
            if result is None or result.status_code != 200 or result.stream is None:
                continue
            local_path.write_bytes(self._consume_stream(result.stream))

    def sync_up(self) -> None:
        if not self.enabled:
            return

        for name, local_path in self.artifacts.items():
            if not local_path.exists():
                continue
            put(
                self._blob_path(name),
                local_path.read_bytes(),
                access=self.settings.blob_access,
                token=self.token,
                overwrite=True,
                content_type=self._content_type(local_path),
            )

    def _blob_path(self, name: str) -> str:
        return f"{self.settings.blob_state_prefix.rstrip('/')}/{name}"

    def _sqlite_path(self) -> Path:
        if self.settings.database_url.startswith("sqlite:///"):
            raw = self.settings.database_url.replace("sqlite:///", "", 1)
            return Path(raw)
        raise ValueError("Blob persistence only supports SQLite database URLs.")

    def _resolve_blob_token(self) -> str:
        return os.getenv("BLOB_READ_WRITE_TOKEN", "")

    def _content_type(self, path: Path) -> str:
        if path.suffix == ".json":
            return "application/json"
        if path.suffix == ".db":
            return "application/octet-stream"
        if path.suffix == ".faiss":
            return "application/octet-stream"
        return "application/octet-stream"

    def _consume_stream(self, stream) -> bytes:
        if hasattr(stream, "__aiter__"):
            async def collect() -> bytes:
                parts: list[bytes] = []
                async for chunk in stream:
                    parts.append(chunk)
                return b"".join(parts)

            try:
                return asyncio.run(collect())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(collect())
                finally:
                    loop.close()

        return b"".join(stream)
