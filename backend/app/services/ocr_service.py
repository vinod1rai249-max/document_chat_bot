from __future__ import annotations

import base64
import io
import time
from pathlib import Path

from openai import APIConnectionError, APIError, RateLimitError

from backend.app.core.config import get_settings
from backend.app.services.llm_client import LLMClientFactory
from backend.app.utils.text import clean_text

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - optional dependency fallback
    fitz = None

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - optional dependency fallback
    Image = None
    ImageOps = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency fallback
    pytesseract = None


OCR_PROMPT = """Transcribe this document image faithfully.
It may contain handwritten notes, scanned text, tables, or mixed content.
Return only the extracted text.
Preserve headings, bullet points, labels, and line breaks when possible.
Do not summarize. Do not infer missing words. If a region is unreadable, write [unreadable].
"""


class OCRService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = LLMClientFactory.create()
        if pytesseract is not None and self.settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_cmd

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        image_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                completion = self.client.chat.completions.create(
                    model=self.settings.openai_vision_model,
                    temperature=0,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an OCR engine for document ingestion.",
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": OCR_PROMPT},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        },
                    ],
                )
                return clean_text(completion.choices[0].message.content or "")
            except RateLimitError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError("OCR provider is temporarily rate-limited. Please try the upload again in a moment.") from exc
            except (APIConnectionError, APIError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                    continue
                break

        local_text = self._extract_text_with_tesseract(image_bytes)
        if local_text:
            return local_text

        if last_error is not None:
            raise RuntimeError(
                "OCR provider is temporarily unavailable and local OCR is not configured. "
                "Please try again shortly or install Tesseract for offline OCR."
            ) from last_error
        raise RuntimeError("OCR failed to extract text from the image.")

    def extract_text_from_image_file(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        return self.extract_text_from_image(file_path.read_bytes(), mime_type)

    def render_pdf_page_to_png(self, file_path: Path, page_number: int) -> bytes:
        if fitz is None:
            raise RuntimeError("PyMuPDF is not installed. PDF OCR fallback is unavailable.")
        document = fitz.open(file_path)
        try:
            page = document.load_page(page_number)
            zoom = max(self.settings.ocr_image_dpi / 72.0, 1.0)
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            return pixmap.tobytes("png")
        finally:
            document.close()

    def _extract_text_with_tesseract(self, image_bytes: bytes) -> str:
        if pytesseract is None or Image is None or ImageOps is None:
            return ""

        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.grayscale(image)
            text = pytesseract.image_to_string(image)
            return clean_text(text)
        except Exception:
            return ""
