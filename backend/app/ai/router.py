from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai.contracts import ChatMessage, ProviderError
from app.ai.factory import create_chat_provider
from app.ai.references import parse_reference
from app.ai.retrieval import retrieve_exact_reference
from app.auth.dependencies import get_session


router = APIRouter(prefix="/chat", tags=["AI study"])


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=10_000)


@router.post("/ask")
async def ask(payload: AskRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    reference = parse_reference(payload.question)
    sources = retrieve_exact_reference(session, reference) if reference else []
    if not sources:
        return {"answer": "The library does not contain enough verified evidence to answer that question yet.", "provider": "none", "model": "none", "is_demo": False, "grounding_status": "insufficient", "sources": [], "citation_ids": [], "follow_ups": [], "study_message_id": None}

    evidence = "\n".join(f"[{source.id}] {source.reference} ({source.translation}): {source.text}" for source in sources)
    provider = create_chat_provider(request.app.state.settings.ai_chat_provider, request.app.state.settings)
    try:
        result = await provider.complete([
            ChatMessage(role="system", content="Answer only from the supplied verified Scripture evidence. Do not invent citations."),
            ChatMessage(role="user", content=f"Question: {payload.question}\n\nEvidence:\n{evidence}"),
        ])
    except ProviderError:
        return {"answer": "Verified passages were found, but the analysis provider is temporarily unavailable.", "provider": provider.name, "model": "unavailable", "is_demo": False, "grounding_status": "evidence_only", "sources": [source.to_dict() for source in sources], "citation_ids": [source.id for source in sources], "follow_ups": [], "study_message_id": None}
    return {"answer": result.content, "provider": result.provider, "model": result.model, "is_demo": result.is_demo, "grounding_status": "grounded", "sources": [source.to_dict() for source in sources], "citation_ids": [source.id for source in sources], "follow_ups": [], "study_message_id": None}
