import pytest

from app.ai_coach.provider_factory import LLMNotConfiguredError, get_llm_client
from app.ai_coach.providers.groq_client import GroqClient
from app.config import get_settings


def test_get_llm_client_returns_groq_by_default(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    assert settings.llm_provider == "groq"
    client = get_llm_client()
    assert isinstance(client, GroqClient)


def test_get_llm_client_raises_on_unknown_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "made_up_provider")
    with pytest.raises(ValueError):
        get_llm_client()


def test_get_llm_client_raises_when_api_key_missing(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "groq_api_key", "")
    with pytest.raises(LLMNotConfiguredError):
        get_llm_client()
