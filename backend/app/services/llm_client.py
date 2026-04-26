from openai import OpenAI

from backend.app.core.config import get_settings


class LLMClientFactory:
    @staticmethod
    def create() -> OpenAI:
        settings = get_settings()
        return OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
