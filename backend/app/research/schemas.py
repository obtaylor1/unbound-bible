"""Strict request and response contracts for scripture research."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceScope(StrEnum):
    BIBLICAL_CANON = 'biblical-canon'
    ETHIOPIAN_CANON = 'ethiopian-canon'
    ANCIENT_ACCOUNTS = 'ancient-accounts'
    HISTORICAL_SOURCES = 'historical-sources'
    COMMENTARIES = 'commentaries'
    LANGUAGE_RESOURCES = 'language-resources'
    USER_LIBRARY = 'user-library'
    ALL_SOURCES = 'all-sources'


class ResearchDepth(StrEnum):
    QUICK = 'quick'
    STANDARD = 'standard'
    DEEP = 'deep-research'


class ResearchMode(StrEnum):
    BETWEEN = 'what-happened-between'
    QUESTION = 'research-question'
    TIMELINE = 'timeline'
    PEOPLE_AND_PLACES = 'people-and-places'


class SourceClassification(StrEnum):
    BIBLICAL_CANON = 'biblical-canon'
    ANCIENT_ACCOUNT = 'ancient-account'
    HISTORICAL_SOURCE = 'historical-source'
    COMMENTARY = 'commentary'
    LANGUAGE_RESOURCE = 'language-resource'
    USER_SOURCE = 'user-source'


class ResearchConfidence(StrEnum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    DISPUTED = 'disputed'


class GroundingStatus(StrEnum):
    GROUNDED = 'grounded'
    PARTIALLY_GROUNDED = 'partially-grounded'
    EVIDENCE_ONLY = 'evidence-only'
    INSUFFICIENT_EVIDENCE = 'insufficient-evidence'


class StrictResearchModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


def _default_scopes() -> list[SourceScope]:
    return [SourceScope.BIBLICAL_CANON]


class ResearchSettings(StrictResearchModel):
    source_scopes: list[SourceScope] = Field(
        default_factory=_default_scopes, min_length=1, max_length=8
    )
    depth: ResearchDepth = ResearchDepth.DEEP
    mode_parameters: dict[str, str] = Field(default_factory=dict)

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
    classification: SourceClassification = SourceClassification.BIBLICAL_CANON
    reference: str | None = None
    excerpt: str | None = None
    author: str | None = None
    publication_date: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchClaim(StrictResearchModel):
    text: str = Field(min_length=1, max_length=50_000)
    source_ids: list[str] = Field(default_factory=list)
    confidence: ResearchConfidence = ResearchConfidence.MEDIUM


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


class ResearchQueryRequest(StrictResearchModel):
    question: str = Field(min_length=2, max_length=10_000)
    session_id: uuid.UUID | None = None
    parent_node_id: uuid.UUID | None = None
    mode: ResearchMode = ResearchMode.BETWEEN
    source_scopes: list[SourceScope] = Field(
        default_factory=_default_scopes, min_length=1, max_length=8
    )
    depth: ResearchDepth = ResearchDepth.DEEP
    mode_parameters: dict[str, str] = Field(default_factory=dict)

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
