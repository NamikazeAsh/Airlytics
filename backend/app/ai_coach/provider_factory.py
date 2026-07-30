from app.ai_coach.llm_client import LLMClient
from app.ai_coach.providers.groq_client import GroqClient
from app.config import get_settings


class LLMNotConfiguredError(Exception):
    pass


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise LLMNotConfiguredError("GROQ_API_KEY is not set")
        return GroqClient(api_key=settings.groq_api_key, model=settings.groq_model)
    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Expected 'groq'.")
