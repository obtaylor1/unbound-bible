"""Fail-closed validation for structured scripture research provider output."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.research.retrieval import ResearchEvidence
from app.research.schemas import (
    ClaimClassification,
    PersonReference,
    PlaceReference,
    ResearchClaim,
    ResearchConfidence,
    ResearchSection,
    TimelineEvent,
)


# Provider output contains several fields whose schema limits individual values
# to 50,000 characters. This cap permits a useful multi-section response while
# bounding JSON decoding and validation work.
MAX_PROVIDER_CONTENT_CHARS = 250_000
MAX_RELATED_QUESTIONS = 5
MAX_RELATED_QUESTION_CHARS = 1_000
MAX_DOCUMENT_DEPTH = 12
MAX_DOCUMENT_NODES = 5_000
MAX_COLLECTION_ITEMS = 100
MAX_VALIDATION_WARNINGS = 100
_MAX_UNCERTAINTY_STATEMENT_CHARS = 500

_SAFE_INVALID_MESSAGE = 'Provider returned invalid structured research data.'
_ALLOWED_TOP_LEVEL_KEYS = frozenset({
    'ancient_accounts',
    'canonical_account',
    'historical_context',
    'language_notes',
    'people',
    'places',
    'related_questions',
    'summary',
    'timeline',
    'unknowns',
})
_OUTER_JSON_FENCE = re.compile(
    r'\A```json[ \t]*\r?\n(?P<body>.*)\r?\n```\Z',
    re.DOTALL,
)
_UNCERTAINTY_PATTERN = re.compile(
    r'^\s*(?:the text does not say\b|evidence is insufficient\b|'
    r'it cannot be determined\b|there is insufficient evidence\b|'
    r'no known evidence\b|'
    r'(?:it|this|the (?:answer|chronology|date|details?|identity|location|'
    r'record|text|time|timing))\s+(?:is|are|remains?|appears?)\s+'
    r'(?:uncertain|unknown|disputed)\b)'
    r'(?:\s+[^\n\r.!?;]{0,400})?[.!?]?\s*$',
    re.IGNORECASE,
)
_ASSERTIVE_CONTINUATION_PATTERN = re.compile(
    r'\b(?:and|but|however|yet)\b|[:,]',
    re.IGNORECASE,
)


class ResearchValidationError(ValueError):
    """Raised when provider content cannot safely satisfy the research shape."""


class _DuplicateKeyError(ValueError):
    """Internal signal for ambiguous provider JSON objects."""


class ValidationWarning(BaseModel):
    """A stable, safe description of content removed or downgraded."""

    model_config = ConfigDict(extra='forbid', frozen=True)

    code: str
    message: str


class ValidatedProviderDocument(BaseModel):
    """Validated provider fields awaiting Task 4 response assembly."""

    model_config = ConfigDict(extra='forbid')

    summary: ResearchSection
    timeline: list[TimelineEvent] | None = None
    canonical_account: ResearchSection | None = None
    historical_context: ResearchSection | None = None
    unknowns: ResearchSection | None = None
    ancient_accounts: list[ResearchSection] = Field(default_factory=list)
    language_notes: list[ResearchSection] = Field(default_factory=list)
    people: list[PersonReference] = Field(default_factory=list)
    places: list[PlaceReference] = Field(default_factory=list)
    related_questions: list[str] = Field(default_factory=list)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)


def parse_provider_json(content: str) -> dict[str, Any]:
    """Decode one JSON object, optionally inside exactly one outer JSON fence."""

    if not isinstance(content, str):
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
    if len(content) > MAX_PROVIDER_CONTENT_CHARS:
        raise ResearchValidationError('Provider response exceeded the safe size limit.')

    candidate = content.strip()
    if candidate.startswith('```') or candidate.endswith('```'):
        match = _OUTER_JSON_FENCE.fullmatch(candidate)
        if match is None or '```' in match.group('body'):
            raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
        candidate = match.group('body')

    try:
        parsed = json.loads(candidate, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE) from exc
    if not isinstance(parsed, dict):
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
    _preflight_document(parsed)
    return parsed


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError('duplicate provider JSON key')
        result[key] = value
    return result


def _preflight_document(document: Mapping[str, Any]) -> None:
    """Iteratively enforce structural limits before schema validation."""

    if not isinstance(document, Mapping):
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
    if set(document) - _ALLOWED_TOP_LEVEL_KEYS:
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)

    nodes = 0
    stack: list[tuple[Any, int]] = [(document, 1)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_DOCUMENT_NODES or depth > MAX_DOCUMENT_DEPTH:
            raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
        if isinstance(value, Mapping):
            if len(value) > MAX_COLLECTION_ITEMS:
                raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            if len(value) > MAX_COLLECTION_ITEMS:
                raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
            stack.extend((item, depth + 1) for item in value)


def _warning(code: str, message: str) -> ValidationWarning:
    return ValidationWarning(code=code, message=message)


def _append_warning(
    warnings: list[ValidationWarning],
    code: str,
    message: str,
) -> None:
    if len(warnings) < MAX_VALIDATION_WARNINGS:
        warnings.append(_warning(code, message))


def _known_source_ids(evidence: Iterable[ResearchEvidence]) -> frozenset[str]:
    return frozenset(item.id for item in evidence)


def _valid_ids(source_ids: list[str], known_ids: frozenset[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for source_id in source_ids:
        if source_id in known_ids and source_id not in seen:
            result.append(source_id)
            seen.add(source_id)
    return result


def _allows_uncited_claim(claim: ResearchClaim) -> bool:
    return (
        claim.classification == ClaimClassification.AI_SYNTHESIS
        or (
            len(claim.statement) <= _MAX_UNCERTAINTY_STATEMENT_CHARS
            and _UNCERTAINTY_PATTERN.fullmatch(claim.statement) is not None
            and _ASSERTIVE_CONTINUATION_PATTERN.search(claim.statement) is None
        )
    )


def _validate_claim(
    raw_claim: Any,
    known_ids: frozenset[str],
    warnings: list[ValidationWarning],
) -> ResearchClaim | None:
    try:
        parsed = ResearchClaim.model_validate(raw_claim)
    except ValidationError:
        _append_warning(
            warnings,
            'malformed_claim_removed',
            'A malformed research claim was removed.',
        )
        return None

    valid_ids = _valid_ids(parsed.source_ids, known_ids)
    has_invalid_ids = len(valid_ids) != len(parsed.source_ids)
    if not valid_ids and not _allows_uncited_claim(parsed):
        _append_warning(
            warnings,
            'unsupported_claim_removed',
            'An unsupported factual claim was removed.',
        )
        return None

    updates: dict[str, Any] = {}
    if has_invalid_ids:
        updates['source_ids'] = valid_ids
    if has_invalid_ids or not valid_ids:
        updates['confidence'] = ResearchConfidence.LOW
        _append_warning(
            warnings,
            'claim_confidence_downgraded',
            'A claim with incomplete support was downgraded to low confidence.',
        )
    return parsed.model_copy(update=updates)


def _validate_section(
    raw_section: Any,
    known_ids: frozenset[str],
    warnings: list[ValidationWarning],
    *,
    required: bool = False,
) -> ResearchSection | None:
    if not isinstance(raw_section, Mapping):
        if required:
            raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
        _append_warning(
            warnings,
            'malformed_section_removed',
            'A malformed research section was removed.',
        )
        return None

    section_data = dict(raw_section)
    raw_claims = section_data.pop('claims', [])
    if not isinstance(raw_claims, list):
        if required:
            raise ResearchValidationError(_SAFE_INVALID_MESSAGE)
        _append_warning(
            warnings,
            'malformed_section_removed',
            'A malformed research section was removed.',
        )
        return None
    raw_narrative = section_data.pop('narrative', None)
    if raw_narrative:
        _append_warning(
            warnings,
            'unchecked_narrative_removed',
            'Unchecked provider narrative was removed.',
        )
    try:
        section = ResearchSection.model_validate({
            **section_data,
            'narrative': None,
            'claims': [],
        })
    except ValidationError as exc:
        if required:
            raise ResearchValidationError(_SAFE_INVALID_MESSAGE) from exc
        _append_warning(
            warnings,
            'malformed_section_removed',
            'A malformed research section was removed.',
        )
        return None

    claims = [
        validated
        for raw_claim in raw_claims
        if (
            validated := _validate_claim(
                raw_claim,
                known_ids,
                warnings,
            )
        ) is not None
    ]
    return section.model_copy(update={'claims': claims})


def _validate_section_list(
    value: Any,
    known_ids: frozenset[str],
    warnings: list[ValidationWarning],
) -> list[ResearchSection]:
    if value is None:
        return []
    if not isinstance(value, list):
        _append_warning(
            warnings,
            'malformed_section_list_removed',
            'A malformed research section list was removed.',
        )
        return []
    return [
        section
        for raw_section in value
        if (
            section := _validate_section(raw_section, known_ids, warnings)
        ) is not None
    ]


def _validate_timeline(
    value: Any,
    known_ids: frozenset[str],
    warnings: list[ValidationWarning],
) -> list[TimelineEvent] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        _append_warning(
            warnings,
            'malformed_timeline_removed',
            'A malformed timeline was removed.',
        )
        return None

    events: list[TimelineEvent] = []
    for raw_event in value:
        try:
            event = TimelineEvent.model_validate(raw_event)
        except ValidationError:
            _append_warning(
                warnings,
                'malformed_timeline_event_removed',
                'A malformed timeline event was removed.',
            )
            continue
        has_unknown_id = any(
            source_id not in known_ids for source_id in event.source_ids
        )
        if has_unknown_id or not event.source_ids:
            _append_warning(
                warnings,
                'unsupported_timeline_event_removed',
                'An unsupported timeline event was removed.',
            )
            continue
        events.append(event)
    return events


def _validate_references(
    value: Any,
    model: type[PersonReference] | type[PlaceReference],
    known_ids: frozenset[str],
    warnings: list[ValidationWarning],
) -> list[PersonReference] | list[PlaceReference]:
    if value is None:
        return []
    if not isinstance(value, list):
        _append_warning(
            warnings,
            'malformed_reference_list_removed',
            'A malformed people or places list was removed.',
        )
        return []

    references: list[PersonReference] | list[PlaceReference] = []
    for raw_reference in value:
        try:
            reference = model.model_validate(raw_reference)
        except ValidationError:
            _append_warning(
                warnings,
                'malformed_reference_removed',
                'A malformed person or place reference was removed.',
            )
            continue
        has_unknown_id = any(
            source_id not in known_ids for source_id in reference.source_ids
        )
        if has_unknown_id or not reference.source_ids:
            _append_warning(
                warnings,
                'unsupported_reference_removed',
                'An unsupported person or place reference was removed.',
            )
            continue
        references.append(reference)
    return references


def _validate_related_questions(
    value: Any,
    warnings: list[ValidationWarning],
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        _append_warning(
            warnings,
            'malformed_related_questions_removed',
            'Malformed related questions were removed.',
        )
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        question = item.strip()
        normalized = question.casefold()
        if (
            not question
            or len(question) > MAX_RELATED_QUESTION_CHARS
            or normalized in seen
        ):
            continue
        seen.add(normalized)
        result.append(question)
        if len(result) == MAX_RELATED_QUESTIONS:
            break
    return result


def validate_provider_document(
    document: Mapping[str, Any],
    evidence: Iterable[ResearchEvidence],
) -> ValidatedProviderDocument:
    """Validate provider sections against available evidence without mutation."""

    if not isinstance(document, Mapping):
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)

    _preflight_document(document)
    known_ids = _known_source_ids(evidence)
    warnings: list[ValidationWarning] = []
    summary = _validate_section(
        document.get('summary'),
        known_ids,
        warnings,
        required=True,
    )
    if summary is None:  # Required validation raises; keeps the type explicit.
        raise ResearchValidationError(_SAFE_INVALID_MESSAGE)

    return ValidatedProviderDocument(
        summary=summary,
        timeline=_validate_timeline(document.get('timeline'), known_ids, warnings),
        canonical_account=_validate_section(
            document.get('canonical_account'), known_ids, warnings
        ) if document.get('canonical_account') is not None else None,
        historical_context=_validate_section(
            document.get('historical_context'), known_ids, warnings
        ) if document.get('historical_context') is not None else None,
        unknowns=_validate_section(
            document.get('unknowns'), known_ids, warnings
        ) if document.get('unknowns') is not None else None,
        ancient_accounts=_validate_section_list(
            document.get('ancient_accounts'), known_ids, warnings
        ),
        language_notes=_validate_section_list(
            document.get('language_notes'), known_ids, warnings
        ),
        people=_validate_references(
            document.get('people'), PersonReference, known_ids, warnings
        ),
        places=_validate_references(
            document.get('places'), PlaceReference, known_ids, warnings
        ),
        related_questions=_validate_related_questions(
            document.get('related_questions'), warnings
        ),
        validation_warnings=warnings,
    )
