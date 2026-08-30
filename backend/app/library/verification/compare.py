"""Pure deterministic comparison of current and source scripture verses."""

from __future__ import annotations

from collections.abc import Iterable

from app.library.verification.normalize import normalize_exact, normalize_formatting
from app.library.verification.types import (
    ComparisonCounts,
    ComparisonRules,
    CurrentPublicationIdentity,
    DifferenceClassification,
    SourceArtifactIdentity,
    SourceVerse,
    VerseDifference,
    VersePosition,
    WorkComparisonReport,
    _validate_nonblank_string,
    _validate_normalized_identifier,
)


def _index_rows(
    rows: Iterable[SourceVerse], work_id: str, side: str,
) -> dict[VersePosition, SourceVerse]:
    indexed: dict[VersePosition, SourceVerse] = {}
    for row in rows:
        if type(row) is not SourceVerse:
            raise ValueError(f'{side} rows must be SourceVerse values.')
        if row.work_id != work_id:
            raise ValueError(f'{side} row work_id must match requested work_id.')
        if row.position in indexed:
            raise ValueError(f'duplicate position in {side} dataset: {row.chapter}:{row.verse}.')
        indexed[row.position] = row
    if not indexed:
        raise ValueError(f'{side} dataset must not be empty.')
    return indexed


def _omission_position(value: object) -> VersePosition:
    if type(value) is VersePosition:
        return value
    if type(value) in (tuple, list) and len(value) == 2:
        try:
            return VersePosition(value[0], value[1])
        except ValueError as exc:
            raise ValueError(f'invalid declared omission: {value!r}.') from exc
    raise ValueError(f'invalid declared omission: {value!r}.')


def _validated_omissions(
    values: Iterable[VersePosition | tuple[int, int]],
    occupied: set[VersePosition],
) -> tuple[VersePosition, ...]:
    omissions: set[VersePosition] = set()
    for value in values:
        position = _omission_position(value)
        if position in omissions:
            raise ValueError(f'duplicate declared omission: {position.chapter}:{position.verse}.')
        if position in occupied:
            raise ValueError(
                f'declared omission is present in a dataset: {position.chapter}:{position.verse}.'
            )
        omissions.add(position)
    return tuple(sorted(omissions))


def compare_work(
    work_id: str,
    current: Iterable[SourceVerse],
    source: Iterable[SourceVerse],
    rules: ComparisonRules | None = None,
    *,
    declared_omissions: Iterable[VersePosition | tuple[int, int]] = (),
    source_artifact_sha256: str,
    current_publication_sha256: str,
    parser_version: str,
) -> WorkComparisonReport:
    """Compare one work and return a stable immutable report."""
    _validate_normalized_identifier('work_id', work_id)
    _validate_nonblank_string('parser_version', parser_version)
    if rules is None:
        rules = ComparisonRules()
    if type(rules) is not ComparisonRules:
        raise ValueError('rules must be ComparisonRules.')

    source_artifact = SourceArtifactIdentity(source_artifact_sha256)
    current_publication = CurrentPublicationIdentity(current_publication_sha256)
    current_by_position = _index_rows(current, work_id, 'current')
    source_by_position = _index_rows(source, work_id, 'source')
    omissions = _validated_omissions(
        declared_omissions,
        set(current_by_position) | set(source_by_position),
    )

    counts = {name: 0 for name in ('exact', 'formatting', 'missing', 'extra', 'wording')}
    differences: list[VerseDifference] = []
    for position in sorted(set(current_by_position) | set(source_by_position)):
        current_row = current_by_position.get(position)
        source_row = source_by_position.get(position)
        if current_row is None:
            classification = DifferenceClassification.MISSING
        elif source_row is None:
            classification = DifferenceClassification.EXTRA
        elif normalize_exact(current_row.text, rules) == normalize_exact(source_row.text, rules):
            counts['exact'] += 1
            continue
        elif (
            rules.collapse_whitespace
            and normalize_formatting(current_row.text, rules)
            == normalize_formatting(source_row.text, rules)
        ):
            classification = DifferenceClassification.FORMATTING
        else:
            classification = DifferenceClassification.WORDING

        counts[classification.value] += 1
        differences.append(VerseDifference(
            position=position,
            classification=classification,
            current_text=None if current_row is None else current_row.text,
            source_text=None if source_row is None else source_row.text,
        ))

    return WorkComparisonReport(
        schema_version=1,
        work_id=work_id,
        source_artifact=source_artifact,
        current_publication=current_publication,
        parser_version=parser_version,
        rules=rules,
        totals=ComparisonCounts(**counts),
        declared_omissions=omissions,
        differences=tuple(differences),
    )
