"""Immutable values used by scripture source verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


_ALLOWED_UNICODE_FORMS = frozenset({'NFC', 'NFD', 'NFKC', 'NFKD'})
_SHA256_PATTERN = re.compile(r'[0-9a-f]{64}\Z')


def _validate_normalized_identifier(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f'{name} must be a string.')
    if not value or value != value.strip() or unicodedata.normalize('NFC', value) != value:
        raise ValueError(f'{name} must be nonblank, trimmed, and NFC-normalized.')
    return value


def _validate_nonblank_string(name: str, value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f'{name} must be a nonblank string.')
    return value


def _validate_sha256(name: str, value: object) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f'{name} must be a lowercase 64-character SHA-256 checksum.')
    return value


def _validate_position(chapter: object, verse: object) -> None:
    if (
        type(chapter) is not int
        or type(verse) is not int
        or chapter <= 0
        or verse <= 0
    ):
        raise ValueError('chapter and verse must be positive integers.')


@dataclass(frozen=True, slots=True, order=True)
class VersePosition:
    chapter: int
    verse: int

    def __post_init__(self) -> None:
        _validate_position(self.chapter, self.verse)


@dataclass(frozen=True, slots=True)
class SourceVerse:
    """One verse with untouched evidence text."""

    work_id: str
    chapter: int
    verse: int
    text: str

    def __post_init__(self) -> None:
        _validate_normalized_identifier('work_id', self.work_id)
        _validate_position(self.chapter, self.verse)
        if type(self.text) is not str:
            raise ValueError('text must be a string.')

    @property
    def position(self) -> VersePosition:
        return VersePosition(self.chapter, self.verse)


@dataclass(frozen=True, slots=True)
class ComparisonRules:
    unicode_form: str = 'NFC'
    normalize_line_endings: bool = True
    collapse_whitespace: bool = True

    def __post_init__(self) -> None:
        if (
            type(self.unicode_form) is not str
            or self.unicode_form not in _ALLOWED_UNICODE_FORMS
        ):
            raise ValueError(
                'unicode_form must be one of NFC, NFD, NFKC, or NFKD.'
            )
        if type(self.normalize_line_endings) is not bool:
            raise ValueError('normalize_line_endings must be a boolean.')
        if type(self.collapse_whitespace) is not bool:
            raise ValueError('collapse_whitespace must be a boolean.')


class DifferenceClassification(str, Enum):
    FORMATTING = 'formatting'
    MISSING = 'missing'
    EXTRA = 'extra'
    WORDING = 'wording'


@dataclass(frozen=True, slots=True)
class ComparisonCounts:
    exact: int = 0
    formatting: int = 0
    missing: int = 0
    extra: int = 0
    wording: int = 0

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (
                self.exact, self.formatting, self.missing, self.extra, self.wording,
            )
        ):
            raise ValueError('comparison counts must be nonnegative integers.')


@dataclass(frozen=True, slots=True)
class VerseDifference:
    position: VersePosition
    classification: DifferenceClassification
    current_text: str | None
    source_text: str | None

    def __post_init__(self) -> None:
        if type(self.position) is not VersePosition:
            raise ValueError('position must be a VersePosition.')
        if type(self.classification) is not DifferenceClassification:
            raise ValueError('classification must be a DifferenceClassification.')
        if self.current_text is not None and type(self.current_text) is not str:
            raise ValueError('current_text must be a string or None.')
        if self.source_text is not None and type(self.source_text) is not str:
            raise ValueError('source_text must be a string or None.')
        if self.classification in {
            DifferenceClassification.FORMATTING,
            DifferenceClassification.WORDING,
        }:
            valid_shape = type(self.current_text) is str and type(self.source_text) is str
        elif self.classification is DifferenceClassification.MISSING:
            valid_shape = self.current_text is None and type(self.source_text) is str
        else:
            valid_shape = type(self.current_text) is str and self.source_text is None
        if not valid_shape:
            raise ValueError('current_text and source_text must match the classification.')


@dataclass(frozen=True, slots=True)
class SourceArtifactIdentity:
    sha256: str

    def __post_init__(self) -> None:
        _validate_sha256('source_artifact_sha256', self.sha256)


@dataclass(frozen=True, slots=True)
class CurrentPublicationIdentity:
    sha256: str

    def __post_init__(self) -> None:
        _validate_sha256('current_publication_sha256', self.sha256)


@dataclass(frozen=True, slots=True)
class WorkComparisonReport:
    schema_version: int
    work_id: str
    source_artifact: SourceArtifactIdentity
    current_publication: CurrentPublicationIdentity
    parser_version: str
    rules: ComparisonRules
    totals: ComparisonCounts
    declared_omissions: tuple[VersePosition, ...]
    differences: tuple[VerseDifference, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise ValueError('schema_version must be 1.')
        _validate_normalized_identifier('work_id', self.work_id)
        _validate_nonblank_string('parser_version', self.parser_version)
        if type(self.source_artifact) is not SourceArtifactIdentity:
            raise ValueError('source_artifact must be a SourceArtifactIdentity.')
        if type(self.current_publication) is not CurrentPublicationIdentity:
            raise ValueError('current_publication must be a CurrentPublicationIdentity.')
        if type(self.rules) is not ComparisonRules:
            raise ValueError('rules must be ComparisonRules.')
        if type(self.totals) is not ComparisonCounts:
            raise ValueError('totals must be ComparisonCounts.')
        if type(self.declared_omissions) is not tuple or any(
            type(position) is not VersePosition for position in self.declared_omissions
        ):
            raise ValueError('declared_omissions must be a tuple of VersePosition values.')
        if type(self.differences) is not tuple or any(
            type(difference) is not VerseDifference for difference in self.differences
        ):
            raise ValueError('differences must be a tuple of VerseDifference values.')

        omission_positions = self.declared_omissions
        if (
            len(set(omission_positions)) != len(omission_positions)
            or tuple(sorted(omission_positions)) != omission_positions
        ):
            raise ValueError('declared_omissions must have unique strictly sorted positions.')

        difference_positions = tuple(
            difference.position for difference in self.differences
        )
        if (
            len(set(difference_positions)) != len(difference_positions)
            or tuple(sorted(difference_positions)) != difference_positions
        ):
            raise ValueError('differences must have unique strictly sorted positions.')
        if set(omission_positions) & set(difference_positions):
            raise ValueError('declared omissions and differences must not overlap.')

        difference_counts = {
            classification: sum(
                difference.classification is classification
                for difference in self.differences
            )
            for classification in DifferenceClassification
        }
        if any(
            getattr(self.totals, classification.value) != difference_counts[classification]
            for classification in DifferenceClassification
        ):
            raise ValueError('totals must exactly match the classified differences.')

    @property
    def is_verified_candidate(self) -> bool:
        disqualifying = {
            DifferenceClassification.MISSING,
            DifferenceClassification.EXTRA,
            DifferenceClassification.WORDING,
        }
        return not any(
            difference.classification in disqualifying
            for difference in self.differences
        )
