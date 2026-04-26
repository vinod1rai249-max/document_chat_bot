from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_chat_model: str = Field(default="gpt-4.1-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    openai_vision_model: str = Field(default="gpt-4.1-mini")
    embedding_dimension: int = Field(default=1536)
    database_url: str = Field(default="sqlite:///./backend/storage/app.db")
    upload_dir: Path = Field(default=Path("backend/storage/uploads"))
    vector_index_dir: Path = Field(default=Path("backend/storage/vector"))
    max_chunk_size: int = Field(default=900)
    chunk_overlap: int = Field(default=150)
    parent_chunk_size: int = Field(default=1800)
    parent_chunk_overlap: int = Field(default=240)
    child_chunk_size: int = Field(default=420)
    child_chunk_overlap: int = Field(default=80)
    top_k_results: int = Field(default=3)
    embedding_batch_size: int = Field(default=32)
    max_context_sources: int = Field(default=3)
    max_source_excerpt_chars: int = Field(default=700)
    chat_history_limit: int = Field(default=4)
    ocr_min_text_length: int = Field(default=20)
    ocr_image_dpi: int = Field(default=120)
    tesseract_cmd: str = Field(default="")
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    streamlit_api_url: str = Field(default="http://127.0.0.1:8000")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector_index_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
