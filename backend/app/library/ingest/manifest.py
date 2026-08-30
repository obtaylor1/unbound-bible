"""Strict, commit-safe metadata for an authorized scripture source."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationInfo,
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
AdapterId = Literal[
    'usfm', 'ertale', 'wikisource', 'weahadu_bundle',
    'composite_english_bundle',
]
Checksum = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
VerificationStatus = Literal[
    'in_progress',
    'verified_exact',
    'verified_formatting',
    'verified_rebuilt',
    'review_required',
]
VERIFIED_STATUSES = {
    'verified_exact', 'verified_formatting', 'verified_rebuilt',
}
SourceEdition = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
SourceRevision = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
RightsJurisdiction = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ArtifactFilename = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
ParserVersion = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
Transformation = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Transformations = Annotated[list[Transformation], Field(max_length=100)]
ComparisonCount = Annotated[StrictInt, Field(ge=0)]
ChapterCount = Annotated[StrictInt, Field(gt=0, le=200)]
VerseCount = Annotated[StrictInt, Field(gt=0, le=1000)]
MissingVerseNumber = Annotated[StrictInt, Field(ge=1, le=1000)]
PublishedYear = Annotated[StrictInt, Field(ge=1450, le=date.today().year)]
ChapterKey = Annotated[StrictStr, StringConstraints(pattern=r'^[1-9][0-9]*$')]
MissingVerseNumbers = Annotated[
    list[MissingVerseNumber],
    Field(min_length=1, json_schema_extra={'uniqueItems': True}),
]

_LICENSES = Literal[
    'LicenseRef-Public-Domain',
    'CC0-1.0',
    'CC-BY-4.0',
    'CC-BY-SA-4.0',
    'CC-BY-NC-ND-4.0',
    'LicenseRef-Mixed',
]
_RELATIONSHIPS = Literal['exact_ethiopian', 'related_recension', 'general_reading']
_CAMEL_CASE_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')
_KEY_TOKEN = re.compile(r'[a-z0-9]+')
_URL_SECRET_EXACT = {'sig', 'key', 'auth', 'authorization', 'bearer'}
_URL_SECRET_SUFFIXES = (
    'token', 'secret', 'password', 'passwd', 'credential', 'credentials',
    'signature',
)
_URL_SECURITY_KEY_PREFIXES = {
    'api', 'access', 'private', 'secret', 'signing', 'encryption', 'session',
}
_URL_AUTH_COMPOUNDS = {
    'basicauth', 'authheader', 'authorizationheader', 'sessioncookie',
}

SourceBookCode = Annotated[
    StrictStr,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
    ),
]
ExportedPageId = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
TextEncoding = Literal['utf-8', 'utf-8-sig']


def _normalize_mapping_keys(
    value: Any, *, case_insensitive: bool
) -> Any:
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    seen: set[str] = set()
    for key, mapped_work in value.items():
        if not isinstance(key, str):
            raise ValueError('adapter mapping keys must be strings.')
        cleaned = unicodedata.normalize('NFC', key.strip())
        identity = cleaned.casefold() if case_insensitive else cleaned
        if identity in seen:
            raise ValueError('adapter mapping keys must be unique after normalization.')
        seen.add(identity)
        normalized[cleaned] = mapped_work
    return normalized


def _normalize_work_ids(
    values: Any, *, field_name: str, enforce_unique: bool = True,
    exact_duplicate_message: str | None = None,
) -> Any:
    if not isinstance(values, (list, tuple)):
        values = list(values)

    normalized: list[str] = []
    seen: set[str] = set()
    raw_seen: set[str] = set()
    for work_id in values:
        if not isinstance(work_id, str):
            raise ValueError(f'{field_name} must contain nonblank work IDs.')
        cleaned = unicodedata.normalize('NFC', work_id.strip())
        identity = ' '.join(cleaned.casefold().split())
        if not identity:
            raise ValueError(f'{field_name} must contain nonblank work IDs.')
        if enforce_unique and identity in seen:
            if exact_duplicate_message is not None and work_id.strip() in raw_seen:
                raise ValueError(exact_duplicate_message)
            raise ValueError(
                f'{field_name} cannot contain duplicate normalized work IDs.'
            )
        seen.add(identity)
        raw_seen.add(work_id.strip())
        normalized.append(cleaned)
    return normalized


def _normalize_work_id_mapping_keys(value: Any, *, field_name: str) -> Any:
    if not isinstance(value, dict):
        return value
    normalized_keys = _normalize_work_ids(
        value.keys(), field_name=f'{field_name} keys'
    )
    return dict(zip(normalized_keys, value.values()))


def _normalize_mapping_work_ids(
    value: dict[str, str], *, field_name: str, enforce_unique: bool,
    exact_duplicate_message: str | None = None,
) -> dict[str, str]:
    normalized_values = _normalize_work_ids(
        value.values(), field_name=field_name, enforce_unique=enforce_unique,
        exact_duplicate_message=exact_duplicate_message,
    )
    return dict(zip(value.keys(), normalized_values))


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


class WorkSourceManifest(BaseModel):
    """Per-work provenance for a mixed-source scripture bundle."""

    model_config = ConfigDict(extra='forbid', strict=True)

    source_key: SourceBookCode
    source_label: EditionName
    translator: Contributor | None
    source_language: LanguageOrScript
    source_tradition: SourceTradition
    published_year: PublishedYear | None
    license_spdx: _LICENSES
    attribution: Attribution
    provenance_url: HttpUrl | None
    fallback: StrictBool = False
    modified: StrictBool = False
    modification_note: Attribution | None = None
    verification_status: VerificationStatus
    canon_scope: Literal['ethio81', 'supplemental']
    source_edition: SourceEdition | None = None
    source_revision: SourceRevision | None = None
    rights_url: HttpUrl | None = None
    rights_jurisdiction: RightsJurisdiction | None = None
    artifact_filename: ArtifactFilename | None = None
    artifact_retrieved_at: datetime | None = None
    artifact_size: Annotated[StrictInt, Field(ge=0)] | None = None
    artifact_sha256: Checksum | None = None
    parser_version: ParserVersion | None = None
    transformations: Transformations = Field(default_factory=list)
    comparison_exact: ComparisonCount = 0
    comparison_formatting: ComparisonCount = 0
    comparison_missing: ComparisonCount = 0
    comparison_extra: ComparisonCount = 0
    comparison_wording: ComparisonCount = 0
    comparison_report_sha256: Checksum | None = None
    reviewer: Contributor | None = None
    reviewed_at: datetime | None = None
    review_note: Attribution | None = None

    @field_validator('provenance_url', 'rights_url')
    @classmethod
    def evidence_url_is_commit_safe(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None:
            _validate_commit_safe_url(value)
        return value

    @field_validator('artifact_filename')
    @classmethod
    def artifact_filename_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = unicodedata.normalize('NFC', value)
        if normalized in {'.', '..'} or '/' in normalized or '\\' in normalized:
            raise ValueError('artifact_filename must be a filename without path segments.')
        if re.match(r'^[A-Za-z]:', normalized):
            raise ValueError('artifact_filename must not contain a drive prefix.')
        if any(unicodedata.category(character).startswith('C') for character in normalized):
            raise ValueError('artifact_filename must not contain control characters.')
        return normalized

    @field_validator('artifact_retrieved_at', 'reviewed_at', mode='before')
    @classmethod
    def parse_evidence_timestamp(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError as error:
                raise ValueError('evidence timestamp must be valid ISO-8601.') from error
        return value

    @field_validator('artifact_retrieved_at', 'reviewed_at')
    @classmethod
    def evidence_timestamp_is_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError('evidence timestamp must be timezone-aware.')
        return value

    @model_validator(mode='after')
    def provenance_and_modification_are_complete(self) -> WorkSourceManifest:
        if self.modified and self.modification_note is None:
            raise ValueError('modified work source requires modification_note.')
        if self.verification_status not in VERIFIED_STATUSES:
            return self

        required_evidence = (
            'provenance_url', 'source_edition', 'source_revision', 'rights_url',
            'rights_jurisdiction', 'artifact_filename', 'artifact_retrieved_at',
            'artifact_size', 'artifact_sha256', 'parser_version',
            'comparison_report_sha256', 'reviewer', 'reviewed_at',
        )
        for field_name in required_evidence:
            if getattr(self, field_name) is None:
                raise ValueError(
                    f'verified work source requires {field_name}.'
                )
        for field_name in (
            'comparison_missing', 'comparison_extra', 'comparison_wording'
        ):
            if getattr(self, field_name) != 0:
                raise ValueError(
                    f'verified work source requires {field_name} to be zero.'
                )
        if (
            self.verification_status == 'verified_formatting'
            and not self.transformations
        ):
            raise ValueError(
                'verified_formatting work source requires a transformation.'
            )
        if self.verification_status == 'verified_rebuilt' and not self.modified:
            raise ValueError('verified_rebuilt work source requires modified=true.')
        return self


class UsfmAdapterOptions(BaseModel):
    """Reviewed options for local USFM sources."""

    model_config = ConfigDict(extra='forbid', strict=True)

    encoding: TextEncoding = 'utf-8'
    book_map: dict[SourceBookCode, WorkId] = Field(default_factory=dict)
    strip_notes: StrictBool = False

    @field_validator('book_map', mode='before')
    @classmethod
    def normalize_book_map_keys(cls, value: Any) -> Any:
        return _normalize_mapping_keys(value, case_insensitive=True)

    @field_validator('book_map')
    @classmethod
    def normalize_book_map_work_ids(cls, value: dict[str, str]) -> dict[str, str]:
        return _normalize_mapping_work_ids(
            value, field_name='book_map targets', enforce_unique=False
        )


class ErtaleAdapterOptions(BaseModel):
    """Reviewed options for Ertale exports."""

    model_config = ConfigDict(extra='forbid', strict=True)

    encoding: TextEncoding = 'utf-8'
    book_map: dict[SourceBookCode, WorkId] = Field(default_factory=dict)

    @field_validator('book_map', mode='before')
    @classmethod
    def normalize_book_map_keys(cls, value: Any) -> Any:
        return _normalize_mapping_keys(value, case_insensitive=True)

    @field_validator('book_map')
    @classmethod
    def normalize_book_map_work_ids(cls, value: dict[str, str]) -> dict[str, str]:
        return _normalize_mapping_work_ids(
            value, field_name='book_map targets', enforce_unique=False
        )


class WikisourceAdapterOptions(BaseModel):
    """Reviewed options for Wikisource page exports."""

    model_config = ConfigDict(extra='forbid', strict=True)

    encoding: TextEncoding = 'utf-8'
    page_map: dict[ExportedPageId, WorkId] = Field(default_factory=dict)

    @field_validator('page_map', mode='before')
    @classmethod
    def normalize_page_map_keys(cls, value: Any) -> Any:
        return _normalize_mapping_keys(value, case_insensitive=False)

    @field_validator('page_map')
    @classmethod
    def normalize_page_map_work_ids(cls, value: dict[str, str]) -> dict[str, str]:
        return _normalize_mapping_work_ids(
            value, field_name='page_map targets', enforce_unique=False
        )


class WeahaduBundleAdapterOptions(BaseModel):
    """Select one edition and an explicit work allowlist from a frozen bundle."""

    model_config = ConfigDict(extra='forbid', strict=True)

    edition: SourceBookCode
    book_map: dict[SourceBookCode, WorkId]

    @field_validator('book_map', mode='before')
    @classmethod
    def normalize_book_map_keys(cls, value: Any) -> Any:
        return _normalize_mapping_keys(value, case_insensitive=True)

    @field_validator('book_map')
    @classmethod
    def book_map_is_not_empty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError('book_map must contain at least one reviewed source book.')
        return _normalize_mapping_work_ids(
            value, field_name='book_map targets', enforce_unique=True,
            exact_duplicate_message=(
                'book_map may not map multiple source books to one work.'
            ),
        )


class CompositeEnglishBundleAdapterOptions(BaseModel):
    """Map a reviewed English bundle with per-work source provenance."""

    model_config = ConfigDict(extra='forbid', strict=True)

    book_map: dict[SourceBookCode, WorkId]
    work_sources: dict[WorkId, WorkSourceManifest]
    supplemental_works: list[WorkId] = Field(default_factory=list)
    known_missing_verses: dict[
        WorkId, dict[ChapterKey, MissingVerseNumbers]
    ] = Field(default_factory=dict)

    @field_validator('book_map', mode='before')
    @classmethod
    def normalize_book_map_keys(cls, value: Any) -> Any:
        return _normalize_mapping_keys(value, case_insensitive=True)

    @field_validator('book_map')
    @classmethod
    def normalize_book_map_work_ids(cls, value: dict[str, str]) -> dict[str, str]:
        return _normalize_mapping_work_ids(
            value, field_name='book_map targets', enforce_unique=True,
            exact_duplicate_message=(
                'book_map may not map multiple source books to one work.'
            ),
        )

    @field_validator('work_sources', mode='before')
    @classmethod
    def normalize_work_source_keys(cls, value: Any) -> Any:
        return _normalize_work_id_mapping_keys(value, field_name='work_sources')

    @field_validator('known_missing_verses', mode='before')
    @classmethod
    def normalize_missing_verse_work_keys(cls, value: Any) -> Any:
        return _normalize_work_id_mapping_keys(
            value, field_name='known_missing_verses'
        )

    @field_validator('known_missing_verses')
    @classmethod
    def missing_verse_lists_are_strictly_sorted(
        cls, value: dict[str, dict[str, list[int]]]
    ) -> dict[str, dict[str, list[int]]]:
        for work_id, chapters in value.items():
            for chapter, verses in chapters.items():
                if not verses:
                    raise ValueError(
                        'known_missing_verses verse lists must be nonempty.'
                    )
                if any(left >= right for left, right in zip(verses, verses[1:])):
                    raise ValueError(
                        'known_missing_verses verse lists must be strictly sorted '
                        'ascending and unique.'
                    )
        return value

    @field_validator('supplemental_works', mode='before')
    @classmethod
    def normalize_supplemental_work_ids(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return _normalize_work_ids(value, field_name='supplemental_works')

    @model_validator(mode='after')
    def mappings_and_canon_scopes_agree(self) -> CompositeEnglishBundleAdapterOptions:
        targets = list(self.book_map.values())
        target_set = set(targets)
        if set(self.work_sources) != target_set:
            raise ValueError('work_sources keys must exactly match book_map targets.')

        supplemental = set(self.supplemental_works)
        if not supplemental <= target_set:
            raise ValueError('supplemental_works must be a subset of book_map targets.')

        for work_id, source in self.work_sources.items():
            expected_scope = 'supplemental' if work_id in supplemental else 'ethio81'
            if source.canon_scope != expected_scope:
                raise ValueError(
                    f'work source canon_scope for {work_id!r} must be {expected_scope!r}.'
                )

        unknown_missing = set(self.known_missing_verses) - target_set
        if unknown_missing:
            work_id = sorted(unknown_missing, key=str.casefold)[0]
            raise ValueError(
                'known_missing_verses work '
                f'{work_id!r} must be a mapped book_map target.'
            )
        return self


AdapterOptions = (
    UsfmAdapterOptions
    | ErtaleAdapterOptions
    | WikisourceAdapterOptions
    | WeahaduBundleAdapterOptions
    | CompositeEnglishBundleAdapterOptions
)
_ADAPTER_OPTIONS_MODELS: dict[AdapterId, type[BaseModel]] = {
    'usfm': UsfmAdapterOptions,
    'ertale': ErtaleAdapterOptions,
    'wikisource': WikisourceAdapterOptions,
    'weahadu_bundle': WeahaduBundleAdapterOptions,
    'composite_english_bundle': CompositeEnglishBundleAdapterOptions,
}
_REQUIRED_ADAPTER_OPTIONS = {'weahadu_bundle', 'composite_english_bundle'}


def _standalone_model_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    definitions = schema.pop('$defs', {})

    def inline_local_references(value: Any) -> Any:
        if isinstance(value, list):
            return [inline_local_references(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get('$ref')
        if isinstance(reference, str) and reference.startswith('#/$defs/'):
            definition_name = reference.removeprefix('#/$defs/')
            return inline_local_references(definitions[definition_name])
        return {
            key: inline_local_references(item)
            for key, item in value.items()
        }

    return inline_local_references(schema)


_ADAPTER_SCHEMA_CORRELATIONS = [
    {
        'if': {
            'properties': {'adapter': {'const': adapter}},
            'required': ['adapter'],
        },
        'then': {
            'properties': {
                'adapter_options': _standalone_model_schema(options_model),
            },
            **(
                {'required': ['adapter_options']}
                if adapter in _REQUIRED_ADAPTER_OPTIONS else {}
            ),
        },
    }
    for adapter, options_model in _ADAPTER_OPTIONS_MODELS.items()
]


class SourceManifest(BaseModel):
    """Licensed provenance and expected coverage for a scripture edition."""

    model_config = ConfigDict(
        extra='forbid',
        strict=True,
        json_schema_extra={'allOf': _ADAPTER_SCHEMA_CORRELATIONS},
    )

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
    adapter_options: AdapterOptions = Field(default_factory=UsfmAdapterOptions)
    source_verification: Literal['provisional', 'verified'] = 'verified'

    @model_validator(mode='before')
    @classmethod
    def default_adapter_options(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if 'adapter_options' in value:
            return value
        normalized = dict(value)
        normalized['adapter_options'] = {}
        return normalized

    @field_validator('adapter_options', mode='before')
    @classmethod
    def validate_adapter_options_for_adapter(
        cls, value: Any, info: ValidationInfo
    ) -> Any:
        options_model = _ADAPTER_OPTIONS_MODELS.get(info.data.get('adapter'))
        return options_model.model_validate(value) if options_model else value

    @field_validator('provenance_url')
    @classmethod
    def provenance_url_is_commit_safe(cls, value: HttpUrl) -> HttpUrl:
        _validate_commit_safe_url(value)
        return value

    @field_validator('expected_works', mode='before')
    @classmethod
    def normalize_and_validate_work_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError('expected_works must be a nonempty mapping.')
        return _normalize_work_id_mapping_keys(value, field_name='expected_works')

    @field_validator('source_files')
    @classmethod
    def source_files_are_unique_and_present(cls, value: list[SourceFile]) -> list[SourceFile]:
        if not value:
            raise ValueError('source_files must contain at least one source record.')
        paths = [source.path.casefold() for source in value]
        if len(paths) != len(set(paths)):
            raise ValueError('source_files paths must be unique.')
        return value

    @model_validator(mode='after')
    def source_verification_agrees_with_work_sources(self) -> SourceManifest:
        if not isinstance(self.adapter_options, CompositeEnglishBundleAdapterOptions):
            return self
        if self.source_verification == 'verified' and any(
            source.verification_status not in VERIFIED_STATUSES
            for source in self.adapter_options.work_sources.values()
        ):
            raise ValueError(
                'verified source_verification requires all work sources to be verified.'
            )
        for work_id, chapters in self.adapter_options.known_missing_verses.items():
            coverage = self.expected_works.get(work_id)
            if coverage is None:
                raise ValueError(
                    'known_missing_verses work must also be declared in expected_works.'
                )
            declared_chapters = coverage.chapters
            if any(int(chapter) > declared_chapters for chapter in chapters):
                raise ValueError(
                    'known_missing_verses chapter may not exceed the work\'s '
                    'declared expected chapter count.'
                )
        return self


def _key_tokens(key: str) -> tuple[str, ...]:
    expanded = _CAMEL_CASE_BOUNDARY.sub(' ', key)
    return tuple(_KEY_TOKEN.findall(expanded.casefold()))


def _compact_key(key: str) -> str:
    return ''.join(_KEY_TOKEN.findall(key.casefold()))


def _is_secret_url_parameter(name: str) -> bool:
    tokens = _key_tokens(name)
    compact_name = _compact_key(name)
    if compact_name in _URL_SECRET_EXACT | _URL_AUTH_COMPOUNDS:
        return True
    if compact_name.endswith('value'):
        return _is_secret_url_parameter(compact_name[:-len('value')])
    if compact_name.endswith(_URL_SECRET_SUFFIXES):
        return True
    if any(
        compact_name.endswith(f'{prefix}key')
        for prefix in _URL_SECURITY_KEY_PREFIXES
    ):
        return True
    return any(
        first in _URL_SECURITY_KEY_PREFIXES and second == 'key'
        for first, second in zip(tokens, tokens[1:])
    )


def _validate_commit_safe_url(url: HttpUrl) -> None:
    if len(str(url)) > 2048:
        raise ValueError('URL must not exceed 2048 serialized characters.')
    if url.username is not None or url.password is not None:
        raise ValueError('URL must not include embedded credentials.')
    for query_name, _ in parse_qsl(url.query or '', keep_blank_values=True):
        if _is_secret_url_parameter(query_name):
            raise ValueError('URL must not include secret-like query parameters.')
    fragment = url.fragment or ''
    if '=' in fragment:
        for fragment_name, _ in parse_qsl(fragment, keep_blank_values=True):
            if _is_secret_url_parameter(fragment_name):
                raise ValueError('URL fragment must not include secret-like parameters.')
