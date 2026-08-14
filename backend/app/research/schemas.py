"""Strict request and response contracts for scripture research."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceScope(StrEnum):
    BIBLICAL_CANON = 'biblical-canon'
    ETHIOPIAN_TRADITION = 'ethiopian-tradition'
    APOCRYPHA = 'apocrypha'
    FIRST_ENOCH = '1-enoch'
    JUBILEES = 'jubilees'
    ANCIENT_SOURCES = 'ancient-sources'
    COMMENTARY = 'commentary'
    ALL_SOURCES = 'all-sources'


class ResearchDepth(StrEnum):
    QUICK = 'quick'
    STUDY = 'study'
    DEEP = 'deep-research'
    SCHOLAR = 'scholar'


class ResearchMode(StrEnum):
    BETWEEN = 'what-happened-between'
    EXPLAIN_A_BOOK = 'explain-a-book'
    COMPARE_ACCOUNTS = 'compare-accounts'
    PEOPLE_AND_PLACES = 'people-and-places'
    ORIGINAL_LANGUAGES = 'original-languages'
    GENEALOGY = 'genealogy'


class ClaimClassification(StrEnum):
    CANONICAL_SCRIPTURE = 'canonical-scripture'
    ETHIOPIAN_CANON = 'ethiopian-canon'
    ANCIENT_TEXT = 'ancient-text'
    COMMENTARY = 'commentary'
    TRADITION = 'tradition'
    HISTORICAL = 'historical'
    SCHOLARSHIP = 'scholarship'
    AI_SYNTHESIS = 'ai-synthesis'


class SourceType(StrEnum):
    CANONICAL_SCRIPTURE = 'canonical-scripture'
    ETHIOPIAN_CANON = 'ethiopian-canon'
    ANCIENT_TEXT = 'ancient-text'
    MANUSCRIPT = 'manuscript'
    HISTORICAL_SOURCE = 'historical-source'
    EARLY_CHRISTIAN_WRITING = 'early-christian-writing'
    JEWISH_TRADITION = 'jewish-tradition'
    CHURCH_TRADITION = 'church-tradition'
    COMMENTARY = 'commentary'
    SCHOLARSHIP = 'scholarship'
    AI_SYNTHESIS = 'ai-synthesis'


class ResearchConfidence(StrEnum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    DISPUTED = 'disputed'


class GroundingStatus(StrEnum):
    GROUNDED = 'grounded'
    PARTIALLY_GROUNDED = 'partially-grounded'
    EVIDENCE_ONLY = 'evidence-only'
    INSUFFICIENT = 'insufficient'


class StrictResearchModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


def _default_scopes() -> list[SourceScope]:
    return [SourceScope.BIBLICAL_CANON]


def _bounded_mode_parameters(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError('mode parameters must be an object')
    if len(value) > 8:
        raise ValueError('mode parameters must contain at most 8 items')
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError('mode parameter keys and values must be strings')
        key = raw_key.strip()
        item = raw_value.strip()
        if not 1 <= len(key) <= 64:
            raise ValueError('mode parameter keys must contain 1 to 64 characters')
        if not item:
            raise ValueError('mode parameter values must not be blank')
        if len(item) > 256:
            raise ValueError('mode parameter values must contain at most 256 characters')
        if key in normalized:
            raise ValueError('mode parameter keys must be unique after normalization')
        normalized[key] = item
    return normalized


class ResearchSettings(StrictResearchModel):
    source_scopes: list[SourceScope] = Field(
        default_factory=_default_scopes, min_length=1, max_length=8
    )
    depth: ResearchDepth = ResearchDepth.DEEP
    mode_parameters: dict[str, str] = Field(default_factory=dict)

    @field_validator('mode_parameters', mode='before')
    @classmethod
    def validate_mode_parameters(cls, value: Any) -> dict[str, str]:
        return _bounded_mode_parameters(value)

    @model_validator(mode='after')
    def validate_source_scopes(self) -> ResearchSettings:
        if len(set(self.source_scopes)) != len(self.source_scopes):
            raise ValueError('source scopes must be unique')
        if (
            SourceScope.ALL_SOURCES in self.source_scopes
            and len(self.source_scopes) != 1
        ):
            raise ValueError('all-sources cannot be mixed with another source')
        return self


class ResearchSource(StrictResearchModel):
    id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=1_000)
    reference: str = Field(min_length=1, max_length=2_000)
    excerpt: str | None = None
    text: str | None = None
    source_type: SourceType
    tradition: str | None = None
    date_or_era: str | None = None
    original_language: str | None = None
    translation: str | None = None
    relevance: str | None = None
    open_target: str | None = None


class ResearchClaim(StrictResearchModel):
    id: str = Field(min_length=1, max_length=500)
    statement: str = Field(min_length=1, max_length=50_000)
    classification: ClaimClassification
    confidence: ResearchConfidence = ResearchConfidence.MEDIUM
    source_ids: list[str] = Field(default_factory=list)


class ResearchSection(StrictResearchModel):
    title: str = Field(min_length=1, max_length=1_000)
    narrative: str | None = None
    claims: list[ResearchClaim] = Field(default_factory=list)


class TimelineEvent(StrictResearchModel):
    title: str = Field(min_length=1, max_length=1_000)
    description: str = Field(min_length=1, max_length=50_000)
    date_label: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    confidence: ResearchConfidence = ResearchConfidence.MEDIUM


class PersonReference(StrictResearchModel):
    name: str = Field(min_length=1, max_length=1_000)
    description: str | None = None
    role: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class PlaceReference(StrictResearchModel):
    name: str = Field(min_length=1, max_length=1_000)
    description: str | None = None
    location: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class TrailNode(StrictResearchModel):
    id: uuid.UUID
    parent_node_id: uuid.UUID | None = None
    question: str = Field(min_length=2, max_length=10_000)
    label: str | None = None


def _bounded_unique_context_values(
    value: Any, *, label: str, max_length: int
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f'{label} must be an array')
    if len(value) > 16:
        raise ValueError(f'{label} must contain at most 16 items')
    normalized: list[str] = []
    for raw_item in value:
        if not isinstance(raw_item, str):
            raise ValueError(f'{label} items must be strings')
        item = raw_item.strip()
        if not item:
            raise ValueError(f'{label} items must not be blank')
        if len(item) > max_length:
            raise ValueError(
                f'{label} items must contain at most {max_length} characters'
            )
        if item not in normalized:
            normalized.append(item)
    return normalized


class ConversationContext(StrictResearchModel):
    """Compact validated guest context; never prior generated prose."""

    entity_names: list[str] = Field(default_factory=list, max_length=16)
    source_references: list[str] = Field(default_factory=list, max_length=16)

    @field_validator('entity_names', mode='before')
    @classmethod
    def validate_entity_names(cls, value: Any) -> list[str]:
        return _bounded_unique_context_values(
            value, label='entity names', max_length=200
        )

    @field_validator('source_references', mode='before')
    @classmethod
    def validate_source_references(cls, value: Any) -> list[str]:
        return _bounded_unique_context_values(
            value, label='source references', max_length=500
        )


class ResearchQueryRequest(StrictResearchModel):
    question: str = Field(min_length=2, max_length=10_000)
    session_id: uuid.UUID | None = None
    parent_node_id: uuid.UUID | None = None
    conversation_context: ConversationContext | None = None
    mode: ResearchMode = ResearchMode.BETWEEN
    source_scopes: list[SourceScope] = Field(
        default_factory=_default_scopes, min_length=1, max_length=8
    )
    depth: ResearchDepth = ResearchDepth.DEEP
    mode_parameters: dict[str, str] = Field(default_factory=dict)

    @field_validator('mode_parameters', mode='before')
    @classmethod
    def validate_mode_parameters(cls, value: Any) -> dict[str, str]:
        return _bounded_mode_parameters(value)

    @model_validator(mode='after')
    def validate_source_scopes(self) -> ResearchQueryRequest:
        if len(set(self.source_scopes)) != len(self.source_scopes):
            raise ValueError('source scopes must be unique')
        if (
            SourceScope.ALL_SOURCES in self.source_scopes
            and len(self.source_scopes) != 1
        ):
            raise ValueError('all-sources cannot be mixed with another source')
        return self


class ResearchResponse(StrictResearchModel):
    id: uuid.UUID
    query: str = Field(min_length=2, max_length=10_000)
    mode: ResearchMode
    settings: ResearchSettings
    summary: ResearchSection
    timeline: list[TimelineEvent] | None = None
    canonical_account: ResearchSection | None = None
    historical_context: ResearchSection | None = None
    unknowns: ResearchSection | None = None
    trail_node: TrailNode | None = None
    ancient_accounts: list[ResearchSection] = Field(default_factory=list)
    language_notes: list[ResearchSection] = Field(default_factory=list)
    people: list[PersonReference] = Field(default_factory=list)
    places: list[PlaceReference] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    related_questions: list[str] = Field(default_factory=list)
    grounding_status: GroundingStatus = GroundingStatus.GROUNDED
    provider: str = 'none'
    model: str = 'none'

    @model_validator(mode='after')
    def validate_source_ids(self) -> ResearchResponse:
        seen_ids: set[str] = set()
        duplicates: set[str] = set()
        for source in self.sources:
            if source.id in seen_ids:
                duplicates.add(source.id)
            seen_ids.add(source.id)
        if duplicates:
            formatted = ', '.join(sorted(duplicates))
            raise ValueError(f'duplicate source ID: {formatted}')

        known_ids = {source.id for source in self.sources}

        def visit(value: Any) -> None:
            if isinstance(
                value,
                (ResearchClaim, TimelineEvent, PersonReference, PlaceReference),
            ):
                unknown_ids = set(value.source_ids) - known_ids
                if unknown_ids:
                    formatted = ', '.join(sorted(unknown_ids))
                    raise ValueError(f'unknown source ID: {formatted}')
            if isinstance(value, BaseModel):
                for field_name in type(value).model_fields:
                    visit(getattr(value, field_name))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for item in value.values():
                    visit(item)

        for field_name in type(self).model_fields:
            if field_name != 'sources':
                visit(getattr(self, field_name))
        return self
