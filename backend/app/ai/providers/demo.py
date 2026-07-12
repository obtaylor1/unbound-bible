from collections.abc import Sequence

from app.ai.contracts import ChatMessage, ChatResult


class DemoChatProvider:
    name = "demo"
    model = "unbound-demo"

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatResult:
        question = next((message.content for message in reversed(messages) if message.role == "user"), "your question")
        return ChatResult(
            content=f"Demo response for: {question}. Connect a configured AI provider for generated analysis.",
            provider=self.name, model=self.model, is_demo=True,
        )


class DemoEmbeddingProvider:
    name = "demo"
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float((sum(map(ord, text)) + offset) % 997) / 997 for offset in range(16)] for text in texts]


class DemoTranscriptionProvider:
    name = "demo"
    async def transcribe(self, audio: bytes, filename: str) -> str:
        return "Demo transcription unavailable. Configure a transcription provider to process audio."
