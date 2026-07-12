import httpx

from app.ai.contracts import ChatProvider, EmbeddingProvider, TranscriptionProvider
from app.ai.providers.demo import DemoChatProvider, DemoEmbeddingProvider, DemoTranscriptionProvider
from app.ai.providers.ollama import OllamaChatProvider, OllamaEmbeddingProvider
from app.ai.providers.openai_compatible import OpenAICompatibleChatProvider, OpenAICompatibleEmbeddingProvider, OpenAICompatibleTranscriptionProvider
from app.config import Settings


def create_chat_provider(name: str, settings: Settings, http_client: httpx.AsyncClient | None = None) -> ChatProvider:
    if name == "demo":
        return DemoChatProvider()
    if name == "openai_compatible":
        return OpenAICompatibleChatProvider(settings.openai_compatible_base_url, settings.ai_chat_model, settings.ai_api_key, http_client)
    if name == "ollama":
        return OllamaChatProvider(settings.ollama_base_url, settings.ai_chat_model, http_client)
    raise ValueError(f"Unsupported chat provider: {name}")


def create_embedding_provider(name: str, settings: Settings, http_client: httpx.AsyncClient | None = None) -> EmbeddingProvider:
    if name == "demo": return DemoEmbeddingProvider()
    if name == "openai_compatible": return OpenAICompatibleEmbeddingProvider(settings.openai_compatible_base_url, settings.ai_embedding_model, settings.ai_api_key, http_client)
    if name == "ollama": return OllamaEmbeddingProvider(settings.ollama_base_url, settings.ai_embedding_model, http_client)
    raise ValueError(f"Unsupported embedding provider: {name}")


def create_transcription_provider(name: str, settings: Settings, http_client: httpx.AsyncClient | None = None) -> TranscriptionProvider:
    if name == "demo": return DemoTranscriptionProvider()
    if name == "openai_compatible": return OpenAICompatibleTranscriptionProvider(settings.openai_compatible_base_url, settings.ai_transcription_model, settings.ai_api_key, http_client)
    raise ValueError(f"Unsupported transcription provider: {name}")


def provider_diagnostics(settings: Settings) -> dict[str, dict[str, str | bool]]:
    chat = settings.ai_chat_provider
    configured = chat == "demo" or chat == "ollama" or bool(settings.ai_api_key)
    return {"chat": {"provider": chat, "configured": configured}, "embeddings": {"provider": settings.ai_embedding_provider, "configured": settings.ai_embedding_provider == "demo" or bool(settings.ai_api_key)}, "transcription": {"provider": settings.ai_transcription_provider, "configured": settings.ai_transcription_provider == "demo" or bool(settings.ai_api_key)}}
