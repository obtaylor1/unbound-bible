from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import hashlib
import re

from app.ai.contracts import ChatMessage, ProviderError
from app.ai.factory import create_chat_provider
from app.ai.references import parse_reference
from app.ai.retrieval import retrieve_exact_reference
from app.ai.citations import validate_citations
from app.ai.models import AIOperation
from app.auth.dependencies import get_optional_user, get_session
from app.auth.models import User
from app.security.rate_limits import enforce_rate_limit


router = APIRouter(prefix="/chat", tags=["AI study"])


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=10_000)


@router.post("/ask", dependencies=[Depends(enforce_rate_limit('ai', 'ai_rate_limit', 60))])
async def ask(payload: AskRequest, request: Request, session: Session = Depends(get_session), user: User | None = Depends(get_optional_user)) -> dict:
    reference = parse_reference(payload.question)
    sources = retrieve_exact_reference(session, reference) if reference else []
    if not sources:
        record_operation(session, payload.question, user, 'none', 'none', 'insufficient', [], ['no_verified_evidence'])
        return {"answer": "The library does not contain enough verified evidence to answer that question yet.", "provider": "none", "model": "none", "is_demo": False, "grounding_status": "insufficient", "sources": [], "citation_ids": [], "follow_ups": [], "study_message_id": None}

    evidence = "\n".join(f"[{source.id}] {source.reference} ({source.translation}): {source.text}" for source in sources)
    provider = create_chat_provider(request.app.state.settings.ai_chat_provider, request.app.state.settings)
    try:
        result = await provider.complete([
            ChatMessage(role="system", content="Answer only from the supplied verified Scripture evidence. Cite every factual claim using the exact bracketed source ID, such as [scripture:123]. Do not invent citations."),
            ChatMessage(role="user", content=f"Question: {payload.question}\n\nEvidence:\n{evidence}"),
        ])
    except ProviderError:
        record_operation(session, payload.question, user, provider.name, 'unavailable', 'evidence_only', [source.id for source in sources], ['provider_unavailable'])
        return {"answer": "Verified passages were found, but the analysis provider is temporarily unavailable.", "provider": provider.name, "model": "unavailable", "is_demo": False, "grounding_status": "evidence_only", "sources": [source.to_dict() for source in sources], "citation_ids": [source.id for source in sources], "follow_ups": [], "study_message_id": None}
    generated_ids = re.findall(r'\[([a-z_]+:\d+)\]', result.content)
    valid_ids, all_valid = validate_citations(generated_ids, sources)
    grounding_status = 'grounded' if generated_ids and all_valid else 'evidence_only'
    errors = [] if grounding_status == 'grounded' else (['missing_inline_citations'] if not generated_ids else ['invalid_inline_citations'])
    record_operation(session, payload.question, user, result.provider, result.model, grounding_status, valid_ids, errors)
    return {"answer": result.content, "provider": result.provider, "model": result.model, "is_demo": result.is_demo, "grounding_status": grounding_status, "sources": [source.to_dict() for source in sources], "citation_ids": valid_ids, "follow_ups": [], "study_message_id": None}


def record_operation(session: Session, question: str, user: User | None, provider: str, model: str, status: str, source_ids: list[str], errors: list[str]) -> None:
    session.add(AIOperation(user_id=user.id if user else None, question_hash=hashlib.sha256(question.strip().encode()).hexdigest(), provider=provider, model=model, grounding_status=status, source_ids=source_ids, validation_errors=errors))
    session.commit()
