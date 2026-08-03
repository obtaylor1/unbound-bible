"""Strict, commit-safe metadata for an authorized scripture source."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)


NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Checksum = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
PositiveInteger = Annotated[int, Field(gt=0)]
PublishedYear = Annotated[int, Field(ge=1450, le=2500)]

_LICENSES = Literal[
    'LicenseRef-Public-Domain',
    'CC0-1.0',
    'CC-BY-4.0',
    'CC-BY-SA-4.0',
]
_RELATIONSHIPS = Literal['exact_ethiopian', 'related_recension', 'general_reading']
_ADAPTER_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')


class ExpectedCoverage(BaseModel):
    """The coverage the source is expected to provide for one canonical work."""

    model_config = ConfigDict(extra='forbid')

    chapters: PositiveInteger
    verse_counts: dict[PositiveInteger, PositiveInteger] = Field(default_factory=dict)

    @model_validator(mode='after')
    def verse_counts_are_within_declared_chapters(self) -> ExpectedCoverage:
        if any(chapter > self.chapters for chapter in self.verse_counts):
            raise ValueError('verse_counts may not include chapters beyond chapters.')
        return self


class SourceFile(BaseModel):
    """An immutable source artifact used by an ingest adapter."""

    model_config = ConfigDict(extra='forbid')

    path: NonBlankString
    sha256: Checksum
    source_url: HttpUrl | None = None

    @field_validator('sha256', mode='before')
    @classmethod
    def normalize_checksum(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class SourceManifest(BaseModel):
    """Licensed provenance and expected coverage for a scripture edition."""

    model_config = ConfigDict(extra='forbid')

    edition_code: NonBlankString
    name: NonBlankString
    reading_language: NonBlankString
    source_language: NonBlankString
    script: NonBlankString
    translator: NonBlankString | None
    publisher: NonBlankString | None
    published_year: PublishedYear | None
    license_spdx: _LICENSES
    attribution: NonBlankString
    provenance_url: HttpUrl
    source_tradition: NonBlankString
    relationship: _RELATIONSHIPS
    versification: NonBlankString
    expected_works: dict[NonBlankString, ExpectedCoverage]
    source_files: list[SourceFile]
    adapter: NonBlankString
    adapter_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator('adapter')
    @classmethod
    def adapter_is_a_conservative_identifier(cls, value: str) -> str:
        if not _ADAPTER_PATTERN.fullmatch(value):
            raise ValueError('adapter must contain only letters, numbers, underscores, or hyphens.')
        return value

    @field_validator('expected_works', mode='before')
    @classmethod
    def normalize_and_validate_work_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError('expected_works must be a nonempty mapping.')

        normalized: dict[str, Any] = {}
        seen: set[str] = set()
        for work_id, coverage in value.items():
            if not isinstance(work_id, str):
                raise ValueError('expected_works keys must be nonblank work IDs.')
            cleaned = work_id.strip()
            identity = ' '.join(cleaned.casefold().split())
            if not identity:
                raise ValueError('expected_works keys must be nonblank work IDs.')
            if identity in seen:
                raise ValueError('expected_works cannot contain duplicate normalized work IDs.')
            seen.add(identity)
            normalized[cleaned] = coverage
        return normalized

    @field_validator('source_files')
    @classmethod
    def source_files_are_unique_and_present(cls, value: list[SourceFile]) -> list[SourceFile]:
        if not value:
            raise ValueError('source_files must contain at least one source record.')
        paths = [source.path.casefold() for source in value]
        if len(paths) != len(set(paths)):
            raise ValueError('source_files paths must be unique.')
        return value

    @field_validator('adapter_options', mode='before')
    @classmethod
    def adapter_options_do_not_contain_secrets(
        cls, value: Any
    ) -> Any:
        if not isinstance(value, dict):
            raise ValueError('adapter_options must be a JSON-compatible dictionary.')
        _raise_for_non_json_or_secret_option(value)
        return value


def _raise_for_non_json_or_secret_option(value: Any) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError('adapter_options dictionary keys must be strings.')
            if _is_secret_key(key):
                raise ValueError('adapter_options may not include secret fields.')
            _raise_for_non_json_or_secret_option(nested_value)
        return
    if isinstance(value, list):
        for item in value:
            _raise_for_non_json_or_secret_option(item)
        return
    raise ValueError('adapter_options must contain only JSON-compatible values.')
def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r'[^a-z0-9]', '', key.casefold())
    return normalized == 'apikey' or normalized.endswith('token') or normalized.endswith('password')
