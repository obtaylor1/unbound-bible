"""Strict, commit-safe metadata for an authorized scripture source."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from math import isfinite
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)


EditionCode = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
EditionName = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
LanguageOrScript = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
Contributor = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Attribution = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)
]
SourceTradition = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Versification = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
WorkId = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
SourcePath = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
AdapterId = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Checksum = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
ChapterCount = Annotated[StrictInt, Field(gt=0, le=200)]
VerseCount = Annotated[StrictInt, Field(gt=0, le=1000)]
PublishedYear = Annotated[StrictInt, Field(ge=1450, le=date.today().year)]
ChapterKey = Annotated[StrictStr, StringConstraints(pattern=r'^[1-9][0-9]*$')]

_LICENSES = Literal[
    'LicenseRef-Public-Domain',
    'CC0-1.0',
    'CC-BY-4.0',
    'CC-BY-SA-4.0',
]
_RELATIONSHIPS = Literal['exact_ethiopian', 'related_recension', 'general_reading']
_ADAPTER_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
_CAMEL_CASE_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')
_KEY_TOKEN = re.compile(r'[a-z0-9]+')
_SAFE_CONFIGURATION_NAMES = {
    'authmethod',
    'credentialsmode',
    'requiresauth',
    'requiresauthorization',
    'maxtokens',
}
_SECRET_COMPACT_NAMES = {
    'clientsecret',
    'accesstoken',
    'refreshtoken',
    'privatekey',
    'secretkey',
    'xapikey',
    'apikey',
    'tokenvalue',
    'token',
    'authorization',
    'auth',
    'bearer',
    'credential',
    'credentials',
    'password',
    'passwd',
}
_SECRET_TOKEN_PAIRS = {
    ('api', 'key'),
    ('secret', 'key'),
    ('client', 'secret'),
    ('token', 'value'),
    ('access', 'token'),
    ('refresh', 'token'),
    ('private', 'key'),
    ('access', 'key'),
}
_SECRET_VALUE_TOKENS = {
    'secret',
    'password',
    'passwd',
    'credential',
    'credentials',
    'bearer',
}


class ExpectedCoverage(BaseModel):
    """The coverage the source is expected to provide for one canonical work."""

    model_config = ConfigDict(extra='forbid', strict=True)

    chapters: ChapterCount
    verse_counts: dict[ChapterKey, VerseCount] = Field(default_factory=dict)

    @model_validator(mode='after')
    def verse_counts_are_within_declared_chapters(self) -> ExpectedCoverage:
        if any(int(chapter) > self.chapters for chapter in self.verse_counts):
            raise ValueError('verse_counts may not include chapters beyond chapters.')
        return self


class SourceFile(BaseModel):
    """An immutable source artifact used by an ingest adapter."""

    model_config = ConfigDict(extra='forbid', strict=True)

    path: SourcePath
    sha256: Checksum
    source_url: HttpUrl | None = None

    @field_validator('path')
    @classmethod
    def path_is_relative_posix_source_path(cls, value: str) -> str:
        normalized = unicodedata.normalize('NFC', value)
        segments = normalized.split('/')
        if normalized.startswith('/') or '\\' in normalized:
            raise ValueError('source path must be a relative POSIX path.')
        if re.match(r'^[A-Za-z]:', normalized):
            raise ValueError('source path must not contain a drive prefix.')
        if any(not segment or segment in {'.', '..'} for segment in segments):
            raise ValueError('source path must not contain empty, dot, or traversal segments.')
        if any(
            unicodedata.category(character).startswith('C')
            for segment in segments
            for character in segment
        ):
            raise ValueError('source path must not contain control characters.')
        return normalized

    @field_validator('sha256', mode='before')
    @classmethod
    def normalize_checksum(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator('source_url')
    @classmethod
    def source_url_is_commit_safe(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None:
            _validate_commit_safe_url(value)
        return value


class SourceManifest(BaseModel):
    """Licensed provenance and expected coverage for a scripture edition."""

    model_config = ConfigDict(extra='forbid', strict=True)

    edition_code: EditionCode
    name: EditionName
    reading_language: LanguageOrScript
    source_language: LanguageOrScript
    script: LanguageOrScript
    translator: Contributor | None
    publisher: Contributor | None
    published_year: PublishedYear | None
    license_spdx: _LICENSES
    attribution: Attribution
    provenance_url: HttpUrl
    source_tradition: SourceTradition
    relationship: _RELATIONSHIPS
    versification: Versification
    expected_works: dict[WorkId, ExpectedCoverage]
    source_files: list[SourceFile]
    adapter: AdapterId
    adapter_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator('provenance_url')
    @classmethod
    def provenance_url_is_commit_safe(cls, value: HttpUrl) -> HttpUrl:
        _validate_commit_safe_url(value)
        return value

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
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError('adapter_options numbers must be finite.')
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


def _key_tokens(key: str) -> tuple[str, ...]:
    expanded = _CAMEL_CASE_BOUNDARY.sub(' ', key)
    return tuple(_KEY_TOKEN.findall(expanded.casefold()))


def _is_secret_key(key: str) -> bool:
    tokens = _key_tokens(key)
    if not tokens:
        return False
    compact_name = ''.join(tokens)
    if compact_name in _SAFE_CONFIGURATION_NAMES:
        return False
    if compact_name in _SECRET_COMPACT_NAMES:
        return True
    if any(token in {'auth', 'authorization'} for token in tokens):
        return True
    if any(token in _SECRET_VALUE_TOKENS for token in tokens):
        return True
    return any(pair in _SECRET_TOKEN_PAIRS for pair in zip(tokens, tokens[1:]))


def _is_secret_query_parameter(name: str) -> bool:
    tokens = _key_tokens(name)
    return (
        _is_secret_key(name)
        or any(token in {'key', 'sig', 'signature'} for token in tokens)
    )


def _validate_commit_safe_url(url: HttpUrl) -> None:
    if len(str(url)) > 2048:
        raise ValueError('URL must not exceed 2048 serialized characters.')
    if url.username is not None or url.password is not None:
        raise ValueError('URL must not include embedded credentials.')
    for query_name, _ in parse_qsl(url.query or '', keep_blank_values=True):
        if _is_secret_query_parameter(query_name):
            raise ValueError('URL must not include secret-like query parameters.')
    fragment = url.fragment or ''
    if '=' in fragment:
        for fragment_name, _ in parse_qsl(fragment, keep_blank_values=True):
            if _is_secret_query_parameter(fragment_name):
                raise ValueError('URL fragment must not include secret-like parameters.')
