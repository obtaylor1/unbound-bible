from dataclasses import dataclass
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    provider: str
    model: str
    is_demo: bool = False


class ChatProvider(Protocol):
    name: str
    async def complete(self, messages: Sequence[ChatMessage]) -> ChatResult: ...


class EmbeddingProvider(Protocol):
    name: str
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class TranscriptionProvider(Protocol):
    name: str
    async def transcribe(self, audio: bytes, filename: str) -> str: ...


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False):
        super().__init__(message)
        self.code, self.retryable = code, retryable
