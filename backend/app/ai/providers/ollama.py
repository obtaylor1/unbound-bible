from collections.abc import Sequence

import httpx

from app.ai.contracts import ChatMessage, ChatResult, ProviderError


class OllamaChatProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, client: httpx.AsyncClient | None = None):
        self.base_url, self.model = base_url.rstrip("/"), model
        self.client = client or httpx.AsyncClient(timeout=60)

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatResult:
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [vars(message) for message in messages],
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            return ChatResult(content=payload["message"]["content"], provider=self.name, model=payload.get("model") or self.model)
        except httpx.TimeoutException as error:
            raise ProviderError("Local AI provider timed out", code="timeout", retryable=True) from error
        except httpx.RequestError as error:
            raise ProviderError(
                "Local AI provider is unavailable", code="unavailable", retryable=True
            ) from error
        except httpx.HTTPStatusError as error:
            raise ProviderError("Local AI provider is unavailable", code="unavailable", retryable=True) from error
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError("Local AI provider returned a malformed response", code="malformed_response") from error


class OllamaEmbeddingProvider:
    name = "ollama"
    def __init__(self, base_url: str, model: str, client: httpx.AsyncClient | None = None):
        self.base_url, self.model = base_url.rstrip("/"), model
        self.client = client or httpx.AsyncClient(timeout=60)
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        results = []
        for text in texts:
            try:
                response = await self.client.post(f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text})
                response.raise_for_status(); results.append(response.json()["embedding"])
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                raise ProviderError("Local embedding provider failed", code="embedding_failed", retryable=True) from error
        return results
