"""Grounded orchestration for structured scripture research."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from app.ai.contracts import ChatMessage, ChatProvider, ProviderError
from app.ai.models import AIOperation
from app.research.retrieval import ResearchEvidence
from app.research.schemas import (
    ClaimClassification,
    GroundingStatus,
    ResearchClaim,
    ResearchConfidence,
    ResearchQueryRequest,
    ResearchResponse,
    ResearchSection,
    ResearchSettings,
    ResearchSource,
)
from app.research.validation import (
    ResearchValidationError,
    ValidatedProviderDocument,
    parse_provider_json,
    validate_provider_document,
)


_MAX_EVIDENCE_RECORDS = 32
_MAX_EVIDENCE_TEXT_CHARS = 8_000
_MAX_EVIDENCE_METADATA_CHARS = 2_000

_SYSTEM_INSTRUCTION = """Use only supplied evidence. Return one JSON object matching schema.
Every factual claim/event must cite source_ids from evidence.
Do not treat prior AI text as evidence. State uncertainty when silent.
Do not add source merely because scope enabled.
The only recognized top-level keys are: summary, timeline, canonical_account, historical_context, unknowns, ancient_accounts, language_notes, people, places, related_questions.
The summary object is required. Section objects contain title and claims only. narrative and other free-form fields are forbidden.
Claims must contain id, statement, classification, confidence, and source_ids. Timeline events must contain title, description, date_label, source_ids, and confidence."""


class ResearchService:
    """Coordinate retrieval, provider generation, validation, and auditing."""

    def __init__(
        self,
        retriever: Callable[..., Iterable[ResearchEvidence]],
        provider: ChatProvider,
        session: Any | None = None,
        user: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._provider = provider
        self._session = session
        self._user = user

    async def query(self, request: ResearchQueryRequest) -> ResearchResponse:
        evidence = list(self._retriever(
            self._session,
            request.question,
            request.source_scopes,
            request.depth,
        ))[:_MAX_EVIDENCE_RECORDS]
        sources = [_to_source(item) for item in evidence]

        if not evidence:
            response = _fallback_response(
                request,
                status=GroundingStatus.INSUFFICIENT,
                sources=[],
                provider='none',
                model='none',
                summary_statement=(
                    'The selected library does not contain enough verified evidence '
                    'to answer this question.'
                ),
                unknown_statement=(
                    'The selected library is insufficient to establish an '
                    'evidence-backed answer.'
                ),
            )
            self._audit(response, ['no_verified_evidence'])
            return response

        try:
            result = await self._provider.complete(_messages(request, evidence))
        except ProviderError:
            response = _fallback_response(
                request,
                status=GroundingStatus.EVIDENCE_ONLY,
                sources=sources,
                provider=self._provider.name,
                model='unavailable',
                summary_statement=(
                    'Verified evidence was found, but a structured analysis is '
                    'temporarily unavailable.'
                ),
                unknown_statement=(
                    'No validated synthesis could be produced from the retrieved '
                    'evidence at this time.'
                ),
            )
            self._audit(response, ['provider_unavailable'])
            return response

        try:
            document = validate_provider_document(
                parse_provider_json(result.content), evidence
            )
        except ResearchValidationError:
            response = _fallback_response(
                request,
                status=GroundingStatus.EVIDENCE_ONLY,
                sources=sources,
                provider=result.provider,
                model=result.model,
                summary_statement=(
                    'Verified evidence was found, but no valid structured analysis '
                    'was returned.'
                ),
                unknown_statement=(
                    'No validated synthesis could be produced from the retrieved '
                    'evidence at this time.'
                ),
            )
            self._audit(response, ['invalid_structured_response'])
            return response

        status = (
            GroundingStatus.GROUNDED
            if _has_grounded_fact(document)
            else GroundingStatus.EVIDENCE_ONLY
        )
        response = ResearchResponse(
            id=uuid.uuid4(),
            query=request.question,
            mode=request.mode,
            settings=_settings(request),
            summary=document.summary,
            timeline=document.timeline,
            canonical_account=document.canonical_account,
            historical_context=document.historical_context,
            unknowns=document.unknowns,
            ancient_accounts=document.ancient_accounts,
            language_notes=document.language_notes,
            people=document.people,
            places=document.places,
            sources=sources,
            related_questions=document.related_questions,
            grounding_status=status,
            provider=result.provider,
            model=result.model,
        )
        self._audit(
            response,
            [warning.code for warning in document.validation_warnings],
        )
        return response

    def _audit(self, response: ResearchResponse, errors: list[str]) -> None:
        """Best-effort audit: roll back audit failure and preserve safe response."""

        if self._session is None:
            return
        operation = AIOperation(
            user_id=getattr(self._user, 'id', None),
            question_hash=hashlib.sha256(
                response.query.strip().encode('utf-8')
            ).hexdigest(),
            provider=response.provider,
            model=response.model,
            grounding_status=response.grounding_status.value,
            source_ids=[source.id for source in response.sources],
            validation_errors=errors,
        )
        try:
            self._session.add(operation)
            self._session.commit()
        except Exception:
            try:
                self._session.rollback()
            except Exception:
                pass


def _settings(request: ResearchQueryRequest) -> ResearchSettings:
    return ResearchSettings(
        source_scopes=request.source_scopes,
        depth=request.depth,
        mode_parameters=request.mode_parameters,
    )


def _fallback_claim(statement: str) -> ResearchClaim:
    return ResearchClaim(
        id=str(uuid.uuid4()),
        statement=statement,
        classification=ClaimClassification.AI_SYNTHESIS,
        confidence=ResearchConfidence.LOW,
        source_ids=[],
    )


def _fallback_response(
    request: ResearchQueryRequest,
    *,
    status: GroundingStatus,
    sources: list[ResearchSource],
    provider: str,
    model: str,
    summary_statement: str,
    unknown_statement: str,
) -> ResearchResponse:
    return ResearchResponse(
        id=uuid.uuid4(),
        query=request.question,
        mode=request.mode,
        settings=_settings(request),
        summary=ResearchSection(
            title='Research status',
            claims=[_fallback_claim(summary_statement)],
        ),
        unknowns=ResearchSection(
            title="What We Don't Know",
            claims=[_fallback_claim(unknown_statement)],
        ),
        sources=sources,
        grounding_status=status,
        provider=provider,
        model=model,
    )


def _to_source(evidence: ResearchEvidence) -> ResearchSource:
    return ResearchSource(
        id=evidence.id,
        title=evidence.title,
        reference=evidence.reference,
        text=evidence.text,
        source_type=evidence.source_type,
        tradition=evidence.tradition,
        date_or_era=evidence.date_or_era,
        original_language=evidence.original_language,
        translation=evidence.translation,
        open_target=evidence.open_target,
    )


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def _evidence_record(evidence: ResearchEvidence) -> dict[str, Any]:
    return {
        'id': _bounded(evidence.id, _MAX_EVIDENCE_METADATA_CHARS),
        'title': _bounded(evidence.title, _MAX_EVIDENCE_METADATA_CHARS),
        'reference': _bounded(evidence.reference, _MAX_EVIDENCE_METADATA_CHARS),
        'text': _bounded(evidence.text, _MAX_EVIDENCE_TEXT_CHARS),
        'provenance': {
            'source_type': _bounded(
                evidence.source_type, _MAX_EVIDENCE_METADATA_CHARS
            ),
            'tradition': _bounded(
                evidence.tradition, _MAX_EVIDENCE_METADATA_CHARS
            ),
            'translation': _bounded(
                evidence.translation, _MAX_EVIDENCE_METADATA_CHARS
            ),
            'date_or_era': _bounded(
                evidence.date_or_era, _MAX_EVIDENCE_METADATA_CHARS
            ),
            'original_language': _bounded(
                evidence.original_language, _MAX_EVIDENCE_METADATA_CHARS
            ),
            'open_target': _bounded(
                evidence.open_target, _MAX_EVIDENCE_METADATA_CHARS
            ),
        },
    }


def _messages(
    request: ResearchQueryRequest,
    evidence: list[ResearchEvidence],
) -> list[ChatMessage]:
    payload = {
        'question': request.question,
        'settings': {
            'source_scopes': [scope.value for scope in request.source_scopes],
            'depth': request.depth.value,
            'mode': request.mode.value,
            'mode_parameters': request.mode_parameters,
        },
        'evidence': [_evidence_record(item) for item in evidence],
    }
    return [
        ChatMessage(role='system', content=_SYSTEM_INSTRUCTION),
        ChatMessage(
            role='user',
            content=json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
        ),
    ]


def _has_grounded_fact(document: ValidatedProviderDocument) -> bool:
    sections = [
        document.summary,
        document.canonical_account,
        document.historical_context,
        document.unknowns,
        *document.ancient_accounts,
        *document.language_notes,
    ]
    for section in sections:
        if section is None:
            continue
        if any(
            claim.source_ids
            and claim.classification != ClaimClassification.AI_SYNTHESIS
            for claim in section.claims
        ):
            return True
    return any(event.source_ids for event in document.timeline or [])
