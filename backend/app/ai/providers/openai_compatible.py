from collections.abc import Sequence

import httpx

from app.ai.contracts import ChatMessage, ChatResult, ProviderError


class OpenAICompatibleChatProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.client = client or httpx.AsyncClient(timeout=30)

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [vars(message) for message in messages],
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return ChatResult(content=content, provider=self.name, model=payload.get("model") or self.model)
        except httpx.TimeoutException as error:
            raise ProviderError("AI provider timed out", code="timeout", retryable=True) from error
        except httpx.RequestError as error:
            raise ProviderError(
                "AI provider is unavailable", code="unavailable", retryable=True
            ) from error
        except httpx.HTTPStatusError as error:
            code = "authentication" if error.response.status_code in (401, 403) else "unavailable"
            raise ProviderError("AI provider request failed", code=code, retryable=error.response.status_code >= 500) from error
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("AI provider returned a malformed response", code="malformed_response") from error


class OpenAICompatibleEmbeddingProvider:
    name = "openai_compatible"
    def __init__(self, base_url: str, model: str, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.client = client or httpx.AsyncClient(timeout=30)
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = await self.client.post(f"{self.base_url}/embeddings", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "input": list(texts)})
            response.raise_for_status()
            return [item["embedding"] for item in response.json()["data"]]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderError("Embedding provider request failed", code="embedding_failed", retryable=True) from error


class OpenAICompatibleTranscriptionProvider:
    name = "openai_compatible"
    def __init__(self, base_url: str, model: str, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.client = client or httpx.AsyncClient(timeout=120)
    async def transcribe(self, audio: bytes, filename: str) -> str:
        try:
            response = await self.client.post(f"{self.base_url}/audio/transcriptions", headers={"Authorization": f"Bearer {self.api_key}"}, data={"model": self.model}, files={"file": (filename, audio)})
            response.raise_for_status()
            return response.json()["text"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderError("Transcription provider request failed", code="transcription_failed", retryable=True) from error
